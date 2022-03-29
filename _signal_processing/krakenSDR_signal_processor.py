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
#os.environ['OPENBLAS_NUM_THREADS'] = '4'
#os.environ['NUMBA_CPU_NAME'] = 'cortex-a72'
#os.environ['NUMBA_OPT'] = '4'

import time
import logging
import threading
import queue
import math
import copy

# Import optimization modules
import numba as nb
from numba import jit, njit
from functools import lru_cache
from joblib import Parallel, delayed
import multiprocessing

# Math support
import numpy as np
import numpy.linalg as lin
#import numexpr as ne
#from numba import jit
#import pyfftw

# Signal processing support
import scipy
from scipy import fft
from scipy import signal
from scipy.signal import correlate
from scipy.signal import convolve
from pyargus import directionEstimation as de

#import socket
# UDP is useless to us because it cannot work over mobile internet

# Init UDP
#server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
# Enable broadcasting mode
#server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# Set a timeout so the  socket does not block
# indefinitely when trying to receive data.
#server.settimeout(0.2)

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
        self.squelch_update = True
        self.squelch_threshold = 0.1
        self.squelch_trigger_channel = 0
        self.raw_signal_amplitude = np.empty(0)
        self.filt_signal = np.empty(0)
        self.squelch_mask = np.empty(0)

        self.phasetest = [0,0,0,0,0]
        self.dsp_decimation = 0
                
        # DOA processing options
        self.en_DOA_Bartlett = False
        self.en_DOA_Capon    = False
        self.en_DOA_MEM      = False
        self.en_DOA_MUSIC    = False
        self.en_DOA_FB_avg   = False
        self.DOA_offset      = 0
        self.DOA_inter_elem_space = 0.5
        self.DOA_ant_alignment    = "ULA"
        self.DOA_theta =  np.linspace(0,359,360)

            
        # Processing parameters        
        self.spectrum_window_size = fft.next_fast_len(4096) #16384) #16384 #2048 #8192 #2048 #8192 #4096 #2048 #1024
        self.spectrum_plot_size = 1024 #16384) #16384 #2048 #8192 #2048 #8192 #4096 #2048 #1024
        self.spectrum_window = "hann"
        self.run_processing = False
        self.is_running = False 
        self.channel_number = 4  # Update from header
        self.spectrum_fig_type = 0 #0 Single, 1 Full

        self.max_vfos = 16
        self.vfo_bw = [12500] * self.max_vfos
        self.vfo_freq = [self.module_receiver.daq_center_freq] * self.max_vfos
        self.vfo_squelch = [-120] * self.max_vfos
        
        # Result vectors
        self.DOA_Bartlett_res = np.ones(181)
        self.DOA_Capon_res = np.ones(181)
        self.DOA_MEM_res = np.ones(181)
        self.DOA_MUSIC_res = np.ones(181)
        self.DOA_theta = np.arange(0,181,1)

        self.ch_center_pt = 0
        #self.max_index = 0
        self.max_frequency = 0
        #self.fft_signal_width = 0
        self.ch_width_pts = 0
        

       
        self.active_vfos = 2
        self.output_vfo = 0

        self.DOA_theta =  np.linspace(0,359,360)

        self.spectrum = None #np.ones((self.channel_number+2,N), dtype=np.float32)
        self.spectrum_upd_counter = 0

        self.corrections = np.zeros((self.channel_number, 16384), dtype=np.complex64)



    def run(self):
        """
            Main processing thread        
        """
        
        #pyfftw.config.NUM_THREADS = 4
        #scipy.fft.set_global_backend(pyfftw.interfaces.scipy_fft)
        #pyfftw.interfaces.cache.enable()
        
        scipy.fft.set_workers(4)

        #fir_filt, b = signal.firwin(65, 1. / 2, window='hann'), 1.
        #fir_filt = np.ascontiguousarray(fir_filt)
        #parallel = Parallel(n_jobs=4, backend="threading")

        while True:
            self.is_running = False
            time.sleep(1)
            #window = signal.tukey(self.spectrum_window_size, 0.25)

            while self.run_processing:  
                self.is_running = True

                que_data_packet = []

                #-----> ACQUIRE NEW DATA FRAME <-----
                self.module_receiver.get_iq_online()

                start_time = time.time()

                # Check frame type for processing
                en_proc = (self.module_receiver.iq_header.frame_type == self.module_receiver.iq_header.FRAME_TYPE_DATA)# or \
                          #(self.module_receiver.iq_header.frame_type == self.module_receiver.iq_header.FRAME_TYPE_CAL)# For debug purposes
                """
                    You can enable here to process other frame types (such as call type frames)
                """

                que_data_packet.append(['iq_header',self.module_receiver.iq_header])
                self.logger.debug("IQ header has been put into the data que entity")

                # Configure processing parameteres based on the settings of the DAQ chain
                if self.first_frame:
                    self.channel_number = self.module_receiver.iq_header.active_ant_chs
                    self.spectrum_upd_counter = 0
                    self.spectrum = np.ones((self.channel_number+4, self.spectrum_window_size), dtype=np.float32)
                    self.first_frame = 0
                    self.corrections = np.zeros((self.channel_number, 1048576), dtype=np.complex64)


                decimation_factor = 1

                self.data_ready = False

                if en_proc:
                    self.processed_signal = np.ascontiguousarray(self.module_receiver.iq_samples) #self.module_receiver.iq_samples.copy()
                    sampling_freq = self.module_receiver.iq_header.sampling_freq


                    global_decimation_factor = max(int(self.dsp_decimation), 1) #max(int(self.phasetest[0]), 1) #ps_len // 65536 #int(self.phasetest[0]) + 1
                    #for m in range(0, self.channel_number-1):
                        #self.processed_signal[m,:] = signal.oaconvolve(self.processed_signal[m,:], fir_filt, mode='same') #signal.lfilter(fir_filt, 1., self.processed_signal)
                        #self.processed_signal[m,:] = np.convolve(self.processed_signal[m,:], fir_filt, mode='same') #signal.lfilter(fir_filt, 1., self.processed_signal)
 
                    if global_decimation_factor > 1:
                        self.processed_signal = signal.decimate(self.processed_signal, global_decimation_factor, n = global_decimation_factor * 2, ftype='fir')
                        sampling_freq = sampling_freq//global_decimation_factor

                    ps_len = len(self.processed_signal[0,:])
                    avg = int(self.phasetest[0]) + 1 #ps_len // 65536 #int(self.phasetest[0]) + 1

                    self.data_ready = True
                    max_amplitude = -100

                    if self.spectrum_fig_type == 0:
                        m = 0
                        N = self.spectrum_window_size
                        self.spectrum = np.ones((self.channel_number+(self.active_vfos*2+1), N), dtype=np.float32) # Only 0.1 ms, not performance bottleneck

                        single_ch = self.processed_signal[1,:]
                        f, Pxx_den = signal.welch(single_ch, sampling_freq,
                                     nperseg= N,
                                     nfft=N,
                                     noverlap=0.25, #int(N_perseg*0.0),
                                     detrend=False,
                                     return_onesided=False,
                                     window= 'blackman', #('tukey', 0.25), #tukey window gives better time resolution for squelching #self.spectrum_window, #('tukey', 0.25), #self.spectrum_window, 
                                     #window= ('tukey', 0.25), #tukey window gives better time resolution for squelching #self.spectrum_window, #('tukey', 0.25), #self.spectrum_window, 
                                     scaling='spectrum')
                        self.spectrum[1+m,:] = fft.fftshift(10*np.log10(Pxx_den))
                        self.spectrum[0,:] = fft.fftshift(f)
                    else:
                        N = 32768
                        self.spectrum = np.ones((self.channel_number+(self.active_vfos*2+1), N), dtype=np.float32)
                        for m in range(self.channel_number): #range(1): #range(self.channel_number):
                            f, Pxx_den = signal.periodogram(self.processed_signal[m,:], sampling_freq,
                                         nfft=N,
                                         detrend=False,
                                         return_onesided=False,
                                         window= 'blackman',
                                         scaling='spectrum')
                            self.spectrum[1+m,:] = fft.fftshift(10*np.log10(Pxx_den))
                        self.spectrum[0,:] = fft.fftshift(f)
                    
                    #print("spectrum data size: " + str(len(self.spectrum[1,:])))
                


                    #max_ch = np.argmax(np.max(self.spectrum[1:self.module_receiver.iq_header.active_ant_chs+1,:], axis=1)) # Find the channel that had the max amplitude
                    max_amplitude = np.max(self.spectrum[1, :]) #Max amplitude out of all 5 channels
                    #max_spectrum = self.spectrum[1+max_ch, :] #Send max ch to channel centering

                    que_data_packet.append(['max_amplitude',max_amplitude])

                    #-----> DoA PROCESSING <-----

                    single_data_output_vfo = 0

                    if self.data_ready:
                        #self.data_ready = False
                        self.squelch_update = False
                        spectrum_window_size = len(self.spectrum[0,:])
                        #i = 0
                        #TODO: Change ch notation to VFO
                        #TODO: Implement modes:
                        #     1. Single VFO (choose VFO channel to output data)
                        #     2. Any Active VFO (output data from any active VFO (only for use with intermittant signals, otherwise the continuous signal would dominate)
                        #     3. Peak (auto tune to peak signal on spectrum)
                        #     4. All (output all VFOs to JSON only for flutter app)
                        for i in range(self.active_vfos):

                            # If chanenl freq is out of bounds for the current tuned bandwidth, reset to the middle freq
                            if abs(self.vfo_freq[i] - self.module_receiver.daq_center_freq) > sampling_freq/2 :
                                self.vfo_freq[i] = self.module_receiver.daq_center_freq

                            freq = self.vfo_freq[i] - self.module_receiver.daq_center_freq #ch_freq is relative to -sample_freq/2 : sample_freq/2, so correct for that and get the actual freq

                            decimation_factor = max((sampling_freq // self.vfo_bw[i]), 1) # How much decimation is required to get to the requested bandwidth

                            # Get max amplitude of the channel from the FFT for squelching
                            # From channel frequency determine array index of channel
                            ch_width_pts = int((spectrum_window_size * self.vfo_bw[i]) / (sampling_freq)) # Width of channel in array indexes based on FFT size
                            freqMin = -sampling_freq/2

                            ch_center_pt = int((((freq - freqMin) * spectrum_window_size) / sampling_freq))

                            if self.spectrum_fig_type == 0: # Do CH1 only (or make channel selectable)
                                spectrum_channel = self.spectrum[1, ch_center_pt - ch_width_pts//2 : ch_center_pt + ch_width_pts//2]
                                max_amplitude = np.max(spectrum_channel)
                            else:
                                spectrum_channel = self.spectrum[:, ch_center_pt - ch_width_pts//2 : ch_center_pt + ch_width_pts//2]
                                max_amplitude = np.max(spectrum_channel[1:self.module_receiver.iq_header.active_ant_chs+1, :])

                            #Only update if we're above the threshold
                            if max_amplitude > self.vfo_squelch[i]:
                                #self.data_ready = True
                                self.squelch_update = True


                            # *** HERE WE NEED TO PERFORM THE SPECTRUM UPDATE TOO ***
                            if self.en_spectrum:
                                # Selected Channel Window
                                signal_window = np.ones(spectrum_window_size) * -120
                                signal_window[max(ch_center_pt - ch_width_pts//2, 0) : min(ch_center_pt + ch_width_pts//2, spectrum_window_size)] = 0 #max_amplitude
                                self.spectrum[self.channel_number+(2*i+1), :] = signal_window #np.ones(len(spectrum[1,:])) * self.module_receiver.daq_squelch_th_dB # Plot threshold line

                                # Squelch Window
                                signal_window = np.ones(spectrum_window_size) * -120
                                signal_window[max(ch_center_pt - ch_width_pts//2, 0) : min(ch_center_pt + ch_width_pts//2, spectrum_window_size)] = self.vfo_squelch[i]
                                self.spectrum[self.channel_number+(2*i+2), :] = signal_window #np.ones(len(spectrum[1,:])) * self.module_receiver.daq_squelch_th_dB # Plot threshold line

                            #-----> DoA ESIMATION <-----
                            conf_val = 0
                            theta_0 = 0
                            if self.en_DOA_estimation and self.channel_number > 1 and self.squelch_update and (i == self.output_vfo or self.output_vfo < 0):

                                # Do channelization
                                vfo_channel = channelize(self.processed_signal, freq, decimation_factor, sampling_freq)

                                ########################## Method to check IQ diffs when noise source forced ON
                                #iq_diffs = calc_sync(self.processed_signal)
                                #print("IQ DIFFS: " + str(iq_diffs))
                                #print("IQ DIFFS ANGLE: " + str(np.rad2deg(np.angle(iq_diffs))))
                                ##########################

                                self.estimate_DOA(vfo_channel)

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



                        
#################################################### 
                            # KerberosSDR App compatible message output, this will be redundant soon once the new app is published

                            #confidence_str = "{}".format(np.max(int(conf_val*100)))
                            #max_power_level_str = "{:.1f}".format((np.maximum(-100, max_amplitude+100)))

                            #message = str(int(time.time() * 1000)) + ", " + DOA_str + ", " + confidence_str + ", " + max_power_level_str
                            #html_str = "<DATA>\n<DOA>"+DOA_str+"</DOA>\n<CONF>"+confidence_str+"</CONF>\n<PWR>"+max_power_level_str+"</PWR>\n</DATA>"
                            #self.DOA_res_fd.seek(0)
                            #self.DOA_res_fd.write(html_str)
                            #self.DOA_res_fd.truncate()
                            #self.logger.debug("DoA results writen: {:s}".format(html_str))
####################################################

#####################################################
                            #KrakenSDR Android App Output
                            #TODO: This will change into a JSON output
                        
                        freq = str(self.module_receiver.daq_center_freq)
                        latency = str(100)
                        message = str(int(time.time() * 1000)) + ", " \
                                                               + DOA_str + ", " \
                                                               + confidence_str + ", " \
                                                               + max_power_level_str + ", " \
                                                               + freq + ", " \
                                                               + self.DOA_ant_alignment + ", " \
                                                               + latency + ", " \
                                                               + "R, R, R, R, R, R, R, R, R, R" #Reserve 10 entries for other things

                        doa_result_log = doa_result_log + np.abs(np.min(doa_result_log))
                        for i in range(len(doa_result_log)):
                            message += ", " + "{:.2f}".format(doa_result_log[i])
                        
                        self.DOA_res_fd.seek(0)
                        self.DOA_res_fd.write(message)
                        self.DOA_res_fd.truncate()
                        self.logger.debug("DoA results writen: {:s}".format(message))


                    #-----> SPECTRUM PROCESSING <----- 

                    if self.en_spectrum and self.data_ready:

                        spectrum_size = len(self.spectrum[0,:])
                        """
                        # Selected Channel Window
                        signal_window = np.ones(spectrum_size) * -120
                        signal_window[max(self.ch_center_pt - self.ch_width_pts//2, 0) : min(self.ch_center_pt + self.ch_width_pts//2, spectrum_size)] = 0 #max_amplitude
                        self.spectrum[self.channel_number+1, :] = signal_window #np.ones(len(spectrum[1,:])) * self.module_receiver.daq_squelch_th_dB # Plot threshold line

                        # Squelch Window
                        signal_window = np.ones(spectrum_size) * -120
                        signal_window[max(self.ch_center_pt - self.ch_width_pts//2, 0) : min(self.ch_center_pt + self.ch_width_pts//2, spectrum_size)] = self.vfo_squelch[0]
                        self.spectrum[self.channel_number+2, :] = signal_window #np.ones(len(spectrum[1,:])) * self.module_receiver.daq_squelch_th_dB # Plot threshold line
                        """
                        spectrum_plot_data = reduce_spectrum(self.spectrum, self.spectrum_plot_size, self.channel_number)

                        que_data_packet.append(['spectrum', spectrum_plot_data])
                    """
                    #-----> DoA ESIMATION <-----
                    conf_val = 0
                    theta_0 = 0
                    if self.en_DOA_estimation and self.data_ready and self.channel_number > 1 and self.squelch_update:
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



                        
#################################################### 
                        # KerberosSDR App compatible message output, this will be redundant soon once the new app is published

                        #confidence_str = "{}".format(np.max(int(conf_val*100)))
                        #max_power_level_str = "{:.1f}".format((np.maximum(-100, max_amplitude+100)))

                        #message = str(int(time.time() * 1000)) + ", " + DOA_str + ", " + confidence_str + ", " + max_power_level_str
                        #html_str = "<DATA>\n<DOA>"+DOA_str+"</DOA>\n<CONF>"+confidence_str+"</CONF>\n<PWR>"+max_power_level_str+"</PWR>\n</DATA>"
                        #self.DOA_res_fd.seek(0)
                        #self.DOA_res_fd.write(html_str)
                        #self.DOA_res_fd.truncate()
                        #self.logger.debug("DoA results writen: {:s}".format(html_str))
####################################################

#####################################################
                        #KrakenSDR Android App Output
                        #TODO: This will change into a JSON output
                        
                        freq = str(self.module_receiver.daq_center_freq)
                        latency = str(100)
                        message = str(int(time.time() * 1000)) + ", " \
                                                               + DOA_str + ", " \
                                                               + confidence_str + ", " \
                                                               + max_power_level_str + ", " \
                                                               + freq + ", " \
                                                               + self.DOA_ant_alignment + ", " \
                                                               + latency + ", " \
                                                               + "R, R, R, R, R, R, R, R, R, R" #Reserve 10 entries for other things

                        doa_result_log = doa_result_log + np.abs(np.min(doa_result_log))
                        for i in range(len(doa_result_log)):
                            message += ", " + "{:.2f}".format(doa_result_log[i])
                        
                        self.DOA_res_fd.seek(0)
                        self.DOA_res_fd.write(message)
                        self.DOA_res_fd.truncate()
                        self.logger.debug("DoA results writen: {:s}".format(message))
                    """
######################################################

                    # Record IQ samples
                    if self.en_record:
                        # TODO: Implement IQ frame recording
                        self.logger.error("Saving IQ samples to npy is obsolete, IQ Frame saving is currently not implemented")

                stop_time = time.time()
                que_data_packet.append(['update_rate', stop_time-start_time])
                que_data_packet.append(['latency', int(stop_time*10**3)-self.module_receiver.iq_header.time_stamp])

                # If the que is full, and data is ready (from squelching), clear the buffer immediately so that useful data has the priority
                #if self.data_que.full() and self.data_ready:
                #    try:
                        #self.logger.info("BUFFER WAS NOT EMPTY, EMPTYING NOW")
                #        self.data_que.get(False) #empty que if not taken yet so fresh data is put in
                #    except queue.Empty:
                        #self.logger.info("DIDNT EMPTY")
                #        pass

                # Put data into buffer, but if there is no data because its a cal/trig wait frame etc, then only write if the buffer is empty
                # Otherwise just discard the data so that we don't overwrite good DATA frames.
                try:
                    self.data_que.put(que_data_packet, False) # Must be non-blocking so DOA can update when dash browser window is closed
                except:
                    # Discard data, UI couldn't consume fast enough
                    pass

                """
                start = time.time()
                end = time.time()
                thetime = ((end - start) * 1000)
                print ("Time elapsed: ", thetime)
                """

    def estimate_DOA(self, processed_signal):
        """
            Estimates the direction of arrival of the received RF signal
        """

        # Calculating spatial correlation matrix
        R = corr_matrix(processed_signal) #de.corr_matrix_estimate(self.processed_signal.T, imp="fast")

        if self.en_DOA_FB_avg:
            R=de.forward_backward_avg(R)

        M = self.channel_number

        if self.DOA_ant_alignment == "UCA":

            scanning_vectors = gen_scanning_vectors(M, self.DOA_inter_elem_space, self.DOA_ant_alignment)

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
                DOA_MUSIC_res = DOA_MUSIC(R, scanning_vectors, signal_dimension = 1) #de.DOA_MUSIC(R, scanning_vectors, signal_dimension = 1)
                self.DOA_MUSIC_res = DOA_MUSIC_res

        elif self.DOA_ant_alignment == "ULA":

            #x = np.zeros(M)
            #y = -np.arange(M) * self.DOA_inter_elem_space
            #scanning_vectors = de.gen_scanning_vectors(M, x, y, self.DOA_theta)

            scanning_vectors = gen_scanning_vectors(M, self.DOA_inter_elem_space, self.DOA_ant_alignment)

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
                DOA_MUSIC_res = DOA_MUSIC(R, scanning_vectors, signal_dimension = 1)
                self.DOA_MUSIC_res = DOA_MUSIC_res


def calc_sync(iq_samples):
    iq_diffs   = np.ones(4, dtype=np.complex64)
    dyn_ranges = []

    N_proc = len(iq_samples[0,:])

    # Calculate Spatial correlation matrix to determine amplitude-phase missmatches
    Rxx = iq_samples.dot(np.conj(iq_samples.T))
    # Perform eigen-decomposition
    eigenvalues, eigenvectors = lin.eig(Rxx)
    # Get dominant eigenvector
    max_eig_index = np.argmax(np.abs(eigenvalues))
    vmax  = eigenvectors[:, max_eig_index]
    iq_diffs = 1 / vmax
    iq_diffs /= iq_diffs[0]

    return iq_diffs



# Reduce spectrum size for plotting purposes by taking the MAX val every few values
# Significantly faster with numba once we added nb.prange
@njit(fastmath=True, cache=True, parallel=True)
def reduce_spectrum(spectrum, spectrum_size, channel_number):
    spectrum_elements = len(spectrum[:,0])

    spectrum_plot_data = np.ones((spectrum_elements, spectrum_size), dtype=np.float32)
    group = len(spectrum[0,:]) // spectrum_size
    for m in nb.prange(spectrum_elements):
        for i in nb.prange(spectrum_size):
            spectrum_plot_data[m, i] = np.max(spectrum[m, i*group:group*(i+1)])
    return spectrum_plot_data

# Get the FIR filter
@lru_cache(maxsize=8)
def get_fir(n, q, padd):
    #b, a = signal.firwin(n+1, 1. / q, window='hamming'), 1.
    return signal.dlti(signal.firwin(n+1, 1. / (q * padd), window='hann'), 1.)

# Get the frequency rotation exponential
@lru_cache(maxsize=8)
def get_exponential(freq, sample_freq, sig_len):
    # Auto shift peak frequency center of spectrum, this frequency will be decimated:
    # https://pysdr.org/content/filters.html
    f0 = -freq #+10
    Ts = 1.0/sample_freq
    t = np.arange(0.0, Ts*sig_len, Ts)
    exponential = np.exp(2j*np.pi*f0*t) # this is essentially a complex sine wave

    return np.ascontiguousarray(exponential)

@njit(fastmath=True, cache=True, parallel=True)
def numba_mult(a,b):
    return a*b

# Memoize the total shift filter
@lru_cache(maxsize=24)
def shift_filter(decimation_factor, freq, sampling_freq, padd):
    system = get_fir(decimation_factor*2, decimation_factor, padd)
    b = system.num
    a = system.den
    exponential = get_exponential(-freq, sampling_freq, len(b))
    b = numba_mult(b, exponential)
    return signal.dlti(b,a)

# This function takes the full data, and efficiently returns only a filtered and decimated requested channel
# Efficient method: Create BANDPASS Filter for frequency of interest, decimate with that bandpass filter, then do the final shift
#@jit(fastmath=True, cache=True, parallel=True)
def channelize(processed_signal, freq, decimation_factor, sampling_freq):
    system = shift_filter(decimation_factor, freq, sampling_freq, 1.1) # Decimate with a BANDPASS filter
    decimated = signal.decimate(processed_signal, decimation_factor, ftype=system)
    exponential = get_exponential(freq, sampling_freq/decimation_factor, len(decimated[0,:]))     # Shift the signal AFTER to get back to normal decimate behaviour
    return numba_mult(decimated, exponential)

    # Old Method
    # Auto shift peak frequency center of spectrum, this frequency will be decimated:
    # https://pysdr.org/content/filters.html
    #f0 = -freq #+10
    #Ts = 1.0/sample_freq
    #t = np.arange(0.0, Ts*len(processed_signal[0, :]), Ts)
    #exponential = np.exp(2j*np.pi*f0*t) # this is essentially a complex sine wave

    # Decimate down to BW
    #decimation_factor = max((sample_freq // bw), 1)
    #decimated_signal = signal.decimate(processed_signal, decimation_factor, n = decimation_factor * 2, ftype='fir')

    #return decimated_signal

# NUMBA optimized MUSIC function. About 100x faster on the Pi 4
#@njit(fastmath=True, cache=True, parallel=True)
@njit(fastmath=True, cache=True)
def DOA_MUSIC(R, scanning_vectors, signal_dimension, angle_resolution=1):
    # --> Input check
    if R[:,0].size != R[0,:].size:
        print("ERROR: Correlation matrix is not quadratic")
        return np.ones(1, dtype=np.complex64)*-1 #[(-1, -1j)]

    if R[:,0].size != scanning_vectors[:,0].size:
        print("ERROR: Correlation matrix dimension does not match with the antenna array dimension")
        return np.ones(1, dtype=np.complex64)*-2

    ADORT = np.zeros(scanning_vectors[0,:].size, dtype=np.complex64)
    M = R[:,0].size #np.size(R, 0)

    # --- Calculation ---
    # Determine eigenvectors and eigenvalues
    sigmai, vi = lin.eig(R)
    sigmai = np.abs(sigmai)

    idx = sigmai.argsort()[::1] # Sort eigenvectors by eigenvalues, smallest to largest
    #sigmai = sigmai[idx] # Eigenvalues not used again
    vi = vi[:,idx]

    # Generate noise subspace matrix
    noise_dimension = M - signal_dimension
    #E = np.zeros((M, noise_dimension),dtype=np.complex)
    E = np.zeros((M, noise_dimension),dtype=np.complex64)
    for i in range(noise_dimension):
        E[:,i] = vi[:,i]

    theta_index=0
    for i in range(scanning_vectors[0,:].size):
        S_theta_ = scanning_vectors[:, i]
        S_theta_  = S_theta_.T
        ADORT[theta_index] = 1/np.abs(S_theta_.conj().T @ (E @ E.conj().T) @ S_theta_)
        #ADORT[theta_index] = 1/np.abs(np.dot(np.dot(S_theta_.conj().T, (np.dot(E, E.conj().T))), S_theta_))
        theta_index += 1

    return ADORT

# Numba optimized version of pyArgus corr_matrix_estimate with "fast". About 2x faster on Pi4
@njit(fastmath=True, cache=True) #(nb.c8[:,:](nb.c16[:,:]))
def corr_matrix(X):
    #M = X[:,0].size
    N = X[0,:].size
    #R = np.zeros((M, M), dtype=nb.c8)
    R = np.dot(X, X.conj().T)
    R = np.divide(R, N)
    return R

# LRU cache memoize about 1000x faster.
@lru_cache(maxsize=8)
def gen_scanning_vectors(M, DOA_inter_elem_space, type):

    thetas =  np.linspace(0,359,360) # Remember to change self.DOA_thetas too, we didn't include that in this function due to memoization cannot work with arrays
    if type == "UCA":
        x = DOA_inter_elem_space * np.cos(2*np.pi/M * np.arange(M))
        y = -DOA_inter_elem_space * np.sin(2*np.pi/M * np.arange(M)) # For this specific array only
    else: #"ULA"
        x = np.zeros(M)
        y = -np.arange(M) * DOA_inter_elem_space

    scanning_vectors = np.zeros((M, thetas.size), dtype=np.complex64)
    for i in range(thetas.size):
        scanning_vectors[:,i] = np.exp(1j*2*np.pi* (x*np.cos(np.deg2rad(thetas[i])) + y*np.sin(np.deg2rad(thetas[i]))))

    return np.ascontiguousarray(scanning_vectors)
   # scanning_vectors = de.gen_scanning_vectors(M, x, y, self.DOA_theta)

@njit(fastmath=True, cache=True)
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

@njit(fastmath=True, cache=True)
def calculate_doa_papr(DOA_data):
    return 10*np.log10(np.max(np.abs(DOA_data))/np.mean(np.abs(DOA_data)))

# Old time-domain squelch algorithm (Unused as freq domain FFT with overlaps gives significantly better sensitivity with acceptable time resolution expense
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


