# KerberosSDR Python GUI

# Copyright (C) 2018-2020  Carl Laufer, Tamás Pető
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

import sys
import os
import time
import math
import copy
import pyqtgraph as pg
import pyqtgraph.exporters
import numpy as np
import scipy
from bottle import route, run, request, get, post, redirect, template, static_file
import threading
import subprocess
import save_settings as settings
import logging

np.seterr(divide='ignore')

# Import Kerberos modules
currentPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.dirname(currentPath)

receiverPath        = os.path.join(rootPath, "_receiver")
signalProcessorPath = os.path.join(rootPath, "_signalProcessing")

sys.path.insert(0, receiverPath)
sys.path.insert(0, signalProcessorPath)

from kerberosSDR_receiver import ReceiverRTLSDR
from kerberosSDR_main_window_layout import Ui_MainWindow
from kerberosSDR_signal_processor import SignalProcessor

from PyQt5 import QtGui, QtCore, uic, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import *

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__ (self,parent = None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        logging.basicConfig(level=settings.logging_level*10)
        self.logger = logging.getLogger(__name__)        
        
        #############################################
        #         Initialize trace displays         #
        #############################################

        # Set pyqtgraph to use white background, black foreground
        pg.setConfigOption('background', (61, 61, 61))
        pg.setConfigOption('foreground', 'w')
        pg.setConfigOption('imageAxisOrder', 'row-major')
        #pg.setConfigOption('useOpenGL', True)
        #pg.setConfigOption('useWeave', True)

        # --> Spectrum display
        self.win_spectrum = pg.GraphicsWindow(title="Signal spectrum")
        self.export_spectrum = pg.exporters.ImageExporter(self.win_spectrum.scene())
        self.plotWidget_spectrum = self.win_spectrum.addPlot(title="Spectrum")
        self.gridLayout_spectrum.addWidget(self.win_spectrum, 1, 1, 1, 1)
        self.plotWidget_spectrum.setDownsampling(ds=64, auto=False, mode='mean')
        self.plotWidget_spectrum.addLegend()
        self.plotWidget_spectrum.setLabel("bottom", "Frequency [MHz]")
        self.plotWidget_spectrum.setLabel("left", "Amplitude [dB]")

        # Plot dummy data
        M = 5
        x = np.arange(1000)
        y = np.random.normal(size=(M,1000))
        for m in range(M):
            self.plotWidget_spectrum.plot(x, y[m,:], width=2, name= "Channel {:d}".format(m), pen=pg.intColor(m))
        
        #---> Squelch display
        self.win_squelch = pg.GraphicsWindow(title="Oscilloscope")
        self.export_squelch = pg.exporters.ImageExporter(self.win_squelch.scene())
        self.plotWidget_squelch = self.win_squelch.addPlot(title="Original signal")
        self.win_squelch.nextRow()
        self.plotWidget_burst = self.win_squelch.addPlot(title="Processed burst")

        self.plotWidget_squelch.setLabel("bottom", "Time [ms]")
        self.plotWidget_squelch.setLabel("left", "Amplitude")
        self.plotWidget_squelch.showGrid(x=True, alpha=0.25)

        self.plotWidget_burst.setLabel("bottom", "Time [ms]")
        self.plotWidget_burst.setLabel("left", "Amplitude")
        self.plotWidget_burst.showGrid(x=True, alpha=0.25)

        self.gridLayout_squelch.addWidget(self.win_squelch, 1, 1, 1, 1)
        self.plotWidget_squelch.addLegend()

        x = np.arange(1000)
        y = np.cos(2*np.pi*x/1000)
        f = np.zeros(1000)
        m = np.zeros(1000)
        m[0:100] =1        
        self.plotWidget_squelch.setDownsampling(ds=2**11, auto=False, mode='mean')
        self.plotWidget_squelch.plot(x, y, pen=pg.mkPen('y', width=2), name="Signal amplitude")
        self.plotWidget_squelch.plot(x, f, pen=pg.mkPen('g', width=2), name="Filtered signal")
        self.plotWidget_squelch.plot(x, m, pen=pg.mkPen('r', width=2), name="Mask")
        
        # Plot dummy data
        for m in range(M):
            self.plotWidget_burst.plot(x, np.roll(y,m*10), width=2, name= "Channel {:d}".format(m), pen=pg.intColor(m))
        
        # ---> DOA results display
        self.win_DOA = pg.GraphicsWindow(title="DOA Plot")        
        self.export_DOA = pg.exporters.ImageExporter(self.win_DOA.scene()) # Set up image exporter for web display

        self.plotWidget_DOA = self.win_DOA.addPlot(title="Direction of Arrival Estimation")
        self.plotWidget_DOA.setLabel("bottom", "Incident Angle [deg]")
        self.plotWidget_DOA.setLabel("left", "Amplitude [dB]")
        self.plotWidget_DOA.showGrid(x=True, alpha=0.25)
        self.gridLayout_DOA.addWidget(self.win_DOA, 1, 1, 1, 1)

        self.DOA_res_fd = open("/ram/DOA_value.html","w+") # DOA estimation result file descriptor

        # Plot dummy data
        x = np.arange(10)
        y = np.random.normal(size=(4,10))
        self.plotWidget_DOA.addLegend()
        self.plotWidget_DOA.plot(x, y[0], pen=pg.mkPen((255, 199, 15), width=2), name="Bartlett")
        self.plotWidget_DOA.plot(x, y[1], pen=pg.mkPen('g', width=2), name="Capon")
        self.plotWidget_DOA.plot(x, y[2], pen=pg.mkPen('r', width=2), name="MEM")
        self.plotWidget_DOA.plot(x, y[3], pen=pg.mkPen((9, 237, 237), width=2), name="MUSIC")
        
        #############################################
        #       Connect GUI component signals       #
        #############################################
        
        # Connect pushbutton signals
        self.pushButton_close.clicked.connect(self.pb_close_clicked)
        self.pushButton_proc_control.clicked.connect(self.pb_proc_control_clicked)
        self.pushButton_set_receiver_config.clicked.connect(self.pb_rec_reconfig_clicked)
        self.stream_state = False

        # Status and configuration tab control
        self.tabWidget.currentChanged.connect(self.tab_changed)

        # Connect checkbox signals        
        self.checkBox_en_spectrum.stateChanged.connect(self.set_spectrum_params)
        self.checkBox_en_DOA.stateChanged.connect(self.set_DOA_params)
        self.checkBox_en_DOA_Bartlett.stateChanged.connect(self.set_DOA_params)
        self.checkBox_en_DOA_Capon.stateChanged.connect(self.set_DOA_params)
        self.checkBox_en_DOA_MEM.stateChanged.connect(self.set_DOA_params)
        self.checkBox_en_DOA_MUSIC.stateChanged.connect(self.set_DOA_params)
        self.checkBox_en_DOA_FB_avg.stateChanged.connect(self.set_DOA_params)        
        self.checkBox_en_squelch.stateChanged.connect(self.set_squelch_params)
        
        # Connect spinbox signals        
        self.doubleSpinBox_DOA_d.valueChanged.connect(self.set_DOA_params)
        self.doubleSpinBox_center_freq.valueChanged.connect(self.freq_changed)
        self.spinBox_trigger_channel.valueChanged.connect(self.set_squelch_params)
        self.doubleSpinBox_trigger_threshold.valueChanged.connect(self.set_squelch_params)
        
        # Connect combobox signals
        self.comboBox_antenna_alignment.currentIndexChanged.connect(self.set_DOA_params)
        self.comboBox_gain.currentIndexChanged.connect(self.gain_changed)
        
        #############################################
        # Initialize and Configure Kerberos modules #
        #############################################
        
        # Instantiate Kerberos SDR modules
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
                
        # -> Set default configuration for the signal processing module
        self.set_squelch_params()
        self.set_spectrum_params()
        self.set_DOA_params()
        
        self.DOA_time = time.time()
        self.spectrum_time = time.time()

        # Init peak hold GUI setting
        self.en_peakhold = False

        # Set default confiuration for the GUI components
        self.gain_change_selected=False
        self.freq_change_selected=False
        self.first_frame = 1 # Used to configure local variables from the header fields

        self.set_default_configuration()
        self.disable_daq_configuration()
        
        # Start Web configuration and display interface        
        threading.Thread(target=run, kwargs=dict(host=sys.argv[2], port=8080, quiet=True, debug=False, server='paste')).start()

    #-------------------------------------
    #    GUI control and configuration
    #-------------------------------------
    def set_default_configuration(self):
        """        
            Initialize the values of the GUI components based on the configure file content            
        """
        self.tabWidget.setCurrentIndex(0)
        self.power_level_update(0)
        self.checkBox_en_spectrum.setChecked(False)        
        self.lineEdit_daq_ip_addr.setText(settings.default_ip)
        
        if settings.data_interface == "shmem":
            self.lineEdit_daq_ip_addr.setText("0.0.0.0")

        self.doubleSpinBox_center_freq.setProperty("value", settings.center_freq)
        
        # DOA Estimation settings
        ant_arrangement_index = settings.ant_arrangement_index
        ant_spacing = settings.ant_spacing
        en_doa = "off" #settings.en_doa
        en_bartlett = settings.en_bartlett
        en_capon = settings.en_capon
        en_MEM = settings.en_MEM
        en_MUSIC = settings.en_MUSIC
        en_fbavg = settings.en_fbavg

        self.comboBox_antenna_alignment.setCurrentIndex(int(ant_arrangement_index))
        self.doubleSpinBox_DOA_d.setProperty("value", ant_spacing)
        self.checkBox_en_DOA.setChecked(True if en_doa=="on" else False)
        self.checkBox_en_DOA_Bartlett.setChecked(True if en_bartlett=="on" else False)
        self.checkBox_en_DOA_Capon.setChecked(True if en_capon=="on" else False)
        self.checkBox_en_DOA_MEM.setChecked(True if en_MEM=="on" else False)
        self.checkBox_en_DOA_MUSIC.setChecked(True if en_MUSIC=="on" else False)
        self.checkBox_en_DOA_FB_avg.setChecked(True if en_fbavg=="on" else False)

    def calculate_spacing(self):
        """
            Calulcates the RF parameters of the antenna arangement from the geometrical
            and electrical parameters. After calulcation it updates the corresponding 
            GUI components.
        """
        
        ant_arrangement_index = self.comboBox_antenna_alignment.currentText()
        ant_meters = self.doubleSpinBox_DOA_d.value()
        freq = self.doubleSpinBox_center_freq.value()
        wave_length = (299.79/freq)
        
        if ant_arrangement_index == "ULA":
            ant_spacing = (ant_meters/wave_length)            

        elif ant_arrangement_index == "UCA":
            ant_spacing = ((ant_meters/wave_length)/math.sqrt(2))
        
        # Max phase diff and ambiguity warning        
        max_phase_diff = np.rad2deg(2*np.pi*ant_spacing)
        if max_phase_diff > 180:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "{:.0f} deg".format(max_phase_diff)
            red_text += ("</span>")
            self.label_DoA_ambiguity.setText(red_text)                        
        else:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "{:.0f} deg".format(max_phase_diff)
            green_text += ("</span>")
            self.label_DoA_ambiguity.setText(green_text)     

        return ant_spacing

    def tab_changed(self):
        """
            Handles GUI tab change event
        """
        tab_index = self.tabWidget.currentIndex()

        if tab_index == 0:  # Spectrum tab
            self.stackedWidget_config.setCurrentIndex(0)
        elif tab_index == 1:  # Sync tab
            self.stackedWidget_config.setCurrentIndex(1)
        elif tab_index == 2:  # DOA tab
            self.stackedWidget_config.setCurrentIndex(2)
        
    def set_spectrum_params(self):
        """
            Enables/Disables spectrum calculation and display
        """
        if self.checkBox_en_spectrum.checkState():
            self.module_signal_processor.en_spectrum = True
        else:
            self.module_signal_processor.en_spectrum = False
    
    def gain_changed(self):
        """
            Indicates the gain changing procedure
        """
        self.gain_change_selected = True
        pal = self.comboBox_gain.palette()
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(255,128,0))
        self.comboBox_gain.setPalette(pal)

    def freq_changed(self):
        """
            Indicates the frequency changing procedure
        """
        self.freq_change_selected = True
        pal = self.doubleSpinBox_center_freq.palette()
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor(255,128,0))
        self.doubleSpinBox_center_freq.setPalette(pal)

    def pb_rec_reconfig_clicked(self):
        """
            Handles receiver parameter reconfiguration request
        """
        center_freq = int(self.doubleSpinBox_center_freq.value() *10**6)
        gain = int(10*float(self.comboBox_gain.currentText()))

        if self.freq_change_selected:
            self.module_receiver.set_center_freq(center_freq)
            self.set_DOA_params()            
            self.freq_change_selected = False
            pal = self.doubleSpinBox_center_freq.palette()
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor(255,255,255))
            self.doubleSpinBox_center_freq.setPalette(pal)

        if self.gain_change_selected:
            self.module_receiver.set_if_gain(gain)
            self.gain_change_selected = False
            pal = self.comboBox_gain.palette()
            pal.setColor(QtGui.QPalette.Button, QtGui.QColor(255,255,255))
            self.comboBox_gain.setPalette(pal)

    def set_squelch_params(self):
        """
            Configures the parameters of the squelch mode
        """
        if self.checkBox_en_squelch.checkState():
            self.module_signal_processor.en_squelch = True
        else:
            self.module_signal_processor.en_squelch = False

        self.module_signal_processor.squelch_trigger_channel =  self.spinBox_trigger_channel.value()
        self.module_signal_processor.squelch_threshold = 10**(self.doubleSpinBox_trigger_threshold.value()/10)

        self.disable_daq_configuration()
        self.module_receiver.set_squelch_threshold(self.doubleSpinBox_trigger_threshold.value())

    def set_DOA_params(self):
        """
            Update DOA processing parameters
            Callback function of:
                -
        """        
        if self.checkBox_en_DOA.checkState():
            self.module_signal_processor.en_DOA_estimation = True
        else:
            self.module_signal_processor.en_DOA_estimation = False

        if self.checkBox_en_DOA_Bartlett.checkState():
            self.module_signal_processor.en_DOA_Bartlett = True
        else:
            self.module_signal_processor.en_DOA_Bartlett = False

        if self.checkBox_en_DOA_Capon.checkState():
            self.module_signal_processor.en_DOA_Capon = True
        else:
            self.module_signal_processor.en_DOA_Capon = False

        if self.checkBox_en_DOA_MEM.checkState():
            self.module_signal_processor.en_DOA_MEM = True
        else:
            self.module_signal_processor.en_DOA_MEM = False

        if self.checkBox_en_DOA_MUSIC.checkState():
            self.module_signal_processor.en_DOA_MUSIC = True
        else:
            self.module_signal_processor.en_DOA_MUSIC = False

        if self.checkBox_en_DOA_FB_avg.checkState():
            self.module_signal_processor.en_DOA_FB_avg = True
        else:
            self.module_signal_processor.en_DOA_FB_avg = False

        self.module_signal_processor.DOA_inter_elem_space = self.calculate_spacing()
        self.module_signal_processor.DOA_ant_alignment = self.comboBox_antenna_alignment.currentText()

        if self.module_signal_processor.DOA_ant_alignment == "UCA":
            self.checkBox_en_DOA_FB_avg.setEnabled(False)
            self.checkBox_en_DOA_FB_avg.setCheckState(False)
        else:
            self.checkBox_en_DOA_FB_avg.setEnabled(True)
         
    def pb_close_clicked(self):
        """
            Handles the termination of the modules
            TODO: Proper shutdown should be implemented
        """
        self.module_receiver.close()
        self.DOA_res_fd.close()
        self.close()

    def pb_proc_control_clicked(self):
        """
            Starts / Stops data processing
        """
        if self.pushButton_proc_control.text() == "Start processing":
            self.pushButton_proc_control.setText("Stop processing")
            self.first_frame = 1
            self.module_receiver.rec_ip_addr = self.lineEdit_daq_ip_addr.text()
            self.module_signal_processor.start()

        elif self.pushButton_proc_control.text() == "Stop processing":
            self.pushButton_proc_control.setText("Start processing")
            self.module_signal_processor.stop()
    
    def disable_daq_configuration(self):    
        """
            Disables the DAQ configuration GUI components until 
            new configuration request takes effect, or until the 
            system has not been initialized
        """    
        self.pushButton_set_receiver_config.setEnabled(False)        
        self.spinBox_trigger_channel.setEnabled(False)
        self.doubleSpinBox_trigger_threshold.setEnabled(False)

    def enable_daq_configuration(self):
        """
            Enables the DAQ configuration GUI component after
            succesfull reconfiguration or after the connection has
            been established.
        """
        self.pushButton_set_receiver_config.setEnabled(True)        
        self.spinBox_trigger_channel.setEnabled(True)
        self.doubleSpinBox_trigger_threshold.setEnabled(True)
 
    #-------------------------------------
    #       System status update
    #-------------------------------------

    def iq_header_update(self, max_amplitude):
        """
            Updates the DAQ status display fields based on the content of the
            recently received IQ header data.
        """
        
        self.module_signal_processor.header_data_update_lock.acquire()
        iq_header = copy.copy(self.module_receiver.iq_header)
        self.module_signal_processor.header_data_update_lock.release()
        
        frame_type         = iq_header.frame_type
        sync_state         = iq_header.sync_state
        delay_sync_state   = iq_header.delay_sync_flag
        iq_sync_state      = iq_header.iq_sync_flag
        noise_source_state = iq_header.noise_source_state
        overdrive_flag     = iq_header.adc_overdrive_flags
        freq               = iq_header.rf_center_freq             
        adc_fs             = iq_header.adc_sampling_freq
        sig_fs             = iq_header.sampling_freq
        cpi                = int(iq_header.cpi_length*10**3/iq_header.sampling_freq)
        CPI_index          = iq_header.cpi_index
        frame_sync         = iq_header.check_sync_word()
        
        
        self.label_status_frame_index.setText(str(CPI_index))
        self.label_status_freq.setText(str(freq/10**6)+" MHz")
        self.label_status_adc_fs.setText(str(adc_fs/10**6)+" MHz")
        self.label_status_fs.setText(str(sig_fs/10**6)+" MHz")
        self.label_status_cpi.setText(str(cpi)+" ms")        
        gain_list_str=""
        for m in range(iq_header.active_ant_chs):
            gain_list_str+=str(iq_header.if_gains[m])
            gain_list_str+=", "
        self.label_gain_list.setText(gain_list_str[:-2])
        self.label_trigger_max_amplitude.setText(str("{:1f}".format(max_amplitude)))
        
        self.daq_state_update(frame_type, sync_state)        
        self.delay_sync_update(delay_sync_state)
        self.iq_sync_update(iq_sync_state)
        self.noise_source_update(noise_source_state)
        self.power_level_update(overdrive_flag)     
        self.frame_sync_update(frame_sync)
        
        if self.first_frame:
            self.first_frame = 0
            # Update system center frequency
            self.doubleSpinBox_center_freq.setProperty("value", (freq/10**6))
            self.set_DOA_params()
            pal = self.doubleSpinBox_center_freq.palette()
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor(255,255,255))
            self.doubleSpinBox_center_freq.setPalette(pal)

            self.logger.info("Center frequency field updated, DOA parameters updated")
            

    def daq_state_update(self, frame_type, sync_state):
        """
            DAQ firmware state machine status update
        """
        if sync_state ==-1 and frame_type == -1:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "Not connected"
            red_text += ("</span>")
            self.label_DAQ_subsys_state.setText(red_text)            
            
        elif sync_state==6 and frame_type == 0:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "Normal operation"
            green_text += ("</span>")
            self.label_DAQ_subsys_state.setText(green_text)     

        elif sync_state==6 and frame_type == 0 or frame_type == 3:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "Check calibration"
            green_text += ("</span>")
            self.label_DAQ_subsys_state.setText(green_text)     
            
        elif sync_state !=6 and frame_type == 0:
            blue_text = "<span style=\" font-size:8pt; font-weight:600; color:#0080ff;\" >"
            blue_text += "Uncalibrated"
            blue_text += ("</span>")            
            self.label_DAQ_subsys_state.setText(blue_text)        
            
        elif sync_state !=6 and frame_type == 1:
            orange_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff9933;\" >"
            orange_text += "Configuration"
            orange_text += ("</span>")
            self.label_DAQ_subsys_state.setText(orange_text)        
            
        elif sync_state !=6 and frame_type == 3:
            orange_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff9933;\" >"
            orange_text += "Calibration"
            orange_text += ("</span>")
            self.label_DAQ_subsys_state.setText(orange_text)   

        elif sync_state==6 and frame_type == 4:
            orange_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff9933;\" >"
            orange_text += "Trigger wait"
            orange_text += ("</span>")
            self.label_DAQ_subsys_state.setText(orange_text)   
        else:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "Unknown"
            red_text += ("</span>")
            self.label_DAQ_subsys_state.setText(red_text)   

    def frame_sync_update(self, frame_sync):
        """
            Data frame level synchorny state update
        """
        if frame_sync != 0:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "Sync loss"
            red_text += ("</span>")
            self.label_status_frame_sync.setText(red_text)            
        else:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "OK"
            green_text += ("</span>")
            self.label_status_frame_sync.setText(green_text)

    def delay_sync_update(self, delay_sync_state):
        """
            Sample level synchrony status update
        """
        if not delay_sync_state:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "No sample sync"
            red_text += ("</span>")
            self.label_sample_delay_sync_state.setText(red_text)            
        else:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "Sample sync OK"
            green_text += ("</span>")
            self.label_sample_delay_sync_state.setText(green_text)
         
    def iq_sync_update(self, iq_sync_state):
        """
            Phase synchrony status update
        """
        if not iq_sync_state:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "No IQ sync"
            red_text += ("</span>")
            self.label_IQ_sync_state.setText(red_text)            
        else:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "IQ sync OK"
            green_text += ("</span>")
            self.label_IQ_sync_state.setText(green_text)
        
    def noise_source_update(self, noise_source_state):
        """
            Built in noise source state update
        """
        if noise_source_state:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "Enabled"
            red_text += ("</span>")
            self.label_noise_source_state.setText(red_text)            
        else:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "Disabled"
            green_text += ("</span>")
            self.label_noise_source_state.setText(green_text)
        
        
    def power_level_update(self, over_drive_flag):
        """
            ADC overdrive state update
        """
        if over_drive_flag:
            red_text = "<span style=\" font-size:8pt; font-weight:600; color:#ff0000;\" >"
            red_text += "OVERDRIVE"
            red_text += ("</span>")
            self.label_power_level.setText(red_text)
        else:
            green_text = "<span style=\" font-size:8pt; font-weight:600; color:#01df01;\" >"
            green_text += "OK"
            green_text += ("</span>")
            self.label_power_level.setText(green_text)
            
    def period_time_update(self, update_period):
        """
            IQ data referesh time update
        """
        if update_period > 1:
            self.label_update_rate.setText("%.1f s" %update_period)
        else:
            self.label_update_rate.setText("%.1f ms" %(update_period*1000))
    
    #-------------------------------------
    #         Results display
    #-------------------------------------
    
    def spectrum_plot(self):
        """
            Called by the signal processing module when new spectrum results are available
            It plots the calculated multichannel spectrum
        """
        self.module_signal_processor.spectrum_plot_lock.acquire()
        spectrum = self.module_signal_processor.spectrum
        self.module_signal_processor.spectrum_plot_lock.release()

        freqs = spectrum[0,:]
        self.plotWidget_spectrum.clear() 
        for m in range(np.size(spectrum, 0)-1):   
            self.plotWidget_spectrum.plot(freqs, spectrum[m+1,:], width=2, name= "Channel {:d}".format(m), pen=pg.intColor(m))

        currentTime = time.time()
        if((currentTime - self.spectrum_time) > 0.5):
            self.spectrum_time = currentTime
            self.export_spectrum.export('/ram/spectrum.jpg')

    def squelch_plot(self):
        """
            Called by the signal processing module when new burst has been captured in squelch mode.
            It plots the time domain signal of the received burst.
        """
        if self.checkBox_en_squelch_display.checkState():
            self.module_signal_processor.squelch_plot_lock.acquire()
            fs = self.module_signal_processor.fs
            raw_signal_amplitude = self.module_signal_processor.raw_signal_amplitude
            filtered_signal = self.module_signal_processor.filtered_signal
            squelch_mask = self.module_signal_processor.squelch_mask
            processed_signal = self.module_signal_processor.processed_signal
            self.module_signal_processor.squelch_plot_lock.release()

            self.logger.info("Squlch data ready, plotting..")

            # Plot original signal and triggering results
            self.plotWidget_squelch.clear()
            time_indexes = np.arange(len(raw_signal_amplitude)) * (1/fs)*1000
            self.plotWidget_squelch.plot(time_indexes, raw_signal_amplitude, pen=pg.mkPen(color='y', width=2))
            self.plotWidget_squelch.plot(time_indexes, filtered_signal, pen=pg.mkPen(color='g', width=2))
            self.plotWidget_squelch.plot(time_indexes, squelch_mask, pen=pg.mkPen(color='r', width=2))        
            
            # Plot the found burst
            self.plotWidget_burst.clear()        
            burst_time_indexes =  np.arange(len(processed_signal[0,:])) * (1/fs)*1000        
            for m in range(np.size(processed_signal, 0)):
                self.plotWidget_burst.plot(burst_time_indexes, np.real(processed_signal[m,:]), width=2, name= "Channel {:d}".format(m), pen=pg.intColor(m))

    def DOA_plot_helper(self, DOA_data, incident_angles, log_scale_min=None, color=(255, 199, 15), legend=None):
        """
            This function prepares the calulcated DoA estimation results for plotting. 
            
            - Noramlize DoA estimation results
            - Changes to log scale
            - Plots the results
        """

        DOA_data = np.divide(np.abs(DOA_data), np.max(np.abs(DOA_data))) # Normalization
        if(log_scale_min != None):
            DOA_data = 10*np.log10(DOA_data) # Change to logscale
            theta_index = 0
            for theta in incident_angles: # Remove extremely low values
                if DOA_data[theta_index] < log_scale_min:
                    DOA_data[theta_index] = log_scale_min
                theta_index += 1
        # Plot results
        plot = self.plotWidget_DOA.plot(incident_angles, DOA_data, pen=pg.mkPen(color, width=2))
        return DOA_data

    def DOA_plot(self):
        """
            Called by the signal processing module when new DoA estimation results are available.
            
            This function plots the obtained results, calculates and displays the finally estimated 
            direction utilizing all the the output of the different DoA estimation algorithms.            
        """

        self.module_signal_processor.doa_plot_lock.acquire()
        thetas =  self.module_signal_processor.DOA_theta
        Bartlett  = self.module_signal_processor.DOA_Bartlett_res
        Capon  = self.module_signal_processor.DOA_Capon_res
        MEM  = self.module_signal_processor.DOA_MEM_res
        MUSIC  = self.module_signal_processor.DOA_MUSIC_res
        self.module_signal_processor.doa_plot_lock.release()

        DOA = 0
        DOA_results = []
        COMBINED = np.zeros_like(thetas, dtype=np.complex)

        self.plotWidget_DOA.clear()

        if self.module_signal_processor.en_DOA_Bartlett:

            plt = self.DOA_plot_helper(Bartlett, thetas, log_scale_min = -50, color=(255, 199, 15))
            COMBINED += np.divide(np.abs(Bartlett),np.max(np.abs(Bartlett)))            
            DOA_results.append(thetas[np.argmax(Bartlett)])

        if self.module_signal_processor.en_DOA_Capon:

            self.DOA_plot_helper(Capon, thetas, log_scale_min = -50, color='g')
            COMBINED += np.divide(np.abs(Capon),np.max(np.abs(Capon)))            
            DOA_results.append(thetas[np.argmax(Capon)])

        if self.module_signal_processor.en_DOA_MEM:

            self.DOA_plot_helper(MEM, thetas, log_scale_min = -50, color='r')
            COMBINED += np.divide(np.abs(MEM),np.max(np.abs(MEM)))            
            DOA_results.append(thetas[np.argmax(MEM)])

        if self.module_signal_processor.en_DOA_MUSIC:

            self.DOA_plot_helper(MUSIC, thetas, log_scale_min = -50, color=(9, 237, 237))
            COMBINED += np.divide(np.abs(MUSIC),np.max(np.abs(MUSIC)))            
            DOA_results.append(thetas[np.argmax(MUSIC)])

        """
            The script bellow implements an experimental confidence measurement to improve the DoA estimaiton
            reliability.
        """
        
        if len(DOA_results) != 0:

            # Combined Graph (beta)
            COMBINED_LOG = self.DOA_plot_helper(COMBINED, thetas, log_scale_min = -50, color=(163, 64, 245))

            confidence = scipy.signal.find_peaks_cwt(COMBINED_LOG, np.arange(10,30), min_snr=1) #np.max(DOA_combined**2) / np.average(DOA_combined**2)
            maxIndex = confidence[np.argmax(COMBINED_LOG[confidence])]
            confidence_sum = 0

            self.logger.debug("Peaks: {0}".format((confidence)))            
            for val in confidence:
               if(val != maxIndex and np.abs(COMBINED_LOG[val] - min(COMBINED_LOG)) > np.abs(min(COMBINED_LOG))*0.25):
                  self.logger.debug("Doing other peaks: {0}, combined value: {1}".format(val, COMBINED_LOG[val]))
                  confidence_sum += 1/(np.abs(COMBINED_LOG[val]))
               elif val == maxIndex:
                  self.logger.debug("Doing maxIndex peak: {0}, min combined:  {1}".format(maxIndex, min(COMBINED_LOG)))                  
                  confidence_sum += 1/np.abs(min(COMBINED_LOG))
                  
            # Get avg power level
            max_power_level = 10 #np.max(self.module_signal_processor.spectrum[1,:])
            #rms_power_level = np.sqrt(np.mean(self.module_signal_processor.spectrum[1,:]**2))

            confidence_sum = 10/confidence_sum            
            self.logger.debug("Confidence sum: {0}".format(confidence_sum))
            
            DOA_results = np.array(DOA_results)
            # Convert measured DOAs to complex numbers
            DOA_results_c = np.exp(1j*np.deg2rad(DOA_results))
            # Average measured DOA angles
            DOA_avg_c = np.average(DOA_results_c)
            # Convert back to degree
            DOA = np.rad2deg(np.angle(DOA_avg_c))
            self.logger.debug("DoA results {0}".format(DOA_results))
            
            # Update DOA results on the compass display                        
            if DOA < 0:
                DOA += 360
            #DOA = 360 - DOA
            DOA_str = str(int(DOA))
            html_str = "<DATA>\n<DOA>"+DOA_str+"</DOA>\n<CONF>"+str(int(confidence_sum))+"</CONF>\n<PWR>"+str(np.maximum(0, max_power_level))+"</PWR>\n</DATA>"
            self.DOA_res_fd.seek(0)
            self.DOA_res_fd.write(html_str)
            self.DOA_res_fd.truncate()
            self.logger.debug("DoA results writen: {:s}".format(html_str))

        currentTime = time.time()
        if((currentTime - self.DOA_time) > 0.5):
            self.DOA_time = currentTime
            self.export_DOA.export('/ram/doa.jpg')



