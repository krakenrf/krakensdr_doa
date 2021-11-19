# KrakenSDR Signal Processor
#
# Copyright (C) 2018-2021  Carl Laufer, Tamás Pető
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
import math

# Math support
import numpy as np
from numba import jit

# Signal processing support
from scipy import fft
from scipy import signal
from scipy.signal import correlate
from scipy.signal import convolve
from pyargus import directionEstimation as de

import socket

# Init UDP
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
# Enable broadcasting mode
server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# Set a timeout so the  socket does not block
# indefinitely when trying to receive data.
server.settimeout(0.2)

class SignalProcessor(threading.Thread):
    
    def __init__(self, data_que, module_receiver, logging_level=10):

        """
            Parameters:
            -----------
            :param: data_que: Que to communicate with the UI (web iface/Qt GUI)
            :param: module_receiver: Kraken SDR DoA DSP receiver modules
        """        
        super(SignalProcessor, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging_level)

        root_path      = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        doa_res_file_path = os.path.join(os.path.join(root_path,"_android_web","DOA_value.html"))        
        self.DOA_res_fd = open(doa_res_file_path,"w+")

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
        self.DOA_offset      = 0
        self.DOA_inter_elem_space = 0.5
        self.DOA_ant_alignment    = "ULA"
            
        # Processing parameters        
        self.spectrum_window_size = 1024
        self.spectrum_window = "blackmanharris"
        self.run_processing = False
        
        self.channel_number = 4  # Update from header
        
        # Result vectors
        self.DOA_Bartlett_res = np.ones(181)
        self.DOA_Capon_res = np.ones(181)
        self.DOA_MEM_res = np.ones(181)
        self.DOA_MUSIC_res = np.ones(181)
        self.DOA_theta = np.arange(0,181,1)

        self.max_index = 0
        self.max_frequency = 0
        self.fft_signal_width = 0

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

                # Check frame type for processing
                en_proc = (self.module_receiver.iq_header.frame_type == self.module_receiver.iq_header.FRAME_TYPE_DATA)# or \
                          #(self.module_receiver.iq_header.frame_type == self.module_receiver.iq_header.FRAME_TYPE_CAL)# For debug purposes
                """
                    You can enable here to process other frame types (such as call type frames)
                """
                max_amplitude = -100
                max_amplitude_2 = -100
                max_amplitude_3 = -100
                max_amplitude_4 = -100
                max_amplitude_5 = -100
                avg_powers    = [0]
                if en_proc:
                    max_amplitude = 20*np.log10(np.max(np.abs(self.module_receiver.iq_samples[0, :])))
                    max_amplitude_2 = 20*np.log10(np.max(np.abs(self.module_receiver.iq_samples[1, :])))
                    max_amplitude_3 = 20*np.log10(np.max(np.abs(self.module_receiver.iq_samples[2, :])))
                    max_amplitude_4 = 20*np.log10(np.max(np.abs(self.module_receiver.iq_samples[3, :])))
                    max_amplitude_5 = 20*np.log10(np.max(np.abs(self.module_receiver.iq_samples[4, :])))

                    avg_powers = []
                    for m in range(self.module_receiver.iq_header.active_ant_chs):
                        avg_powers.append(10*np.log10(np.average(np.abs(self.module_receiver.iq_samples[m, :])**2)))

                que_data_packet.append(['iq_header',self.module_receiver.iq_header])
                que_data_packet.append(['max_amplitude',max_amplitude])
                que_data_packet.append(['avg_powers',avg_powers])
                self.logger.debug("IQ header has been put into the data que entity")

                # Configure processing parameteres based on the settings of the DAQ chain
                if self.first_frame:
                    self.channel_number = self.module_receiver.iq_header.active_ant_chs
                    self.first_frame = 0

                decimation_factor = 1

                self.data_ready = False

                if en_proc:
                    self.processed_signal = self.module_receiver.iq_samples
                    self.data_ready = True

                    #-----> SQUELCH PROCESSING <-----

                    if self.en_squelch:                    
                        self.data_ready = False

                        #self.logger.info("Payload I zero {:f}".format( self.module_receiver.iq_samples[0, 0].real) )
                        #self.logger.info("Payload Q zero {:f}".format( self.module_receiver.iq_samples[0, 0].imag) )

                        #self.logger.info("Max Amplitude RAW: {:f}".format( np.max(np.abs(self.module_receiver.iq_samples[0, :]))  ))

                        #self.logger.info("Max Amplitude RAW: {:f}".format( np.max(np.abs(self.module_receiver.iq_samples[0, :]))  ))
                        #self.logger.info("Max Amplitude 1 (dB): {:f}".format(max_amplitude))
                        #self.logger.info("Max Amplitude 2 (dB): {:f}".format(max_amplitude_2))
                        #self.logger.info("Max Amplitude 3 (dB): {:f}".format(max_amplitude_3))
                        #self.logger.info("Max Amplitude 4 (dB): {:f}".format(max_amplitude_4))
                        #self.logger.info("Max Amplitude 5 (dB): {:f}".format(max_amplitude_5))
                        #self.logger.info("Threshold Value: {:f}".format(self.squelch_threshold))
                        #self.logger.info("Threshold Value dB: {:f}".format(20 * np.log10(self.squelch_threshold)))


                        N = self.spectrum_window_size

                        N_perseg = 0
                        if len(self.processed_signal[0,:]) > self.spectrum_window_size:
                            N_perseg = N
                        else:
                            N_perseg = len(self.processed_signal[0,:])


                        # Get power spectrum
                        f, Pxx_den = signal.welch(self.processed_signal[0, :], self.module_receiver.iq_header.sampling_freq, 
                                                nperseg=N_perseg//4,
                                                nfft=N,
                                                noverlap=0,
                                                return_onesided=False, 
                                                window=self.spectrum_window,
                                                scaling="spectrum")
                        fft_spectrum = np.fft.fftshift(10*np.log10(Pxx_den))
                        frequency = np.fft.fftshift(f)

                        # Where is the max frequency? e.g. where is the signal?
                        self.max_index = np.argmax(fft_spectrum)
                        self.max_frequency = frequency[self.max_index]
                        self.logger.info("Peak Freq: {:f}".format(self.max_frequency))


                        # Auto decimate down to exactly the max signal width
                        self.fft_signal_width = np.sum(fft_spectrum > self.module_receiver.daq_squelch_th_dB) + 50
                        self.logger.info("Signal Width {:d}".format(self.fft_signal_width))
                        decimation_factor = max((self.module_receiver.iq_header.sampling_freq // self.fft_signal_width) // 4, 1)
                        self.logger.info("Decimation Factor {:d}".format(decimation_factor))
                        #decimation_factor = 2

                        # Auto shift peak frequency center of spectrum, this frequency will be decimated:
                        # https://pysdr.org/content/filters.html
                        f0 = -self.max_frequency #+10
                        Ts = 1.0/self.module_receiver.iq_header.sampling_freq
                        t = np.arange(0.0, Ts*len(self.processed_signal[0, :]), Ts)
                        exponential = np.exp(2j*np.pi*f0*t) # this is essentially a complex sine wave
                        self.processed_signal = self.processed_signal * exponential

                        decimated_signal = []
                        if(decimation_factor > 1):
                            decimated_signal = np.zeros((self.channel_number, math.ceil(len(self.processed_signal[0,:])/decimation_factor)), dtype=np.complex64)

                            for m in range(self.channel_number):
                                decimated_signal[m,:] = signal.decimate(self.processed_signal[m,:], decimation_factor, ftype='fir')

                            self.processed_signal = decimated_signal.copy()


                        self.logger.info("FFT Spectrum Max VAL: {:f}".format(np.max(fft_spectrum)))

                        self.logger.info("Squelch Threshold: {:f}".format(self.module_receiver.daq_squelch_th_dB))

                        #Only update if we're above the threshold
                        if np.max(fft_spectrum) > self.module_receiver.daq_squelch_th_dB:
                            self.data_ready = True


                        # Get trigger channel signal absolutate value
                        #self.raw_signal_amplitude = np.abs(self.module_receiver.iq_samples[0, :])
                        #threshold_array = self.raw_signal_amplitude > self.squelch_threshold

                        #self.processed_signal = self.module_receiver.iq_samples[:, threshold_array]
                        #data_length = len(self.processed_signal[0,:])
                        #self.logger.info("Data Length: {:d}".format(data_length))

                        #if data_length > 10:
                        #    self.data_ready = True

                        """
                        K = 10
                        self.filtered_signal = self.raw_signal_amplitude #convolve(np.abs(self.raw_signal_amplitude),np.ones(K), mode = 'same')/K

                        # Burst is always started at the begining of the processed block, ensured by the squelch module in the DAQ FW
                        burst_stop_index  = len(self.filtered_signal) # CARL FIX: Initialize this to the length of the signal, incase the signal is active the entire time
                        self.logger.info("Original burst stop index: {:d}".format(burst_stop_index))

                        min_burst_size = K                    
                        burst_stop_amp_val = 0
                        for n in np.arange(K, len(self.filtered_signal), 1):                        
                            if self.filtered_signal[n] < self.squelch_threshold:
                                burst_stop_amp_val = self.filtered_signal[n]
                                burst_stop_index = n
                                burst_stop_index-=K # Correction with the length of filter
                                break
                        
                        #burst_stop_index-=K # Correction with the length of filter


                        self.logger.info("Burst stop index: {:d}".format(burst_stop_index))
                        self.logger.info("Burst stop ampl val: {:f}".format(burst_stop_amp_val))
                        self.logger.info("Processed signal length: {:d}".format(len(self.processed_signal[0,:])))

                        # If sign
                        if burst_stop_index < min_burst_size:
                            self.logger.debug("The length of the captured burst size is under the minimum: {:d}".format(burst_stop_index))
                            burst_stop_index = 0

                        if burst_stop_index !=0:                        
                            self.logger.info("INSIDE burst_stop_index != 0")

                            self.logger.debug("Burst stop index: {:d}".format(burst_stop_index))
                            self.logger.debug("Burst stop ampl val: {:f}".format(burst_stop_amp_val))
                            self.squelch_mask = np.zeros(len(self.filtered_signal))                        
                            self.squelch_mask[0 : burst_stop_index] = np.ones(burst_stop_index)*self.squelch_threshold
                            # Next line removes the end parts of the samples after where the signal ended, truncating the array
                            self.processed_signal = self.module_receiver.iq_samples[: burst_stop_index, self.squelch_mask == self.squelch_threshold]
                            self.logger.info("Raw signal length when burst_stop_index!=0: {:d}".format(len(self.module_receiver.iq_samples[0,:])))
                            self.logger.info("Processed signal length when burst_stop_index!=0: {:d}".format(len(self.processed_signal[0,:])))

                            #self.logger.info(' '.join(map(str, self.processed_signal)))

                            self.data_ready=True
                        else:
                            self.logger.info("Signal burst is not found, try to adjust the threshold levels")
                            #self.data_ready=True                            
                            self.squelch_mask = np.ones(len(self.filtered_signal))*self.squelch_threshold
                            self.processed_signal = np.zeros([self.channel_number, len(self.filtered_signal)])
                        """

                     
                    #-----> SPECTRUM PROCESSING <----- 
                    
                    if self.en_spectrum and self.data_ready:
                    #if True and self.data_ready:
                        self.logger.info("UPDATING SPECTRUM")

                        #if len(self.processed_signal[0,:]) > self.spectrum_window_size:
                        N = self.spectrum_window_size
                       # else:
                       #     N = len(self.processed_signal[0,:])

                        #N_perseg = 0
                        #if len(self.processed_signal[0,:]) > self.spectrum_window_size:
                        #    N_perseg = N
                        #else:
                        #    N_perseg = len(self.processed_signal[0,:])


                        N_perseg = 0
                        if len(self.module_receiver.iq_samples[0,:]) > self.spectrum_window_size:
                            N_perseg = N
                        else:
                            N_perseg = len(self.module_receiver.iq_samples[0,:])


                        self.logger.info("N VAL {:d}".format(N))




                           ######################################

                        #spectrum = np.ones((self.channel_number+1,N), dtype=np.float32)

                        #spectrum[0, :] = np.fft.fftshift(np.fft.fftfreq(N, 1/self.module_receiver.iq_header.sampling_freq))/10**6

                        #m = self.channel_number
                        #spectrum[1:m+1,:] = 10*np.log10(np.fft.fftshift(np.abs(np.fft.fft(self.processed_signal[0:m, :]))))

                        #for m in range(self.channel_number):
                        #    spectrum[m+1,:] = 10*np.log10(np.fft.fftshift(np.abs(np.fft.fft(self.processed_signal[m, :]))))


                          ########################################


                        #-> Spectral estimation with the Welch method
                        spectrum = np.ones((self.channel_number+2,N), dtype=np.float32)
                        for m in range(self.channel_number):
                           # self.processed_signal[m, :] = self.processed_signal[m, :] * exponential

                            #f, Pxx_den = signal.welch(self.processed_signal[m, :], self.module_receiver.iq_header.sampling_freq//decimation_factor, 
                            f, Pxx_den = signal.welch(self.module_receiver.iq_samples[m, :], self.module_receiver.iq_header.sampling_freq, 
                                                    nperseg=N_perseg//4,
                                                    nfft=N,
                                                    noverlap=0,
                                                    return_onesided=False, 
                                                    window=self.spectrum_window,
                                                    scaling="spectrum")

                            spectrum[1+m,:] = np.fft.fftshift(10*np.log10(Pxx_den))
                        spectrum[0,:] = np.fft.fftshift(f)

                        signal_window = np.ones(len(spectrum[1,:])) * -100
                        signal_window[max(self.max_index - self.fft_signal_width//2, 0) : min(self.max_index + self.fft_signal_width//2, len(spectrum[1,:]))] = max(spectrum[1,:])


                        spectrum[self.channel_number+1, :] = signal_window #np.ones(len(spectrum[1,:])) * self.module_receiver.daq_squelch_th_dB # Plot threshold line
                        que_data_packet.append(['spectrum', spectrum])

                    #-----> DoA ESIMATION <----- 
                    conf_val = 0
                    theta_0 = 0
                    if self.en_DOA_estimation and self.data_ready:
                        self.estimate_DOA()                        
                        que_data_packet.append(['doa_thetas', self.DOA_theta])
                        if self.en_DOA_Bartlett:
                            doa_result_log = DOA_plot_util(self.DOA_Bartlett_res)
                            theta_0 = self.DOA_theta[np.argmax(doa_result_log)]        
                            conf_val = calculate_doa_papr(self.DOA_Bartlett_res)
                            que_data_packet.append(['DoA Bartlett', doa_result_log])
                            que_data_packet.append(['DoA Bartlett Max', theta_0])
                            que_data_packet.append(['DoA Bartlett confidence', conf_val])
                        if self.en_DOA_Capon:
                            doa_result_log = DOA_plot_util(self.DOA_Capon_res)
                            theta_0 = self.DOA_theta[np.argmax(doa_result_log)]        
                            conf_val = calculate_doa_papr(self.DOA_Capon_res)
                            que_data_packet.append(['DoA Capon', doa_result_log])
                            que_data_packet.append(['DoA Capon Max', theta_0])
                            que_data_packet.append(['DoA Capon confidence', conf_val])
                        if self.en_DOA_MEM:
                            doa_result_log = DOA_plot_util(self.DOA_MEM_res)
                            theta_0 = self.DOA_theta[np.argmax(doa_result_log)]        
                            conf_val = calculate_doa_papr(self.DOA_MEM_res)
                            que_data_packet.append(['DoA MEM', doa_result_log])
                            que_data_packet.append(['DoA MEM Max', theta_0])
                            que_data_packet.append(['DoA MEM confidence', conf_val])
                        if self.en_DOA_MUSIC:
                            doa_result_log = DOA_plot_util(self.DOA_MUSIC_res)
                            theta_0 = self.DOA_theta[np.argmax(doa_result_log)]        
                            conf_val = calculate_doa_papr(self.DOA_MUSIC_res)
                            que_data_packet.append(['DoA MUSIC', doa_result_log])
                            que_data_packet.append(['DoA MUSIC Max', theta_0])
                            que_data_packet.append(['DoA MUSIC confidence', conf_val])

                        DOA_str = str(int(theta_0))
                        confidence_str = "{:.2f}".format(np.max(conf_val))
                        max_power_level_str = "{:.1f}".format((np.maximum(-100, max_amplitude)))
                        message = str(int(time.time() * 1000)) + ", " + DOA_str + ", " + confidence_str + ", " + max_power_level_str
                        #server.sendto(message.encode(), ('<broadcast>', 37020))

                        html_str = "<DATA>\n<DOA>"+DOA_str+"</DOA>\n<CONF>"+confidence_str+"</CONF>\n<PWR>"+max_power_level_str+"</PWR>\n</DATA>"
                        #self.DOA_res_fd.seek(0)
                        #self.DOA_res_fd.write(html_str)
                        #self.DOA_res_fd.truncate()
                        self.logger.debug("DoA results writen: {:s}".format(html_str))
                        
                    # Record IQ samples
                    if self.en_record:          
                        # TODO: Implement IQ frame recording          
                        self.logger.error("Saving IQ samples to npy is obsolete, IQ Frame saving is currently not implemented")

                stop_time = time.time()                
                que_data_packet.append(['update_rate', stop_time-start_time])
                que_data_packet.append(['latency', int(stop_time*10**3)-self.module_receiver.iq_header.time_stamp])

                # If the que is full, and data is ready (from squelching), clear the buffer immediately so that useful data has the priority
                if self.data_que.full() and self.data_ready:
                    try:
                        self.logger.info("BUFFER WAS NOT EMPTY, EMPTYING NOW")                
                        self.data_que.get(False) #empty que if not taken yet so fresh data is put in
                    except queue.Empty:
                        self.logger.info("DIDNT EMPTY")                
                        pass

                # Put data into buffer, but if there is no data because its a cal/trig wait frame etc, then only write if the buffer is empty
                # Otherwise just discard the data so that we don't overwrite good DATA frames.
                try:
                    self.data_que.put(que_data_packet, False) # Must be non-blocking so DOA can update when dash browser window is closed
                except:
                    # Discard data, UI couldn't consume fast enough
                    pass

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
            self.DOA_theta =  np.linspace(0,359,360)

            x = self.DOA_inter_elem_space * np.cos(2*np.pi/M * np.arange(M))
            y = -self.DOA_inter_elem_space * np.sin(2*np.pi/M * np.arange(M)) # For this specific array only
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
            self.DOA_theta =  np.linspace(0,359,360)

            x = np.zeros(M)
            y = -np.arange(M) * self.DOA_inter_elem_space            
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

def calculate_doa_papr(DOA_data):
    return 10*np.log10(np.max(np.abs(DOA_data))/np.average(np.abs(DOA_data)))
