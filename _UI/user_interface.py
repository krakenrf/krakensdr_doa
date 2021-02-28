# KrakenSDR User Interface

# Copyright (C) 2018-2021 Tamás Pető
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

# -*- coding: utf-8 -*

# Import built-in modules
import logging
import os
import sys
import copy
import save_settings as settings


# Import Kraken SDR modules
current_path = os.path.dirname(os.path.realpath(__file__))
root_path = os.path.dirname(current_path)
receiver_path        = os.path.join(root_path, "_receiver")
signal_processor_path = os.path.join(root_path, "_signal_processing")
web_iface_path = os.path.join(root_path, "_web_interface")


sys.path.insert(0, receiver_path)
sys.path.insert(0, signal_processor_path)
sys.path.insert(0, web_iface_path)


from kerberosSDR_receiver import ReceiverRTLSDR
from kerberosSDR_signal_processor import SignalProcessor
import kraken_web_interface

from PyQt5.QtCore import QObject
#from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


class krakenUserInterface(QObject):

    def __init__(self, parent = None):
        super(QObject, self).__init__()
        #QWidget.__init__(self, parent)
        
        logging.basicConfig(level=settings.logging_level*10)
        self.logger = logging.getLogger(__name__)        

        #############################################
        #  Initialize and Configure Kraken modules  #
        #############################################
        
        # Instantiate Kraken SDR modules
        self.module_receiver = ReceiverRTLSDR(data_interface=settings.data_interface)
        self.module_signal_processor = SignalProcessor(module_receiver=self.module_receiver)
        
        # Connect callback functions to external modules
        self.module_receiver.signal_ctr_iface_comm_finished.connect(self.enable_daq_configuration)
        self.module_signal_processor.signal_overdrive.connect(self.power_level_update)
        self.module_signal_processor.signal_period.connect(self.period_time_update)
        self.module_signal_processor.signal_spectrum_ready.connect(self.spectrum_plot)
        self.module_signal_processor.signal_DOA_ready.connect(self.DOA_plot)
        self.module_signal_processor.signal_squelch_proc_ready.connect(self.squelch_plot)
        self.module_signal_processor.signal_DAQ_status_update.connect(self.iq_header_update)
                
        # -> Set default confiration for the signal processing module
        self.set_squelch_params()
        self.set_spectrum_params()
        self.set_DOA_params()
        
        #self.DOA_time = time.time()
        #self.spectrum_time = time.time()

        self.first_frame = 1 # Used to configure local variables from the header fields

        #self.set_default_configuration()
        #self.disable_daq_configuration()        
        if settings.user_interface == "web":
            kraken_web_interface.webInterface_inst.set_user_interface(self)
            kraken_web_interface.start_server() 
        elif settings.user_interface == "qtgui":
            pass

        self.logger.info("User interface initialized")
    
    def enable_daq_configuration(self):
        """
            Enables the DAQ configuration GUI component after
            succesfull reconfiguration or after the connection has
            been established.
        """
        kraken_web_interface.webInterface_inst.daq_conn_status=1
    def power_level_update(self, over_drive_flag):
        """
            ADC overdrive state update
        """
        pass
    def period_time_update(self, update_period):
        """
            IQ data referesh time update
        """
        if update_period > 1:
            update_period_str="{:.1f}".format(update_period)
        else:
            update_period_str="{:.1f} ms".format(update_period*1000)

        if settings.user_interface == "web":
            kraken_web_interface.webInterface_inst.daq_update_rate = update_period_str
            #kraken_web_interface.webInterface_inst.page_update_rate = update_period
            
    def spectrum_plot(self):
        """
            Called by the signal processing module when new spectrum results are available
            It plots the calculated multichannel spectrum
        """
        kraken_web_interface.webInterface_inst.export_spectrum()

    def squelch_plot(self):
        """
            Called by the signal processing module when new burst has been captured in squelch mode.
            It plots the time domain signal of the received burst.
        """
        pass
    def DOA_plot(self):
        """
            Called by the signal processing module when new DoA estimation results are available.
            
            This function plots the obtained results, calculates and displays the finally estimated 
            direction utilizing all the the output of the different DoA estimation algorithms.            
        """
        pass
    def iq_header_update(self, max_amplitude):
        """
            Updates the DAQ status display fields based on the content of the
            recently received IQ header data.
        """
        self.logger.info("IQ HEADER UPDATE SIGNAL RECEIVED")
        self.module_signal_processor.header_data_update_lock.acquire()
        iq_header = copy.copy(self.module_receiver.iq_header)
        self.module_signal_processor.header_data_update_lock.release()

        if settings.user_interface == "web":            
            kraken_web_interface.webInterface_inst.daq_frame_index = iq_header.cpi_index
        
            kraken_web_interface.webInterface_inst.daq_frame_sync        = iq_header.check_sync_word()            
            kraken_web_interface.webInterface_inst.daq_power_level       = iq_header.adc_overdrive_flags
            kraken_web_interface.webInterface_inst.daq_sample_delay_sync = iq_header.delay_sync_flag
            kraken_web_interface.webInterface_inst.daq_iq_sync           = iq_header.iq_sync_flag
            kraken_web_interface.webInterface_inst.daq_noise_source_state= iq_header.noise_source_state
            kraken_web_interface.webInterface_inst.daq_center_freq       = iq_header.rf_center_freq/10**6
            kraken_web_interface.webInterface_inst.daq_adc_fs            = iq_header.adc_sampling_freq/10**6
            kraken_web_interface.webInterface_inst.daq_fs                = iq_header.sampling_freq/10**6
            kraken_web_interface.webInterface_inst.daq_cpi               = int(iq_header.cpi_length*10**3/iq_header.sampling_freq)
            gain_list_str=""
            for m in range(iq_header.active_ant_chs):
                gain_list_str+=str(iq_header.if_gains[m])
                gain_list_str+=", "
            kraken_web_interface.webInterface_inst.daq_if_gains          =gain_list_str[:-2]
            self.logger.info("web interface data updated")
    
    def set_squelch_params(self):
        """
            Configures the parameters of the squelch mode
        """
        pass
    def set_spectrum_params(self):
        """
            Enables/Disables spectrum calculation and display
        """
        pass
    def set_DOA_params(self):
        """
            Update DOA processing parameters
            Callback function of:
                -
        """      
        pass

    #############################################
    #           User Request Handling           #
    #############################################
    def start_processing(self, ip_addr):
        """
            Starts data processing

            Parameters:
            -----------
            :param: ip_addr: Ip address of the DAQ Subsystem

            :type ip_addr : string e.g.:"127.0.0.1"
        """
        self.module_signal_processor.en_spectrum = True
        
        self.logger.info("Start processing request")
        self.first_frame = 1
        self.module_receiver.rec_ip_addr = ip_addr
        self.module_signal_processor.start()
    def stop_processing(self):
            self.module_signal_processor.stop()

if __name__ == "__main__":        
    app = QApplication(sys.argv)
    krakenUserInterface_inst = krakenUserInterface()
    app.exec_()
    