def reboot_program():
    form.module_receiver.close()
    form.DOA_res_fd.close()
    subprocess.call(['./run.sh'])

@route('/static/<filepath:path>', name='static')
def server_static(filepath):
    return static_file(filepath, root='./static')


@get('/pr')
def pr():
    en_pr = form.checkBox_en_passive_radar.checkState()

    ref_ch = form.spinBox_ref_ch_select.value()
    surv_ch = form.spinBox_surv_ch_select.value()

    en_clutter = form.checkBox_en_td_filter.checkState()
    filt_dim = form.spinBox_td_filter_dimension.value()
    max_range = form.doubleSpinBox_cc_det_max_range.value()
    max_doppler = form.doubleSpinBox_cc_det_max_Doppler.value()

    windowing_mode = int(form.comboBox_cc_det_windowing.currentIndex())

    dyn_range = form.spinBox_rd_dyn_range.value()


    en_det = form.checkBox_en_autodet.checkState()

    est_win = form.spinBox_cfar_est_win.value()
    guard_win = form.spinBox_cfar_guard_win.value()
    thresh_det = form.doubleSpinBox_cfar_threshold.value()
    
    en_peakhold = form.checkBox_en_peakhold.checkState()

    ip_addr = form.ip_addr

    return template ('pr.tpl', {'en_pr':en_pr,
				'ref_ch':ref_ch,
				'surv_ch':surv_ch,
				'en_clutter':en_clutter,
				'filt_dim':filt_dim,
				'max_range':max_range,
				'max_doppler':max_doppler,
				'windowing_mode':windowing_mode,
				'dyn_range':dyn_range,
				'en_det':en_det,
				'est_win':est_win,
				'guard_win':guard_win,
				'thresh_det':thresh_det,
                                'en_peakhold':en_peakhold,
				'ip_addr':ip_addr})


