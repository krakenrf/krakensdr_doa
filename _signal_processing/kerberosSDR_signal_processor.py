# KerberosSDR Signal Processor
#
# Copyright (C) 2018-2020  Carl Laufer, Tamás Pető
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# - coding: utf-8 -*-

# Import built-in modules
import sys
import os
import time
import logging
import threading
import queue 

# Math support
import numpy as np

# Signal processing support
from scipy import fft
from scipy import signal
from scipy.signal import correlate
from scipy.signal import convolve
from pyargus import directionEstimation as de

class SignalProcessor(threading.Thread):
    
    def __init__(self, data_que, module_receiver):
        """
            Parameters:
            -----------
            :param: data_que: Que to communicate with the UI (web iface/Qt GUI)
            :param: module_receiver: Kraken SDR DoA DSP receiver modules
        """        
        super(SignalProcessor, self).__init__()
        self.logger = logging.getLogger(__name__)

        self.module_receiver = module_receiver
        self.data_que = data_que
        self.en_spectrum = False
        self.en_record = False
        self.en_DOA_estimation = True
        self.first_frame = 1 # Used to configure local variables from the header fields
        self.processed_signal = np.empty(0)        

        # Squelch feature
        self.data_ready = False
        self.en_squelch = False
        self.squelch_threshold = 0.1
        self.squelch_trigger_channel = 0
        self.raw_signal_amplitude = np.empty(0)
        self.filt_signal = np.empty(0)
        self.squelch_mask = np.empty(0)
                
        # DOA processing options
        self.en_DOA_Bartlett = False
        self.en_DOA_Capon    = False
        self.en_DOA_MEM      = False
        self.en_DOA_MUSIC    = False
        self.en_DOA_FB_avg   = False
        self.DOA_inter_elem_space = 0.5
        self.DOA_ant_alignment    = "ULA"
            
        # Processing parameters        
        self.spectrum_window_size = 1024
        self.spectrum_window = "hann"#"blackmanharris"
        self.run_processing = False
        
        self.fs = 1.024 * 10**6  # Update from header
        self.channel_number = 4  # Update from header
        
        # Result vectors
        self.DOA_Bartlett_res = np.ones(181)
        self.DOA_Capon_res = np.ones(181)
        self.DOA_MEM_res = np.ones(181)
        self.DOA_MUSIC_res = np.ones(181)
        self.DOA_theta = np.arange(0,181,1)

    def run(self):
        """
            Main processing thread        
        """
        while True:
            time.sleep(1)
            while self.run_processing:  
                que_data_packet = []

                start_time = time.time()
                        
                #-----> ACQUIRE NEW DATA FRAME <-----                        
                self.module_receiver.get_iq_online()
                # Normal data frame or cal frame ?
                en_proc = self.module_receiver.iq_header.frame_type == self.module_receiver.iq_header.FRAME_TYPE_DATA
                """
                    You can enable here to process other frame types (such as call type frames)
                """
                max_amplitude = 0
                if en_proc:            
                    max_amplitude = 10*np.log10(np.max(np.abs(self.module_receiver.iq_samples[0, :])))
                
                que_data_packet.append(['iq_header',self.module_receiver.iq_header])
                que_data_packet.append(['max_amplitude',max_amplitude])
                self.logger.debug("IQ header has been put into the data que entity")
                            
                # Configure processing parameteres based on the settings of the DAQ chain
                if self.first_frame:
                    self.fs = self.module_receiver.iq_header.sampling_freq
                    self.channel_number = self.module_receiver.iq_header.active_ant_chs
                    self.first_frame = 0
                
                if en_proc:
                    self.processed_signal = self.module_receiver.iq_samples
                    self.data_ready = True
                    
                    #-----> SQUELCH PROCESSING <----- 
                    
                    if self.en_squelch:                    
                        self.data_ready = False

                        # Get trigger channel signal absolutate value
                        self.raw_signal_amplitude = np.abs(self.module_receiver.iq_samples[0, :])

                        K = 50
                        self.filtered_signal = convolve(np.abs(self.raw_signal_amplitude),np.ones(K), mode = 'same')/K

                        # Burst is always started at the begining of the processed block, ensured by the squelch module in the DAQ FW
                        burst_stop_index  = 0
                        min_burst_size = K                    
                        for n in np.arange(K, len(self.filtered_signal), 1):                        
                            if self.filtered_signal[n] < self.squelch_threshold:
                                burst_stop_index = n                            
                                break
                        
                        burst_stop_index-=K # Correction with the length of filter

                        if burst_stop_index < min_burst_size:
                            self.logger.debug("The length of the captured burst size is under the minimum: {:d}".format(burst_stop_index))
                            burst_stop_index = 0

                        if burst_stop_index !=0:                        
                            self.logger.debug("Burst stop index: {:d}".format(burst_stop_index))
                            self.squelch_mask = np.zeros(len(self.filtered_signal))                        
                            self.squelch_mask[0 : burst_stop_index] = np.ones(burst_stop_index)*self.squelch_threshold
                            self.processed_signal = self.module_receiver.iq_samples[: burst_stop_index, self.squelch_mask == self.squelch_threshold]
                            self.data_ready=True
                        else:
                            self.logger.info("Signal burst is not found, try to adjust the threshold levels")
                            self.squelch_mask = np.ones(len(self.filtered_signal))*self.squelch_threshold
                            self.processed_signal = np.zeros([self.channel_number, len(self.filtered_signal)])
                        
                        que_data_packet.append(['squelch_read'])
                    #-----> SPECTRUM PROCESSING <----- 
                    
                    if self.en_spectrum and self.data_ready:

                        if len(self.processed_signal[0,:]) > self.spectrum_window_size:
                            N = self.spectrum_window_size
                        else:
                            N = len(self.processed_signal[0,:])
                        
                        #-> Spectral estimation with the Welch method
                        spectrum = np.ones((self.channel_number+1,N), dtype=np.float32)
                        for m in range(self.channel_number):
                            f, Pxx_den = signal.welch(self.processed_signal[m, :], self.fs, nperseg=N, return_onesided=False, window=self.spectrum_window)
                            spectrum[1+m,:] = np.fft.fftshift(10*np.log10(Pxx_den))
                        spectrum[0,:] = np.fft.fftshift(f)

                        que_data_packet.append(['spectrum', spectrum])

                    #-----> DoA ESIMATION <----- 
                    if self.en_DOA_estimation and self.data_ready:
                        self.estimate_DOA()
                        que_data_packet.append(['doa_thetas', self.DOA_theta])
                        if self.en_DOA_Bartlett:
                            que_data_packet.append(['DoA Bartlett', self.DOA_Bartlett_res])                            
                        if self.en_DOA_Capon:
                            que_data_packet.append(['DoA Capon', self.DOA_Capon_res])
                        if self.en_DOA_MEM:
                            que_data_packet.append(['DoA MEM', self.DOA_MEM_res])
                        if self.en_DOA_MUSIC:
                            que_data_packet.append(['DoA MUSIC', self.DOA_MUSIC_res])
                        
                    
                    # Record IQ samples
                    if self.en_record:          
                        # TODO: Implement IQ frame recording          
                        self.logger.error("Saving IQ samples to npy is obsolete, IQ Frame saving is currently not implemented")

                stop_time = time.time()
                que_data_packet.append(['update_rate', stop_time-start_time])
                self.data_que.put(que_data_packet)

    def estimate_DOA(self):
        """
            Estimates the direction of arrival of the received RF signal
        """
                
        # Calculating spatial correlation matrix
        R = de.corr_matrix_estimate(self.processed_signal.T, imp="fast")

        if self.en_DOA_FB_avg:
            R=de.forward_backward_avg(R)

        M = self.channel_number        

        if self.DOA_ant_alignment == "UCA":
            self.DOA_theta =  np.linspace(0,360,361)

            x = self.DOA_inter_elem_space * np.cos(2*np.pi/M * np.arange(M))
            y = self.DOA_inter_elem_space * np.sin(-2*np.pi/M * np.arange(M)) # For this specific array only
            scanning_vectors = de.gen_scanning_vectors(M, x, y, self.DOA_theta)

             # DOA estimation
            if self.en_DOA_Bartlett:
                DOA_Bartlett_res = de.DOA_Bartlett(R, scanning_vectors)
                self.DOA_Bartlett_res = DOA_Bartlett_res
            if self.en_DOA_Capon:
                DOA_Capon_res = de.DOA_Capon(R, scanning_vectors)
                self.DOA_Capon_res = DOA_Capon_res
            if self.en_DOA_MEM:
                DOA_MEM_res = de.DOA_MEM(R, scanning_vectors,  column_select = 0)
                self.DOA_MEM_res = DOA_MEM_res
            if self.en_DOA_MUSIC:
                DOA_MUSIC_res = de.DOA_MUSIC(R, scanning_vectors, signal_dimension = 1)
                self.DOA_MUSIC_res = DOA_MUSIC_res

        elif self.DOA_ant_alignment == "ULA":
            self.DOA_theta =  np.linspace(-90,90,181)

            x = np.zeros(M)
            y = np.arange(M) * self.DOA_inter_elem_space            
            scanning_vectors = de.gen_scanning_vectors(M, x, y, self.DOA_theta)

            # DOA estimation
            if self.en_DOA_Bartlett:
                DOA_Bartlett_res = de.DOA_Bartlett(R, scanning_vectors)
                self.DOA_Bartlett_res = DOA_Bartlett_res
            if self.en_DOA_Capon:
                DOA_Capon_res = de.DOA_Capon(R, scanning_vectors)
                self.DOA_Capon_res = DOA_Capon_res
            if self.en_DOA_MEM:
                DOA_MEM_res = de.DOA_MEM(R, scanning_vectors,  column_select = 0)
                self.DOA_MEM_res = DOA_MEM_res
            if self.en_DOA_MUSIC:
                DOA_MUSIC_res = de.DOA_MUSIC(R, scanning_vectors, signal_dimension = 1)
                self.DOA_MUSIC_res = DOA_MUSIC_res        

def DOA_plot_util(DOA_data, log_scale_min=-100):
    """
        This function prepares the calulcated DoA estimation results for plotting. 
        
        - Noramlize DoA estimation results
        - Changes to log scale
    """

    DOA_data = np.divide(np.abs(DOA_data), np.max(np.abs(DOA_data))) # Normalization    
    DOA_data = 10*np.log10(DOA_data) # Change to logscale
    
    for i in range(len(DOA_data)): # Remove extremely low values
        if DOA_data[i] < log_scale_min:
            DOA_data[i] = log_scale_min
    
    return DOA_data