@get('/doa')
def doa():
    ant_arrangement_index = int(form.comboBox_antenna_alignment.currentIndex())
    ant_meters = form.doubleSpinBox_DOA_d.value()
    en_doa = form.checkBox_en_DOA.checkState()
    en_bartlett = form.checkBox_en_DOA_Bartlett.checkState()
    en_capon = form.checkBox_en_DOA_Capon.checkState()
    en_MEM = form.checkBox_en_DOA_MEM.checkState()
    en_MUSIC = form.checkBox_en_DOA_MUSIC.checkState()
    en_fbavg = form.checkBox_en_DOA_FB_avg.checkState()
    ip_addr = form.ip_addr

    return template ('doa.tpl', {'ant_arrangement_index':ant_arrangement_index,
#				'ant_spacing':ant_spacing,
                'ant_meters' :ant_meters,
				'en_doa':en_doa,
				'en_bartlett':en_bartlett,
				'en_capon':en_capon,
				'en_MEM':en_MEM,
				'en_MUSIC':en_MUSIC,
				'en_fbavg':en_fbavg,
				'ip_addr':ip_addr})


@post('/doa')
def do_doa():
    ant_arrangement_index = request.forms.get('ant_arrangement')
    form.comboBox_antenna_alignment.setCurrentIndex(int(ant_arrangement_index))

    ant_spacing = request.forms.get('ant_spacing')
    form.doubleSpinBox_DOA_d.setProperty("value", ant_spacing)

    en_doa = request.forms.get('en_doa')
    form.checkBox_en_DOA.setChecked(True if en_doa=="on" else False)

    en_bartlett = request.forms.get('en_bartlett')
    form.checkBox_en_DOA_Bartlett.setChecked(True if en_bartlett=="on" else False)

    en_capon = request.forms.get('en_capon')
    form.checkBox_en_DOA_Capon.setChecked(True if en_capon=="on" else False)

    en_MEM = request.forms.get('en_MEM')
    form.checkBox_en_DOA_MEM.setChecked(True if en_MEM=="on" else False)

    en_MUSIC = request.forms.get('en_MUSIC')
    form.checkBox_en_DOA_MUSIC.setChecked(True if en_MUSIC=="on" else False)

    en_fbavg = request.forms.get('en_fbavg')
    form.checkBox_en_DOA_FB_avg.setChecked(True if en_fbavg=="on" else False)

    settings.ant_arrangement_index = ant_arrangement_index
    settings.ant_spacing = ant_spacing
    settings.en_doa = en_doa
    settings.en_bartlett = en_bartlett
    settings.en_capon = en_capon
    settings.en_MEM = en_MEM
    settings.en_MUSIC = en_MUSIC
    settings.en_fbavg = en_fbavg
    form.set_DOA_params()

    settings.write()
    return redirect('doa')


@get('/')
@get('/init')
def init():
    center_freq = form.doubleSpinBox_center_freq.value()
    samp_index = int(form.comboBox_sampling_freq.currentIndex())
    uniform_gain = form.checkBox_en_uniform_gain.checkState()
    gain_index = int(form.comboBox_gain.currentIndex())
    gain_index_2 = int(form.comboBox_gain_2.currentIndex())
    gain_index_3 = int(form.comboBox_gain_3.currentIndex())
    gain_index_4 = int(form.comboBox_gain_4.currentIndex())    
    #filt_bw = form.doubleSpinBox_filterbw.value()
    #fir_size = form.spinBox_fir_tap_size.value()
    #decimation = form.spinBox_decimation.value()
    filt_bw = 0
    fir_size=0
    decimation=0
    ip_addr = form.ip_addr

    return template ('init.tpl', {'center_freq':center_freq,
				'samp_index':samp_index,
                'uniform_gain':uniform_gain,
				'gain_index':gain_index,
				'gain_index_2':gain_index_2,
				'gain_index_3':gain_index_3,
				'gain_index_4':gain_index_4,
				'dc_comp':dc_comp,
				'filt_bw':filt_bw,
				'fir_size':fir_size,
				'decimation':decimation,
				'ip_addr':ip_addr})

@post('/init') # or @route('/login', method='POST')
def do_init():
    if (request.POST.get('rcv_params') == 'rcv_params'):
        center_freq = request.forms.get('center_freq')
        form.doubleSpinBox_center_freq.setProperty("value", center_freq)

        samp_index = request.forms.get('samp_freq')
        form.comboBox_sampling_freq.setCurrentIndex(int(samp_index))

        uniform_gain = request.forms.get('uniform_gain')
        form.checkBox_en_uniform_gain.setChecked(True if uniform_gain=="on" else False)

        if uniform_gain == "on":
            gain_index = request.forms.get('gain')
            form.comboBox_gain.setCurrentIndex(int(gain_index))
            gain_index_2 = request.forms.get('gain')
            form.comboBox_gain_2.setCurrentIndex(int(gain_index))
            gain_index_3 = request.forms.get('gain')
            form.comboBox_gain_3.setCurrentIndex(int(gain_index))
            gain_index_4 = request.forms.get('gain')
            form.comboBox_gain_4.setCurrentIndex(int(gain_index))
        else:
            gain_index = request.forms.get('gain')
            form.comboBox_gain.setCurrentIndex(int(gain_index))
            gain_index_2 = request.forms.get('gain_2')
            form.comboBox_gain_2.setCurrentIndex(int(gain_index_2))
            gain_index_3 = request.forms.get('gain_3')
            form.comboBox_gain_3.setCurrentIndex(int(gain_index_3))
            gain_index_4 = request.forms.get('gain_4')
            form.comboBox_gain_4.setCurrentIndex(int(gain_index_4))

        settings.center_freq = center_freq
        settings.samp_index = samp_index
        settings.uniform_gain = uniform_gain
        settings.gain_index = gain_index
        settings.gain_index_2 = gain_index_2
        settings.gain_index_3 = gain_index_3
        settings.gain_index_4 = gain_index_4
        form.pb_rec_reconfig_clicked()


    if (request.POST.get('iq_params') == 'iq_params'):
        dc_comp = request.forms.get('dc_comp')

        filt_bw = request.forms.get('filt_bw')
        #form.doubleSpinBox_filterbw.setProperty("value", filt_bw)

        fir_size = request.forms.get('fir_size')
        #form.spinBox_fir_tap_size.setProperty("value", fir_size)

        decimation = request.forms.get('decimation')
        #form.spinBox_decimation.setProperty("value", decimation)

        settings.dc_comp = dc_comp
        settings.filt_bw = filt_bw
        settings.fir_size = fir_size
        settings.decimation = decimation
        #form.set_iq_preprocessing_params()

    if (request.POST.get('start') == 'start'):
        form.module_signal_processor.start()
        form.pushButton_proc_control.setText("Stop processing")

    if (request.POST.get('stop') == 'stop'):
        form.module_signal_processor.stop()
        form.pushButton_proc_control.setText("Start processing")

    if (request.POST.get('start_spec') == 'start_spec'):
        form.checkBox_en_spectrum.setChecked(True)
        form.set_spectrum_params()

    if (request.POST.get('stop_spec') == 'stop_spec'):
        form.checkBox_en_spectrum.setChecked(False)
        form.set_spectrum_params()

    if (request.POST.get('reboot') == 'reboot'):
        reboot_program()

    settings.write()

    return redirect('init')

@get('/stats')
def stats():

    upd_rate = form.label_update_rate.text()

    if(form.module_receiver.overdrive_detect_flag):
       ovr_drv = "YES"
    else:
       ovr_drv = "NO"

    return template ('stats.tpl', {'upd_rate':upd_rate,
				'ovr_drv':ovr_drv})

"""
|----------------------------|
|          M A I N           |
|----------------------------|
"""
app = QApplication(sys.argv)
form = MainWindow()
form.show()
app.exec_()
