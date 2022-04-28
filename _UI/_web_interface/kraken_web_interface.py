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
import logging
import os
import sys
import queue
import time
import subprocess
#import orjson
import json
import csv

import dash_core_components as dcc
import dash_html_components as html

import dash_devices as dash
from dash_devices.dependencies import Input, Output, State

from dash.dash import no_update
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from configparser import ConfigParser

from threading import Timer

# Import Kraken SDR modules
current_path          = os.path.dirname(os.path.realpath(__file__))
root_path             = os.path.dirname(os.path.dirname(current_path))
receiver_path         = os.path.join(root_path, "_receiver")
signal_processor_path = os.path.join(root_path, "_signal_processing")
ui_path               = os.path.join(root_path, "_UI")

sys.path.insert(0, receiver_path)
sys.path.insert(0, signal_processor_path)
sys.path.insert(0, ui_path)

daq_subsystem_path    = os.path.join(
                        os.path.join(os.path.dirname(root_path),
                        "heimdall_daq_fw"),
                        "Firmware")
daq_preconfigs_path   = os.path.join(
                        os.path.join(os.path.dirname(root_path),
                        "heimdall_daq_fw"),
                        "config_files")
daq_config_filename   = os.path.join(daq_subsystem_path, "daq_chain_config.ini")
daq_stop_filename     = "daq_stop.sh"
daq_start_filename    = "daq_start_sm.sh"
#daq_start_filename    = "daq_synthetic_start.sh"
sys.path.insert(0, daq_subsystem_path)

settings_file_path = os.path.join(root_path, "settings.json")
# Load settings file
settings_found = False
if os.path.exists(settings_file_path):
    settings_found = True
    with open(settings_file_path, 'r') as myfile:
        dsp_settings = json.loads(myfile.read())

import ini_checker
from krakenSDR_receiver import ReceiverRTLSDR
from krakenSDR_signal_processor import SignalProcessor
import tooltips

class webInterface():

    def __init__(self):
        self.user_interface = None

        self.logging_level = dsp_settings.get("logging_level", 0)*10
        logging.basicConfig(level=self.logging_level)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.logging_level)
        self.logger.info("Inititalizing web interface ")

        if not settings_found:
            self.logger.warning("Web Interface settings file is not found!")

        #############################################
        #  Initialize and Configure Kraken modules  #
        #############################################

        # Web interface internal
        self.disable_tooltips = dsp_settings.get("disable_tooltips", 0)
        self.page_update_rate = 1
        self._avg_win_size = 10
        self._update_rate_arr = None

        self._doa_method = dsp_settings.get("doa_method", "MUSIC")
        self._doa_fig_type = dsp_settings.get("doa_fig_type", "Linear")

        self.sp_data_que = queue.Queue(1) # Que to communicate with the signal processing module
        self.rx_data_que = queue.Queue(1) # Que to communicate with the receiver modules

        self.data_interface = dsp_settings.get("data_interface", "shmem")

        # Instantiate and configure Kraken SDR modules
        self.module_receiver = ReceiverRTLSDR(data_que=self.rx_data_que, data_interface=self.data_interface, logging_level=self.logging_level)
        self.module_receiver.daq_center_freq   = dsp_settings.get("center_freq", 100.0) * 10**6
        self.module_receiver.daq_rx_gain       = dsp_settings.get("uniform_gain", 1.4)
        self.module_receiver.rec_ip_addr       = dsp_settings.get("default_ip", "0.0.0.0")

        self.module_signal_processor = SignalProcessor(data_que=self.sp_data_que, module_receiver=self.module_receiver, logging_level=self.logging_level)
        self.module_signal_processor.DOA_ant_alignment    = dsp_settings.get("ant_arrangement", "ULA")
        self.ant_spacing_meters = float(dsp_settings.get("ant_spacing_meters", 0.5))
        self.module_signal_processor.DOA_inter_elem_space = self.ant_spacing_meters / (300 / self.module_receiver.daq_center_freq)
        self.module_signal_processor.ula_direction = dsp_settings.get("ula_direction", "Both")

        self.custom_array_x_meters = np.float_(dsp_settings.get("custom_array_x_meters", "0.1,0.2,0.3,0.4,0.5").split(","))
        self.custom_array_y_meters = np.float_(dsp_settings.get("custom_array_y_meters", "0.1,0.2,0.3,0.4,0.5").split(","))
        self.module_signal_processor.custom_array_x = self.custom_array_x_meters / (300 / self.module_receiver.daq_center_freq)
        self.module_signal_processor.custom_array_y = self.custom_array_y_meters / (300 / self.module_receiver.daq_center_freq)

        self.module_signal_processor.en_DOA_estimation    = dsp_settings.get("en_doa", 0)
        self.module_signal_processor.en_DOA_FB_avg        = dsp_settings.get("en_fbavg", 0)
        self.config_doa_in_signal_processor()
        self.module_signal_processor.start()

        #############################################
        #       UI Status and Config variables      #
        #############################################

        # Output Data format.
        self.module_signal_processor.DOA_data_format = dsp_settings.get("doa_data_format", "Kraken App")

        # Station Information
        self.module_signal_processor.station_id    = dsp_settings.get("station_id", "NO-CALL")
        self.location_source                       = dsp_settings.get("location_source", "None")
        self.module_signal_processor.latitude      = dsp_settings.get("latitude", 0.0)
        self.module_signal_processor.longitude     = dsp_settings.get("longitude", 0.0)
        self.module_signal_processor.heading       = dsp_settings.get("heading", 0.0)

        # Kraken Pro Remote Key
        self.module_signal_processor.krakenpro_key = dsp_settings.get("krakenpro_key", 0.0)

        # VFO Configuration
        self.module_signal_processor.spectrum_fig_type = dsp_settings.get("spectrum_calculation", "Single")
        self.module_signal_processor.vfo_mode = dsp_settings.get("vfo_mode", 'Standard')
        self.module_signal_processor.dsp_decimation = int(dsp_settings.get("dsp_decimation", 0))
        self.module_signal_processor.active_vfos = int(dsp_settings.get("active_vfos", 0))
        self.module_signal_processor.output_vfo = int(dsp_settings.get("output_vfo", 0))
        self.module_signal_processor.optimize_short_bursts = dsp_settings.get("en_optimize_short_bursts", 0)
        self.selected_vfo = 0

        for i in range(self.module_signal_processor.max_vfos):
            self.module_signal_processor.vfo_bw[i] = int(dsp_settings.get("vfo_bw_" + str(i), 0))
            self.module_signal_processor.vfo_freq[i] = float(dsp_settings.get("vfo_freq_" + str(i), 0))
            self.module_signal_processor.vfo_squelch[i] = int(dsp_settings.get("vfo_squelch_" + str(i), 0))

        # DAQ Subsystem status parameters
        self.daq_conn_status       = 0
        self.daq_cfg_iface_status  = 0 # 0- ready, 1-busy
        self.daq_restart           = 0 # 1-restarting
        self.daq_update_rate       = 0
        self.daq_frame_sync        = 1 # Active low
        self.daq_frame_index       = 0
        self.daq_frame_type        = "-"
        self.daq_power_level       = 0
        self.daq_sample_delay_sync = 0
        self.daq_iq_sync           = 0
        self.daq_noise_source_state= 0
        self.daq_center_freq       = dsp_settings.get("center_freq", 100.0)
        self.daq_adc_fs            = 0 #"-"
        self.daq_fs                = 0 #"-"
        self.daq_cpi               = 0 #"-"
        self.daq_if_gains          ="[,,,,]"
        self.en_advanced_daq_cfg   = False
        self.en_basic_daq_cfg   = False
        self.daq_ini_cfg_dict      = read_config_file_dict()
        self.active_daq_ini_cfg    = self.daq_ini_cfg_dict['config_name'] #"Default" # Holds the string identifier of the actively loaded DAQ ini configuration
        self.tmp_daq_ini_cfg       = "Default"
        self.daq_cfg_ini_error     = ""

        # DSP Processing Parameters and Results
        self.spectrum              = None
        self.doa_thetas            = None
        self.doa_results           = []
        self.doa_labels            = []
        self.doas                  = [] # Final measured DoAs [deg]
        self.max_doas_list         = []
        self.doa_confidences       = []
        self.compass_ofset         = dsp_settings.get("compass_offset", 0)
        self.daq_dsp_latency       = 0 # [ms]
        self.max_amplitude         = 0 # Used to help setting the threshold level of the squelch
        self.avg_powers            = []
        self.squelch_update        = []
        self.logger.info("Web interface object initialized")

        self.dsp_timer = None
        self.settings_change_timer = None
        self.update_time = 9999

        self.pathname = ""
        self.reset_doa_graph_flag = False
        self.reset_spectrum_graph_flag = False
        self.oldMaxIndex = 9999

        # Refresh Settings Paramaters
        self.last_changed_time_previous = float("inf")
        self.needs_refresh = False

        # Basic DAQ Config
        self.decimated_bandwidth = 12.5

        if self.daq_ini_cfg_dict is not None:
            self.logger.info("Config file found and read succesfully")
            """
             Set the number of channels in the receiver module because it is required
             to produce the initial gain configuration message (Only needed in shared-memory mode)
            """
            self.module_receiver.M = self.daq_ini_cfg_dict['num_ch']

        # Populate vfo_cfg_inputs array for VFO setting callback
        self.vfo_cfg_inputs = []
        self.vfo_cfg_inputs.append(Input(component_id ="spectrum_fig_type", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id ="vfo_mode", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id ="dsp_decimation", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id ="active_vfos", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id ="output_vfo", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id ="en_optimize_short_bursts", component_property="value"))

        for i in range(self.module_signal_processor.max_vfos):
            self.vfo_cfg_inputs.append(Input(component_id ="vfo_"+str(i)+"_bw", component_property="value"))
            self.vfo_cfg_inputs.append(Input(component_id ="vfo_"+str(i)+"_freq", component_property="value"))
            self.vfo_cfg_inputs.append(Input(component_id ="vfo_"+str(i)+"_squelch", component_property="value"))

    def save_configuration(self):
        data = {}

        # DAQ Configuration
        data["center_freq"]    = self.module_receiver.daq_center_freq/10**6
        data["uniform_gain"]   = self.module_receiver.daq_rx_gain
        data["data_interface"] = dsp_settings.get("data_interface", "shmem")
        data["default_ip"]     = dsp_settings.get("default_ip", "0.0.0.0")

        # DOA Estimation
        data["en_doa"]          = self.module_signal_processor.en_DOA_estimation
        data["ant_arrangement"] = self.module_signal_processor.DOA_ant_alignment
        data["ula_direction"] = self.module_signal_processor.ula_direction
        data["ant_spacing_meters"]     = self.ant_spacing_meters #self.module_signal_processor.DOA_inter_elem_space
        data["custom_array_x_meters"]     = ','.join(['%.2f' % num for num in self.custom_array_x_meters])
        data["custom_array_y_meters"]     = ','.join(['%.2f' % num for num in self.custom_array_y_meters])

        data["doa_method"]      = self._doa_method
        data["en_fbavg"]        = self.module_signal_processor.en_DOA_FB_avg
        data["compass_offset"]  = self.compass_ofset
        data["doa_fig_type"]    = self._doa_fig_type

        # Web Interface
        data["en_hw_check"]         = dsp_settings.get("en_hw_check", 0)
        data["logging_level"]       = dsp_settings.get("logging_level", 0)
        data["disable_tooltips"]    = dsp_settings.get("disable_tooltips", 0)

        # Output Data format. XML for Kerberos, CSV for Kracken, JSON future
        data["doa_data_format"] = self.module_signal_processor.DOA_data_format # XML, CSV, or JSON

        # Station Information
        data["station_id"] = self.module_signal_processor.station_id
        data["location_source"] = self.location_source
        data["latitude"] = self.module_signal_processor.latitude
        data["longitude"] = self.module_signal_processor.longitude
        data["heading"] = self.module_signal_processor.heading
        data["krakenpro_key"] = self.module_signal_processor.krakenpro_key


        # VFO Information
        data["spectrum_calculation"] = self.module_signal_processor.spectrum_fig_type
        data["vfo_mode"] = self.module_signal_processor.vfo_mode
        data["dsp_decimation"] = self.module_signal_processor.dsp_decimation
        data["active_vfos"] = self.module_signal_processor.active_vfos
        data["output_vfo"] = self.module_signal_processor.output_vfo
        data["en_optimize_short_bursts"] = self.module_signal_processor.optimize_short_bursts

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            data["vfo_bw_" + str(i)] = self.module_signal_processor.vfo_bw[i]
            data["vfo_freq_" + str(i)] = self.module_signal_processor.vfo_freq[i]
            data["vfo_squelch_" + str(i)] = self.module_signal_processor.vfo_squelch[i]

        with open(settings_file_path, 'w') as outfile:
            json.dump(data, outfile, indent=2)

    def start_processing(self):
        """
            Starts data processing

            Parameters:
            -----------
            :param: ip_addr: Ip address of the DAQ Subsystem

            :type ip_addr : string e.g.:"127.0.0.1"
        """
        self.logger.info("Start processing request")
        self.first_frame = 1
        self.module_signal_processor.run_processing=True
    def stop_processing(self):
        self.module_signal_processor.run_processing=False
        while self.module_signal_processor.is_running: time.sleep(0.01) # Block until signal processor run_processing while loop ends
    def close_data_interfaces(self):
        self.module_receiver.eth_close()
    def close(self):
        pass
    def config_doa_in_signal_processor(self):
        if self._doa_method == "Bartlett":
            self.module_signal_processor.en_DOA_Bartlett = True
            self.module_signal_processor.en_DOA_Capon    = False
            self.module_signal_processor.en_DOA_MEM      = False
            self.module_signal_processor.en_DOA_MUSIC    = False
        elif self._doa_method == "Capon":
            self.module_signal_processor.en_DOA_Bartlett = False
            self.module_signal_processor.en_DOA_Capon    = True
            self.module_signal_processor.en_DOA_MEM      = False
            self.module_signal_processor.en_DOA_MUSIC    = False
        elif self._doa_method == "MEM":
            self.module_signal_processor.en_DOA_Bartlett = False
            self.module_signal_processor.en_DOA_Capon    = False
            self.module_signal_processor.en_DOA_MEM      = True
            self.module_signal_processor.en_DOA_MUSIC    = False
        elif self._doa_method == "MUSIC":
            self.module_signal_processor.en_DOA_Bartlett = False
            self.module_signal_processor.en_DOA_Capon    = False
            self.module_signal_processor.en_DOA_MEM      = False
            self.module_signal_processor.en_DOA_MUSIC    = True
    def config_daq_rf(self, f0, gain):
        """
            Configures the RF parameters in the DAQ module
        """
        self.daq_cfg_iface_status = 1
        self.module_receiver.set_center_freq(int(f0*10**6))
        self.module_receiver.set_if_gain(gain)

        webInterface_inst.logger.info("Updating receiver parameters")
        webInterface_inst.logger.info("Center frequency: {:f} MHz".format(f0))
        webInterface_inst.logger.info("Gain: {:f} dB".format(gain))


def read_config_file_dict(config_fname=daq_config_filename):
    parser = ConfigParser()
    found = parser.read([config_fname])
    ini_data = {}
    if not found:
        return None

    ini_data['config_name'] = parser.get('meta', 'config_name')
    ini_data['num_ch'] = parser.getint('hw', 'num_ch')
    ini_data['en_bias_tee'] = parser.get('hw', 'en_bias_tee')
    ini_data['daq_buffer_size'] = parser.getint('daq','daq_buffer_size')
    ini_data['sample_rate'] = parser.getint('daq','sample_rate')
    ini_data['en_noise_source_ctr'] =  parser.getint('daq','en_noise_source_ctr')
    ini_data['cpi_size'] = parser.getint('pre_processing', 'cpi_size')
    ini_data['decimation_ratio'] = parser.getint('pre_processing', 'decimation_ratio')
    ini_data['fir_relative_bandwidth'] = parser.getfloat('pre_processing', 'fir_relative_bandwidth')
    ini_data['fir_tap_size'] = parser.getint('pre_processing', 'fir_tap_size')
    ini_data['fir_window'] = parser.get('pre_processing','fir_window')
    ini_data['en_filter_reset'] = parser.getint('pre_processing','en_filter_reset')
    ini_data['corr_size'] = parser.getint('calibration','corr_size')
    ini_data['std_ch_ind'] = parser.getint('calibration','std_ch_ind')
    ini_data['en_iq_cal'] = parser.getint('calibration','en_iq_cal')
    ini_data['gain_lock_interval'] = parser.getint('calibration','gain_lock_interval')
    ini_data['require_track_lock_intervention'] = parser.getint('calibration','require_track_lock_intervention')
    ini_data['cal_track_mode'] = parser.getint('calibration','cal_track_mode')
    ini_data['amplitude_cal_mode'] = parser.get('calibration','amplitude_cal_mode')
    ini_data['cal_frame_interval'] = parser.getint('calibration','cal_frame_interval')
    ini_data['cal_frame_burst_size'] = parser.getint('calibration','cal_frame_burst_size')
    ini_data['amplitude_tolerance'] = parser.getint('calibration','amplitude_tolerance')
    ini_data['phase_tolerance'] = parser.getint('calibration','phase_tolerance')
    ini_data['maximum_sync_fails'] = parser.getint('calibration','maximum_sync_fails')
    ini_data['adpis_gains_init'] = parser.get('adpis', 'adpis_gains_init')

    ini_data['out_data_iface_type'] = parser.get('data_interface','out_data_iface_type')

    return ini_data

def write_config_file_dict(param_dict):
    webInterface_inst.logger.info("Write config file: {0}".format(param_dict))
    parser = ConfigParser()
    found = parser.read([daq_config_filename])
    if not found:
        return -1

    # DONT FORGET TO REWRITE en_bias_tee and adpis_gains_init


    parser['meta']['config_name']=str(param_dict['config_name'])
    parser['hw']['num_ch']=str(param_dict['num_ch'])
    parser['hw']['en_bias_tee']=str(param_dict['en_bias_tee'])
    parser['daq']['daq_buffer_size']=str(param_dict['daq_buffer_size'])
    parser['daq']['sample_rate']=str(param_dict['sample_rate'])
    parser['daq']['en_noise_source_ctr']=str(param_dict['en_noise_source_ctr'])
    # Set these for reconfigure
    parser['daq']['center_freq']=str(int(webInterface_inst.module_receiver.daq_center_freq))
    parser['pre_processing']['cpi_size']=str(param_dict['cpi_size'])
    parser['pre_processing']['decimation_ratio']=str(param_dict['decimation_ratio'])
    parser['pre_processing']['fir_relative_bandwidth']=str(param_dict['fir_relative_bandwidth'])
    parser['pre_processing']['fir_tap_size']=str(param_dict['fir_tap_size'])
    parser['pre_processing']['fir_window']=str(param_dict['fir_window'])
    parser['pre_processing']['en_filter_reset']=str(param_dict['en_filter_reset'])
    parser['calibration']['corr_size']=str(param_dict['corr_size'])
    parser['calibration']['std_ch_ind']=str(param_dict['std_ch_ind'])
    parser['calibration']['en_iq_cal']=str(param_dict['en_iq_cal'])
    parser['calibration']['gain_lock_interval']=str(param_dict['gain_lock_interval'])
    parser['calibration']['require_track_lock_intervention']=str(param_dict['require_track_lock_intervention'])
    parser['calibration']['cal_track_mode']=str(param_dict['cal_track_mode'])
    parser['calibration']['amplitude_cal_mode']=str(param_dict['amplitude_cal_mode'])
    parser['calibration']['cal_frame_interval']=str(param_dict['cal_frame_interval'])
    parser['calibration']['cal_frame_burst_size']=str(param_dict['cal_frame_burst_size'])
    parser['calibration']['amplitude_tolerance']=str(param_dict['amplitude_tolerance'])
    parser['calibration']['phase_tolerance']=str(param_dict['phase_tolerance'])
    parser['calibration']['maximum_sync_fails']=str(param_dict['maximum_sync_fails'])
    parser['adpis']['adpis_gains_init'] = str(param_dict['adpis_gains_init'])

    ini_parameters = parser._sections

    error_list = ini_checker.check_ini(ini_parameters, dsp_settings.get("en_hw_check", 0)) #settings.en_hw_check)

    if len(error_list):
        for e in error_list:
            webInterface_inst.logger.error(e)
        return -1, error_list
    else:
        with open(daq_config_filename, 'w') as configfile:
            parser.write(configfile)
        return 0, []

def get_preconfigs(config_files_path):
    parser = ConfigParser()
    preconfigs = []
    preconfigs.append([daq_config_filename, "Current"])
    for root, dirs, files in os.walk(config_files_path):
        if len(files):
            config_file_path = os.path.join(root, files[0])
            parser.read([config_file_path])
            parameters = parser._sections
            preconfigs.append([config_file_path, parameters['meta']['config_name']])
    return preconfigs


#############################################
#          Prepare Dash application         #
############################################
webInterface_inst = webInterface()

#############################################
#       Prepare component dependencies      #
#############################################

trace_colors = px.colors.qualitative.Plotly
trace_colors[3] = 'rgb(255,255,51)'
valid_fir_windows = ['boxcar', 'triang', 'blackman', 'hamming', 'hann', 'bartlett', 'flattop', 'parzen' , 'bohman', 'blackmanharris', 'nuttall', 'barthann']
valid_sample_rates = [0.25, 0.900001, 1.024, 1.4, 1.8, 1.92, 2.048, 2.4, 2.56, 3.2]
valid_daq_buffer_sizes = (2**np.arange(10,21,1)).tolist()
calibration_tack_modes = [['No tracking',0] , ['Periodic tracking',2]]
doa_trace_colors =	{
  "DoA Bartlett": "#00B5F7",
  "DoA Capon"   : "rgb(226,26,28)",
  "DoA MEM"     : "#1CA71C",
  "DoA MUSIC"   : "rgb(257,233,111)"
}
figure_font_size = 20

y=np.random.normal(0,1,2**1)
x=np.arange(2**1)

fig_layout = go.Layout(
                 paper_bgcolor='rgba(0,0,0,0)',
                 plot_bgcolor='rgba(0,0,0,0)',
                 template='plotly_dark',
                 showlegend=True,
                 margin=go.layout.Margin(
                     t=0 #top margin
                 )
             )

option = [{"label":"", "value": 1}]

def init_spectrum_fig(fig_layout, trace_colors):
    spectrum_fig = go.Figure(layout=fig_layout)

    scatter_plot = go.Scatter(x=x,
                              y=y,
                              name="Channel {:d}".format(1),
                              line = dict(color = trace_colors[1], width = 1),
                              )

    for m in range(0, webInterface_inst.module_receiver.M): #+1 for the auto decimation window selection
        scatter = scatter_plot
        scatter['name'] = "Channel {:d}".format(m)
        scatter['line'] = dict(color = trace_colors[m], width = 1)
        spectrum_fig.add_trace(scatter)

    VFO_color = dict(color = 'green', width=0) #trace_colors[webInterface_inst.module_receiver.M + 2], width = 0)
    VFO_squelch_color = dict(color = 'yellow', width=0) #trace_colors[webInterface_inst.module_receiver.M + 1], width = 0)
    VFO_scatter = go.Scatter(x=x,
                             y=y,
                             name="VFO" + str(0),
                             line = VFO_color, #dict(color = trace_colors[m], width = 0),
                             opacity = 0.33,
                             fill='toself',
                             visible=False
                             )
    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        scatter = VFO_scatter
        scatter['name'] = "VFO" + str(i)
        scatter['line'] = VFO_color
        spectrum_fig.add_trace(scatter)

        scatter['name'] = "VFO" + str(i) +" Squelch"
        scatter['line'] = VFO_squelch_color
        spectrum_fig.add_trace(scatter)

        spectrum_fig.add_annotation(
        x=415640000,
        y=-5,
        text="VFO-" + str(i),
        font=dict(size=12,family='Courier New'),
        showarrow=False,
        yshift=10,
        visible=False)

    # Now add the angle display text
    for i in range(webInterface_inst.module_signal_processor.max_vfos): #webInterface_inst.module_signal_processor.active_vfos):
        spectrum_fig.add_annotation(
        x=415640000,
        y=-5,
        text="Angle",
        font=dict(size=12,family='Courier New'),
        showarrow=False,
        yshift=-5,
        visible=False)

    spectrum_fig.update_xaxes(
                    color='rgba(255,255,255,1)',
                    title_font_size=20,
                    tickfont_size= 15, #figure_font_size,
                    #range=[np.min(x), np.max(x)],
                    #rangemode='normal',
                    mirror=True,
                    ticks='outside',
                    showline=True,
                    #fixedrange=True
                    )
    spectrum_fig.update_yaxes(title_text="Amplitude [dB]",
                    color='rgba(255,255,255,1)',
                    title_font_size=20,
                    tickfont_size=figure_font_size,
                    range=[-90, 0],
                    mirror=True,
                    ticks='outside',
                    showline=True,
                    #fixedrange=True
                    )

    spectrum_fig.update_layout(margin=go.layout.Margin(b=5, t=0), hoverdistance=10000)
    spectrum_fig.update(layout_showlegend=False)

    return spectrum_fig

spectrum_fig = init_spectrum_fig(fig_layout, trace_colors)
waterfall_fig = go.Figure(layout=fig_layout)

waterfall_init_x = list(range(0, webInterface_inst.module_signal_processor.spectrum_plot_size-1)) #[1] * webInterface_inst.module_signal_processor.spectrum_window_size
waterfall_init = [[-80] * webInterface_inst.module_signal_processor.spectrum_plot_size] * 50

waterfall_fig.add_trace(go.Heatmapgl(
                         x=waterfall_init_x,
                         z=waterfall_init,
                         zsmooth=False,
                         showscale=False,
                         #hoverinfo='skip',
                         colorscale=[[0.0, '#000020'], # CREDIT: Youssef SDR# color scale
                         [0.0714, '#000030'],
                         [0.1428, '#000050'],
                         [0.2142, '#000091'],
                         [0.2856, '#1E90FF'],
                         [0.357, '#FFFFFF'],
                         [0.4284, '#FFFF00'],
                         [0.4998, '#FE6D16'],
                         [0.5712, '#FE6D16'],
                         [0.6426, '#FF0000'],
                         [0.714, '#FF0000'],
                         [0.7854, '#C60000'],
                         [0.8568, '#9F0000'],
                         [0.9282, '#750000'],
                         [1.0, '#4A0000']]))

waterfall_fig.update_xaxes(tickfont_size=1)
waterfall_fig.update_yaxes(tickfont_size=1,  showgrid=False)
waterfall_fig.update_layout(margin=go.layout.Margin(t=5), hoverdistance=10000) #Set hoverdistance to 1000 seems to be a hack that fixed clickData events not always firing

doa_fig = go.Figure(layout=fig_layout)

#app = dash.Dash(__name__, suppress_callback_exceptions=True, compress=True, update_title="") # cannot use update_title with dash_devices
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "KrakenSDR DoA"

app.config.suppress_callback_exceptions=True


# app_log = logger.getLogger('werkzeug')
# app_log.setLevel(settings.logging_level*10)
# app_log.setLevel(30) # TODO: Only during dev time
app.layout = html.Div([
    dcc.Location(id='url', children='/config',refresh=False),

    html.Div([html.Img(src="assets/kraken_interface_bw.png", style={"display": "block", "margin-left": "auto", "margin-right": "auto", "height": "60px"})]),
    html.Div([html.A("Configuration", className="header_active"   , id="header_config"  ,href="/config"),
            html.A("Spectrum"       , className="header_inactive" , id="header_spectrum",href="/spectrum"),
            html.A("DoA Estimation" , className="header_inactive" , id="header_doa"     ,href="/doa"),
            ], className="header"),

    dcc.Interval(id="settings-refresh-timer", interval=1000, n_intervals=0),

    html.Div(id="placeholder_start"                , style={"display":"none"}),
    html.Div(id="placeholder_stop"                 , style={"display":"none"}),
    html.Div(id="placeholder_save"                 , style={"display":"none"}),
    html.Div(id="placeholder_update_rx"            , style={"display":"none"}),
    html.Div(id="placeholder_recofnig_daq"         , style={"display":"none"}),
    html.Div(id="placeholder_update_daq_ini_params", style={"display":"none"}),
    html.Div(id="placeholder_update_freq"          , style={"display":"none"}),
    html.Div(id="placeholder_update_dsp"           , style={"display":"none"}),
    html.Div(id="placeholder_config_page_upd"      , style={"display":"none"}),
    html.Div(id="placeholder_spectrum_page_upd"    , style={"display":"none"}),
    html.Div(id="placeholder_doa_page_upd"         , style={"display":"none"}),
    html.Div(id="dummy_output"                     , style={"display":"none"}),


    html.Div(id='page-content')
])
def generate_config_page_layout(webInterface_inst):
    # Read DAQ config file
    daq_cfg_dict = webInterface_inst.daq_ini_cfg_dict

    if daq_cfg_dict is not None:
        en_noise_src_values       =[1] if daq_cfg_dict['en_noise_source_ctr']  else []
        en_filter_rst_values      =[1] if daq_cfg_dict['en_filter_reset'] else []
        en_iq_cal_values          =[1] if daq_cfg_dict['en_iq_cal'] else []
        en_req_track_lock_values  =[1] if daq_cfg_dict['require_track_lock_intervention'] else []

        # Read available preconfig files
        preconfigs = get_preconfigs(daq_preconfigs_path)

    en_doa_values         =[1] if webInterface_inst.module_signal_processor.en_DOA_estimation else []
    en_fb_avg_values      =[1] if webInterface_inst.module_signal_processor.en_DOA_FB_avg     else []

    en_optimize_short_bursts    =[1] if webInterface_inst.module_signal_processor.optimize_short_bursts     else []

    en_fixed_heading = [1] if webInterface_inst.module_signal_processor.fixed_heading else []

    en_advanced_daq_cfg   =[1] if webInterface_inst.en_advanced_daq_cfg                       else []
    en_basic_daq_cfg   =[1] if webInterface_inst.en_basic_daq_cfg                       else []
    # Calulcate spacings
    wavelength= 300 / webInterface_inst.daq_center_freq
    ant_spacing_wavelength = webInterface_inst.module_signal_processor.DOA_inter_elem_space
    ant_spacing_meter = webInterface_inst.ant_spacing_meters #round(wavelength * ant_spacing_wavelength, 3)

    cfg_decimated_bw = ((daq_cfg_dict['sample_rate']) / daq_cfg_dict['decimation_ratio']) / 10**3
    cfg_data_block_len = ( daq_cfg_dict['cpi_size'] / (cfg_decimated_bw) )
    cfg_recal_interval =  (daq_cfg_dict['cal_frame_interval'] * (cfg_data_block_len/10**3)) / 60

    if daq_cfg_dict['cal_track_mode'] == 0: #If set to no tracking
        cfg_recal_interval = 1

    #-----------------------------
    #   Start/Stop Configuration Card
    #-----------------------------
    start_stop_card = \
    html.Div([
        html.Div([html.Div([html.Button('Start Processing', id='btn-start_proc', className="btn_start", n_clicks=0)], className="ctr_toolbar_item"),
              html.Div([html.Button('Stop Processing', id='btn-stop_proc', className="btn_stop", n_clicks=0)], className="ctr_toolbar_item"),
              html.Div([html.Button('Save Configuration', id='btn-save_cfg', className="btn_save_cfg", n_clicks=0)], className="ctr_toolbar_item")
            ], className="ctr_toolbar"),
    ])
    #-----------------------------
    #   DAQ Configuration Card
    #-----------------------------
    # -- > Main Card Layout < --
    daq_config_card_list = \
    [
        html.H2("RF Receiver Configuration", id="init_title_c"),
        html.Div([
                html.Div("Center Frequency [MHz]:", className="field-label"),
                dcc.Input(id='daq_center_freq', value=webInterface_inst.module_receiver.daq_center_freq/10**6, type='number', debounce=True, className="field-body-textbox")
                ], className="field"),
        html.Div([
                html.Div("Receiver Gain:", className="field-label"),
                dcc.Dropdown(id='daq_rx_gain',
                        options=[
                            {'label': '0 dB',    'value': 0},
                            {'label': '0.9 dB',  'value': 0.9},
                            {'label': '1.4 dB',  'value': 1.4},
                            {'label': '2.7 dB',  'value': 2.7},
                            {'label': '3.7 dB',  'value': 3.7},
                            {'label': '7.7 dB',  'value': 7.7},
                            {'label': '8.7 dB',  'value': 8.7},
                            {'label': '12.5 dB', 'value': 12.5},
                            {'label': '14.4 dB', 'value': 14.4},
                            {'label': '15.7 dB', 'value': 15.7},
                            {'label': '16.6 dB', 'value': 16.6},
                            {'label': '19.7 dB', 'value': 19.7},
                            {'label': '20.7 dB', 'value': 20.7},
                            {'label': '22.9 dB', 'value': 22.9},
                            {'label': '25.4 dB', 'value': 25.4},
                            {'label': '28.0 dB', 'value': 28.0},
                            {'label': '29.7 dB', 'value': 29.7},
                            {'label': '32.8 dB', 'value': 32.8},
                            {'label': '33.8 dB', 'value': 33.8},
                            {'label': '36.4 dB', 'value': 36.4},
                            {'label': '37.2 dB', 'value': 37.2},
                            {'label': '38.6 dB', 'value': 38.6},
                            {'label': '40.2 dB', 'value': 40.2},
                            {'label': '42.1 dB', 'value': 42.1},
                            {'label': '43.4 dB', 'value': 43.4},
                            {'label': '43.9 dB', 'value': 43.9},
                            {'label': '44.5 dB', 'value': 44.5},
                            {'label': '48.0 dB', 'value': 48.0},
                            {'label': '49.6 dB', 'value': 49.6},
                            ],
                    value=webInterface_inst.module_receiver.daq_rx_gain, clearable=False, style={"display":"inline-block"}, className="field-body"),
                ], className="field"),
        html.Div([
            html.Button('Update Receiver Parameters', id='btn-update_rx_param', className="btn"),
        ], className="field"),

        html.Div([html.Div("Basic DAQ Configuration", id="label_en_basic_daq_cfg"     , className="field-label"),
                dcc.Checklist(options=option     , id="en_basic_daq_cfg"     ,  className="field-body", value=en_basic_daq_cfg),
        ], className="field"),

        html.Div([


        html.Div([
            html.Div("Preconfigured DAQ Files", className="field-label"),
            dcc.Dropdown(id='daq_cfg_files',
                    options=[
                        {'label': str(i[1]), 'value': i[0]} for i in preconfigs
                    ],
            clearable=False,
            value=preconfigs[0][0],
            placeholder="Select Configuration File",
            persistence=True,
            className="field-body-wide"),
        ], className="field"),
        html.Div([
            html.Div("Active Configuration: " + webInterface_inst.active_daq_ini_cfg, id="active_daq_ini_cfg", className="field-label"),
        ], className="field"),
        html.Div([
                html.Div(webInterface_inst.daq_cfg_ini_error , id="daq_ini_check", className="field-label", style={"color":"#e74c3c"}),
        ], className="field"),

        html.Div([html.Div("Basic Custom DAQ Configuration", id="label_en_basic_daq_cfg"     , className="field-label")]),
            html.Div([
                html.Div("Data Block Length [ms]:", id="label_daq_config_data_block_len", className="field-label"),
                dcc.Input(id='cfg_data_block_len', value=cfg_data_block_len, type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                html.Div("Decimated Bandwidth [kHz]:", id="label_daq_decimated_bw", className="field-label"),
                dcc.Input(id='cfg_decimated_bw', value=cfg_decimated_bw, type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                html.Div("Recalibration Interval [mins]:", id="label_recal_interval", className="field-label"),
                dcc.Input(id='cfg_recal_interval', value=cfg_recal_interval, type='number', debounce=True, className="field-body-textbox")
            ], className="field"),

        html.Div([html.Div("Advanced Custom DAQ Configuration", id="label_en_advanced_daq_cfg"     , className="field-label"),
                dcc.Checklist(options=option     , id="en_advanced_daq_cfg"     ,  className="field-body", value=en_advanced_daq_cfg),
        ], className="field"),

    # --> Optional DAQ Subsystem reconfiguration fields <--
    #daq_subsystem_reconfiguration_options = [ \
        html.Div([
            html.H2("DAQ Subsystem Reconfiguration", id="init_title_reconfig"),
            html.H3("HW", id="cfg_group_hw"),
            html.Div([
                    html.Div("# RX Channels:", className="field-label"),
                    dcc.Input(id='cfg_rx_channels', value=daq_cfg_dict['num_ch'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.H3("DAQ", id="cfg_group_daq"),
            html.Div([
                    html.Div("DAQ Buffer Size:", className="field-label", id="label_daq_buffer_size"),
                    dcc.Dropdown(id='cfg_daq_buffer_size',
                                options=[
                                        {'label': i, 'value': i} for i in valid_daq_buffer_sizes
                                ],
                                value=daq_cfg_dict['daq_buffer_size'], style={"display":"inline-block"},className="field-body"),
            ], className="field"),
            html.Div([
                html.Div("Sample Rate [MHz]:", className="field-label", id="label_sample_rate"),
                dcc.Dropdown(id='cfg_sample_rate',
                        options=[
                            {'label': i, 'value': i} for i in valid_sample_rates
                            ],
                    value=daq_cfg_dict['sample_rate']/10**6, style={"display":"inline-block"},className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Enable Noise Source Control:", className="field-label", id="label_en_noise_source_ctr"),
                    dcc.Checklist(options=option     , id="en_noise_source_ctr"   , className="field-body", value=en_noise_src_values),
            ], className="field"),
            html.H3("Pre Processing"),
            html.Div([
                    html.Div("CPI Size [sample]:", className="field-label", id="label_cpi_size"),
                    dcc.Input(id='cfg_cpi_size', value=daq_cfg_dict['cpi_size'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Decimation Ratio:", className="field-label", id="label_decimation_ratio"),
                    dcc.Input(id='cfg_decimation_ratio', value=daq_cfg_dict['decimation_ratio'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("FIR Relative Bandwidth:", className="field-label", id="label_fir_relative_bw"),
                    dcc.Input(id='cfg_fir_bw', value=daq_cfg_dict['fir_relative_bandwidth'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("FIR Tap Size:", className="field-label", id="label_fir_tap_size"),
                    dcc.Input(id='cfg_fir_tap_size', value=daq_cfg_dict['fir_tap_size'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                html.Div("FIR Window:", className="field-label", id="label_fir_window"),
                dcc.Dropdown(id='cfg_fir_window',
                        options=[
                            {'label': i, 'value': i} for i in valid_fir_windows
                            ],
                    value=daq_cfg_dict['fir_window'], style={"display":"inline-block"},className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Enable Filter Reset:", className="field-label", id="label_en_filter_reset"),
                    dcc.Checklist(options=option     , id="en_filter_reset"   , className="field-body", value=en_filter_rst_values),
            ], className="field"),
            html.H3("Calibration"),
            html.Div([
                    html.Div("Correlation Size [sample]:", className="field-label", id="label_correlation_size"),
                    dcc.Input(id='cfg_corr_size', value=daq_cfg_dict['corr_size'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Standard Channel Index:", className="field-label", id="label_std_ch_index"),
                    dcc.Input(id='cfg_std_ch_ind', value=daq_cfg_dict['std_ch_ind'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Enable IQ Calibration:", className="field-label", id="label_en_iq_calibration"),
                    dcc.Checklist(options=option     , id="en_iq_cal"   , className="field-body", value=en_iq_cal_values),
            ], className="field"),
            html.Div([
                    html.Div("Gain Lock Interval [frame]:", className="field-label", id="label_gain_lock_interval"),
                    dcc.Input(id='cfg_gain_lock', value=daq_cfg_dict['gain_lock_interval'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Require Track Lock Intervention (For Kerberos):", className="field-label", id="label_require_track_lock"),
                    dcc.Checklist(options=option     , id="en_req_track_lock_intervention"   , className="field-body", value=en_req_track_lock_values),
            ], className="field"),
            html.Div([
                    html.Div("Calibration Track Mode:", className="field-label", id="label_calibration_track_mode"),
                    dcc.Dropdown(id='cfg_cal_track_mode',
                                options=[
                                        {'label': i[0], 'value': i[1]} for i in calibration_tack_modes
                                ],
                                value=daq_cfg_dict['cal_track_mode'], style={"display":"inline-block"},className="field-body"),
            ], className="field"),
            html.Div([
                    html.Div("Amplitude Calibration Mode :", className="field-label", id="label_amplitude_calibration_mode"),
                    dcc.Dropdown(id='cfg_amplitude_cal_mode',
                                options=[
                                        {'label': 'default', 'value': 'default'},
                                        {'label': 'disabled', 'value': 'disabled'},
                                        {'label': 'channel_power', 'value': 'channel_power'}
                                ],
                                value=daq_cfg_dict['amplitude_cal_mode'], style={"display":"inline-block"},className="field-body"),
            ], className="field"),
            html.Div([
                    html.Div("Calibration Frame Interval:", className="field-label", id="label_calibration_frame_interval"),
                    dcc.Input(id='cfg_cal_frame_interval', value=daq_cfg_dict['cal_frame_interval'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Calibration Frame Burst Size:", className="field-label", id="label_calibration_frame_burst_size"),
                    dcc.Input(id='cfg_cal_frame_burst_size', value=daq_cfg_dict['cal_frame_burst_size'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Amplitude Tolerance [dB]:", className="field-label", id="label_amplitude_tolerance"),
                    dcc.Input(id='cfg_amplitude_tolerance', value=daq_cfg_dict['amplitude_tolerance'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Phase Tolerance [deg]:", className="field-label", id="label_phase_tolerance"),
                    dcc.Input(id='cfg_phase_tolerance', value=daq_cfg_dict['phase_tolerance'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
            html.Div([
                    html.Div("Maximum Sync Fails:", className="field-label", id="label_max_sync_fails"),
                    dcc.Input(id='cfg_max_sync_fails', value=daq_cfg_dict['maximum_sync_fails'], type='number', debounce=True, className="field-body-textbox")
            ], className="field"),
        ], style={'width': '100%'}, id='adv-cfg-container'),

        # Reconfigure Button
        html.Div([
            html.Button('Reconfigure & Restart DAQ chain', id='btn_reconfig_daq_chain', className="btn"),
        ], className="field"),

    ], id='basic-cfg-container'),
    ]

    daq_config_card = html.Div(daq_config_card_list, className="card")
    #-----------------------------
    #       DAQ Status Card
    #-----------------------------
    daq_status_card = \
    html.Div([
        html.H2("DAQ Subsystem Status", id="init_title_s"),
        html.Div([html.Div("Update Rate:"              , id="label_daq_update_rate"   , className="field-label"), html.Div("- ms"        , id="body_daq_update_rate"   , className="field-body")], className="field"),
        html.Div([html.Div("Latency:"                  , id="label_daq_dsp_latency"   , className="field-label"), html.Div("- ms"        , id="body_daq_dsp_latency"   , className="field-body")], className="field"),
        html.Div([html.Div("Frame Index:"              , id="label_daq_frame_index"   , className="field-label"), html.Div("-"           , id="body_daq_frame_index"   , className="field-body")], className="field"),
        html.Div([html.Div("Frame Type:"               , id="label_daq_frame_type"    , className="field-label"), html.Div("-"           , id="body_daq_frame_type"    , className="field-body")], className="field"),
        html.Div([html.Div("Frame Sync:"               , id="label_daq_frame_sync"    , className="field-label"), html.Div("LOSS"        , id="body_daq_frame_sync"    , className="field-body", style={"color": "#e74c3c"})], className="field"),
        html.Div([html.Div("Power Level:"              , id="label_daq_power_level"   , className="field-label"), html.Div("-"           , id="body_daq_power_level"   , className="field-body")], className="field"),
        html.Div([html.Div("Connection Status:"        , id="label_daq_conn_status"   , className="field-label"), html.Div("Disconnected", id="body_daq_conn_status"   , className="field-body", style={"color": "#e74c3c"})], className="field"),
        html.Div([html.Div("Sample Delay Sync:"        , id="label_daq_delay_sync"    , className="field-label"), html.Div("LOSS"        , id="body_daq_delay_sync"    , className="field-body", style={"color": "#e74c3c"})], className="field"),
        html.Div([html.Div("IQ Sync:"                  , id="label_daq_iq_sync"       , className="field-label"), html.Div("LOSS"        , id="body_daq_iq_sync"       , className="field-body", style={"color": "#e74c3c"})], className="field"),
        html.Div([html.Div("Noise Source State:"       , id="label_daq_noise_source"  , className="field-label"), html.Div("Disabled"    , id="body_daq_noise_source"  , className="field-body", style={"color": "#7ccc63"})], className="field"),
        html.Div([html.Div("Center Frequecy [MHz]:"    , id="label_daq_rf_center_freq", className="field-label"), html.Div("- MHz"       , id="body_daq_rf_center_freq", className="field-body")], className="field"),
        html.Div([html.Div("Sampling Frequency [MHz]:" , id="label_daq_sampling_freq" , className="field-label"), html.Div("- MHz"       , id="body_daq_sampling_freq" , className="field-body")], className="field"),
        html.Div([html.Div("DSP Decimated BW [MHz]:"   , id="label_dsp_decimated_bw"  , className="field-label"), html.Div("- MHz"       , id="body_dsp_decimated_bw"  , className="field-body")], className="field"),
        html.Div([html.Div("VFO Range [MHz]:"          , id="label_vfo_range"         , className="field-label"), html.Div("- MHz"       , id="body_vfo_range"         , className="field-body")], className="field"),
        html.Div([html.Div("Data Block Length [ms]:"   , id="label_daq_cpi"           , className="field-label"), html.Div("- ms"        , id="body_daq_cpi"           , className="field-body")], className="field"),
        html.Div([html.Div("RF Gains [dB]:"            , id="label_daq_if_gain"       , className="field-label"), html.Div("[,] dB"      , id="body_daq_if_gain"       , className="field-body")], className="field"),
        html.Div([html.Div("VFO-0 Power [dB]:"         , id="label_max_amp"           , className="field-label"), html.Div("-"           , id="body_max_amp"           , className="field-body")], className="field"),
    ], className="card")

    #-----------------------------
    #    DSP Confugartion Card
    #-----------------------------

    dsp_config_card = \
    html.Div([
        html.H2("DoA Configuration", id="init_title_d"),
        html.Div([html.Span("Array Configuration: "             , id="label_ant_arrangement"   , className="field-label"),
        dcc.RadioItems(
            options=[
                {'label': "ULA", 'value': "ULA"},
                {'label': "UCA", 'value': "UCA"},
                {'label': "Custom", 'value': "Custom"},
            ], value=webInterface_inst.module_signal_processor.DOA_ant_alignment, className="field-body", labelStyle={'display': 'inline-block', 'vertical-align': 'middle'}, id="radio_ant_arrangement")
        ], className="field"),

        html.Div([
                html.Div("Custom X [m]:", className="field-label"),
                dcc.Input(id='custom_array_x_meters', value=','.join(['%.2f' % num for num in webInterface_inst.custom_array_x_meters]), type='text', debounce=True, className="field-body-textbox")
        ], id="customx", className="field"),

        html.Div([
                html.Div("Custom Y [m]:", className="field-label"),
                dcc.Input(id='custom_array_y_meters', value=','.join(['%.2f' % num for num in webInterface_inst.custom_array_y_meters]), type='text', debounce=True, className="field-body-textbox")
        ], id="customy", className="field"),

        html.Div([
        html.Div([html.Div("[meter]:"             , id="label_ant_spacing_meter"  , className="field-label"),
                    dcc.Input(id="ant_spacing_meter", value=ant_spacing_meter, type='number', debounce=True, className="field-body-textbox")]),
        html.Div([html.Div("Wavelength Multiplier:"         , id="label_ant_spacing_wavelength"        , className="field-label"), html.Div("1"      , id="body_ant_spacing_wavelength"        , className="field-body")], className="field"),
        ], id="antspacing", className="field"),

        html.Div([html.Div("", id="ambiguity_warning" , className="field", style={"color":"#f39c12"})]),

        # --> DoA estimation configuration checkboxes <--

        # Note: Individual checkboxes are created due to layout considerations, correct if extist a better solution
        html.Div([html.Div("Enable DoA Estimation:", id="label_en_doa"     , className="field-label"),
                dcc.Checklist(options=option     , id="en_doa_check"     , className="field-body", value=en_doa_values),
        ], className="field"),

        html.Div([html.Div("DoA Algorithm:", id="label_doa_method"     , className="field-label"),
        dcc.Dropdown(id='doa_method',
            options=[
                {'label': 'Bartlett', 'value': 'Bartlett'},
                {'label': 'Capon'   , 'value': 'Capon'},
                {'label': 'MEM'     , 'value': 'MEM'},
                {'label': 'MUSIC'   , 'value': 'MUSIC'}
                ],
        value=webInterface_inst._doa_method, style={"display":"inline-block"},className="field-body")
        ], className="field"),

        html.Div([html.Div("Enable F-B Averaging:", id="label_en_fb_avg"   , className="field-label"),
                dcc.Checklist(options=option     , id="en_fb_avg_check"   , className="field-body", value=en_fb_avg_values),
        ], className="field"),

        html.Div([html.Div("ULA Output Direction:", id="label_ula_direction"     , className="field-label"),
        dcc.Dropdown(id='ula_direction',
            options=[
                {'label': 'Both', 'value': 'Both'},
                {'label': 'Forward'   , 'value': 'Forward'},
                {'label': 'Backward'     , 'value': 'Backward'}
                ],
        value=webInterface_inst.module_signal_processor.ula_direction, style={"display":"inline-block"},className="field-body")
        ], className="field"),


    ], className="card")

    #-----------------------------
    #    Display Options Card
    #-----------------------------
    display_options_card = \
    html.Div([
        html.H2("Display Options", id="init_title_disp"),

        html.Div([
        html.Div("DoA Graph Type:", id="label_doa_graph_type", className="field-label"),
        dcc.Dropdown(id='doa_fig_type',
                options=[
                    {'label': 'Linear', 'value': 'Linear'},
                    {'label': 'Polar' ,  'value': 'Polar'},
                    {'label': 'Compass'    ,  'value': 'Compass'},
                    ],
            value=webInterface_inst._doa_fig_type, style={"display":"inline-block"},className="field-body"),
        ], className="field"),

        html.Div([
        html.Div("Compass Offset [deg]:", className="field-label"),
        dcc.Input(id="compass_ofset", value=webInterface_inst.compass_ofset, type='number', debounce=True, className="field-body-textbox"),
        ], className="field"),

    ], className="card")

    #--------------------------------
    # Misc station config parameters
    #--------------------------------
    station_config_card = \
        html.Div([
            html.H2("Station Information", id="station_conf_title"),
            html.Div([
                html.Div("Station ID:", id="station_id_label", className="field-label"),
                dcc.Input(id='station_id_input',
                          value=webInterface_inst.module_signal_processor.station_id,
                          type='text', className="field-body-textbox")
            ], className="field"),
            html.Div([
                html.Div("DOA Data Format:", id="doa_format_label", className="field-label"),
                dcc.Dropdown(id='doa_format_type',
                             options=[
                                 {'label': 'Kraken App', 'value': 'Kraken App'},
                                 {'label': 'Kraken Pro Local', 'value': 'Kraken Pro Local'},
                                 {'label': 'Kraken Pro Remote', 'value': 'Kraken Pro Remote'},
                                 {'label': 'Kerberos App', 'value': 'Kerberos App'},
                                 {'label': 'DF Aggregator', 'value': 'DF Aggregator'},
                                 {'label': 'JSON', 'value': 'JSON', 'disabled': True},
                             ],
                             value=webInterface_inst.module_signal_processor.DOA_data_format,
                             style={"display": "inline-block"}, className="field-body"),
            ], className="field"),
            html.Div([
                html.Div("Kraken Pro Key:", className="field-label"),
                dcc.Input(id='krakenpro_key',
                          value=webInterface_inst.module_signal_processor.krakenpro_key,
                          type='text', className="field-body-textbox", debounce=True)
            ], id="krakenpro_field", className="field"),
            html.Div([
                html.Div("Location Source:", id="location_src_label", className="field-label"),
                dcc.Dropdown(id='loc_src_dropdown',
                             options=[
                                 {'label': 'None', 'value': 'None'},
                                 {'label': 'Static', 'value': 'Static'},
                                 {'label': 'GPS', 'value': 'gpsd',
                                  'disabled': not webInterface_inst.module_signal_processor.hasgps},
                             ],
                             value=webInterface_inst.location_source, style={"display": "inline-block"}, className="field-body"),
            ], className="field"),
            html.Div([
                html.Div("Fixed Heading", id="fixed_heading_label", className="field-label"),
                dcc.Checklist(options=option, id="fixed_heading_check",
                              className="field-body",
                              value=en_fixed_heading),
                # html.Div("Fixed Heading:", className="field-label"),
                # daq.BooleanSwitch(id="fixed_heading_check",
                #                   on=webInterface_inst.module_signal_processor.fixed_heading,
                #                   label="Use Fixed Heading",
                #                   labelPosition="right"),
            ], className="field", id="fixed_heading_div"),
            html.Div([
                html.Div([
                    html.Div("Latitude:", className="field-label"),
                    dcc.Input(id='latitude_input',
                              value=webInterface_inst.module_signal_processor.latitude,
                              type='number', className="field-body-textbox")
                ], id="latitude_field", className="field"),
                html.Div([
                    html.Div("Longitude:", className="field-label"),
                    dcc.Input(id='longitude_input',
                              value=webInterface_inst.module_signal_processor.longitude,
                              type='number', className="field-body-textbox")
                ], id="logitude_field", className="field"),
            ], id="location_fields"),
            html.Div([
                html.Div("Heading:", className="field-label"),
                dcc.Input(id='heading_input',
                          value=webInterface_inst.module_signal_processor.heading,
                          type='number', className="field-body-textbox")
            ], id="heading_field", className="field"),
            html.Div([
                html.Div([
                    html.Div("GPS:", className="field-label"),
                    html.Div("-", id="gps_status", className="field-body")
                ], id="gps_status_field", className="field"),
                html.Div([
                    html.Div("Latitude:", id="label_gps_latitude", className="field-label"),
                    html.Div("-", id="body_gps_latitude", className="field-body")
                ], className="field"),
                html.Div([
                    html.Div("Longitude:", id="label_gps_longitude", className="field-label"),
                    html.Div("-", id="body_gps_longitude", className="field-body")
                ], className="field"),
                html.Div([
                    html.Div("Heading:", id="label_gps_heading", className="field-label"),
                    html.Div("-", id="body_gps_heading", className="field-body")
                ], className="field"),
            ], id="gps_status_info")
        ], className="card")



    #-----------------------------
    #  VFO Configuration Card
    #-----------------------------
    vfo_config_card = \
    html.Div([
        html.H2("VFO Configuration", id="init_title_sq"),

        html.Div([
        html.Div("Spectrum Calculation:", id="label_spectrum_calculation", className="field-label"),
        dcc.Dropdown(id='spectrum_fig_type',
                options=[
                    {'label': 'Single Ch', 'value': 'Single'},
                    {'label': 'All Ch (TEST ONLY)' ,  'value': 'All'},
                    ],
            value=webInterface_inst.module_signal_processor.spectrum_fig_type, style={"display":"inline-block"},className="field-body"),
        ], className="field"),

        html.Div([
        html.Div("VFO Mode:", id="label_vfo_mode", className="field-label"),
        dcc.Dropdown(id='vfo_mode',
                options=[
                    {'label': 'Standard', 'value': 'Standard'},
                    {'label': 'VFO-0 Auto Max' ,  'value': 'Auto'},
                    ],
            value=webInterface_inst.module_signal_processor.vfo_mode, style={"display":"inline-block"},className="field-body"),
        ], className="field"),

        html.Div([
        html.Div("Active VFOs:", id="label_active_vfos", className="field-label"),
        dcc.Dropdown(id='active_vfos',
                options=[
                    {'label': '1', 'value': 1},
                    {'label': '2', 'value': 2},
                    {'label': '3', 'value': 3},
                    {'label': '4', 'value': 4},
                    {'label': '5', 'value': 5},
                    {'label': '6', 'value': 6},
                    {'label': '7', 'value': 7},
                    {'label': '8', 'value': 8},
                    {'label': '9', 'value': 9},
                    {'label': '10', 'value': 10},
                    {'label': '11', 'value': 11},
                    {'label': '12', 'value': 12},
                    {'label': '13', 'value': 13},
                    {'label': '14', 'value': 14},
                    {'label': '15', 'value': 15},
                    {'label': '16', 'value': 16},
                    ],
            value=webInterface_inst.module_signal_processor.active_vfos, style={"display":"inline-block"},className="field-body"),
        ], className="field"),

        html.Div([
        html.Div("Output VFO:", id="label_output_vfo", className="field-label"),
        dcc.Dropdown(id='output_vfo',
                options=[
                    {'label': 'ALL', 'value': -1},
                    {'label': '0', 'value': 0},
                    {'label': '1', 'value': 1},
                    {'label': '2', 'value': 2},
                    {'label': '3', 'value': 3},
                    {'label': '4', 'value': 4},
                    {'label': '5', 'value': 5},
                    {'label': '6', 'value': 6},
                    {'label': '7', 'value': 7},
                    {'label': '8', 'value': 8},
                    {'label': '9', 'value': 9},
                    {'label': '10', 'value': 10},
                    {'label': '11', 'value': 11},
                    {'label': '12', 'value': 12},
                    {'label': '13', 'value': 13},
                    {'label': '14', 'value': 14},
                    {'label': '15', 'value': 15},
                    ],
            value=webInterface_inst.module_signal_processor.output_vfo, style={"display":"inline-block"},className="field-body"),
        ], className="field"),

        html.Div([
                html.Div("DSP Side Decimation:", id="label_dsp_side_decimation", className="field-label"),
                dcc.Input(id='dsp_decimation', value=webInterface_inst.module_signal_processor.dsp_decimation, type='number', debounce=True, className="field-body-textbox")
            ], className="field"),

        html.Div([
                html.Div("Optimize Short Bursts:", id="label_optimize_short_bursts", className="field-label"),
                dcc.Checklist(options=option     , id="en_optimize_short_bursts"   , className="field-body", value=en_optimize_short_bursts),
            ], className="field"),



    ], className="card")

    #-----------------------------
    #  Individual VFO Configurations
    #-----------------------------
    vfo_card = [" "] * webInterface_inst.module_signal_processor.max_vfos

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        vfo_card[i] = \
        html.Div([
            html.Div([
                    html.Div("VFO-" + str(i) + " Frequency [MHz]:", className="field-label"),
                    dcc.Input(id='vfo_' + str(i) + '_freq', value=webInterface_inst.module_signal_processor.vfo_freq[i] / 10**6, type='number', debounce=True, className="field-body-textbox")
                ], className="field"),

            html.Div([
                    html.Div("VFO-" + str(i) + " Bandwidth [Hz]:", className="field-label"),
                    dcc.Input(id='vfo_' + str(i) + '_bw', value=webInterface_inst.module_signal_processor.vfo_bw[i], type='number', debounce=True, className="field-body-textbox")
                ], className="field"),

            html.Div([
                    html.Div("VFO-" + str(i) + " Squelch [dB] :", className="field-label"),
                    dcc.Input(id='vfo_' +str(i) + '_squelch', value=webInterface_inst.module_signal_processor.vfo_squelch[i], type='number', debounce=True, className="field-body-textbox")
                ], className="field"),
        ], id="vfo"+str(i), className="card", style = {'display': 'block'} if i < webInterface_inst.module_signal_processor.active_vfos else {'display': 'none'} )

    config_page_component_list = [start_stop_card, daq_status_card, daq_config_card, vfo_config_card, dsp_config_card, display_options_card, station_config_card]

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        config_page_component_list.append(vfo_card[i])

    if not webInterface_inst.disable_tooltips:
        config_page_component_list.append(tooltips.dsp_config_tooltips)
        config_page_component_list.append(tooltips.daq_ini_config_tooltips)
        config_page_component_list.append(tooltips.station_parameters_tooltips)

    return html.Div(children=config_page_component_list)

spectrum_page_layout = html.Div([
    html.Div([
    dcc.Graph(
        id="spectrum-graph",
        style={'width': '100%', 'height': '45%'},
        figure=spectrum_fig #fig_dummy #spectrum_fig #fig_dummy
    ),
    dcc.Graph(
        id="waterfall-graph",
        style={'width': '100%', 'height': '65%'},
        figure=waterfall_fig #waterfall fig remains unchanged always due to slow speed to update entire graph #fig_dummy #spectrum_fig #fig_dummy
    ),
], style={'width': '100%', 'height': '80vh'}),
])

def generate_doa_page_layout(webInterface_inst):
    doa_page_layout = html.Div([
        html.Div([html.Div("MAX DOA Angle:",
                 id="label_doa_max",
                 className="field-label"),
                 html.Div("deg",
                 id="body_doa_max",
                 className="field-body")],
                 className="field"),

        #html.Div([
        dcc.Graph(
            style={"height": "inherit"},
            id="doa-graph",
            figure=doa_fig, #fig_dummy #doa_fig #fig_dummy
        ),
    ], style={'width': '100%', 'height': '80vh'})
    return doa_page_layout

#============================================
#          CALLBACK FUNCTIONS
#============================================
@app.callback_connect
def func(client, connect):
    if connect and len(app.clients)==1:
        fetch_dsp_data()
        fetch_gps_data()
        settings_change_watcher()
    elif not connect and len(app.clients)==0:
        webInterface_inst.dsp_timer.cancel()

def fetch_dsp_data():
    daq_status_update_flag = 0
    spectrum_update_flag   = 0
    doa_update_flag        = 0
    freq_update            = 0 #no_update
    #############################################
    #      Fetch new data from back-end ques    #
    #############################################
    try:
        # Fetch new data from the receiver module
        que_data_packet = webInterface_inst.rx_data_que.get(False)
        for data_entry in que_data_packet:
            if data_entry[0] == "conn-ok":
                webInterface_inst.daq_conn_status = 1
                daq_status_update_flag = 1
            elif data_entry[0] == "disconn-ok":
                webInterface_inst.daq_conn_status = 0
                daq_status_update_flag = 1
            elif data_entry[0] == "config-ok":
                webInterface_inst.daq_cfg_iface_status = 0
                daq_status_update_flag = 1
    except queue.Empty:
        # Handle empty queue here
        webInterface_inst.logger.debug("Receiver module que is empty")
    else:
        pass
        # Handle task here and call q.task_done()
    if webInterface_inst.daq_restart: # Set by the restarting script
        daq_status_update_flag = 1
    try:
        # Fetch new data from the signal processing module
        que_data_packet  = webInterface_inst.sp_data_que.get(False)
        for data_entry in que_data_packet:
            if data_entry[0] == "iq_header":
                webInterface_inst.logger.debug("Iq header data fetched from signal processing que")
                iq_header = data_entry[1]
                # Unpack header
                webInterface_inst.daq_frame_index = iq_header.cpi_index
                if iq_header.frame_type == iq_header.FRAME_TYPE_DATA:
                    webInterface_inst.daq_frame_type  = "Data"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_DUMMY:
                    webInterface_inst.daq_frame_type  = "Dummy"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_CAL:
                    webInterface_inst.daq_frame_type  = "Calibration"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_TRIGW:
                    webInterface_inst.daq_frame_type  = "Trigger wait"
                else:
                    webInterface_inst.daq_frame_type  = "Unknown"

                webInterface_inst.daq_frame_sync        = iq_header.check_sync_word()
                webInterface_inst.daq_power_level       = iq_header.adc_overdrive_flags
                webInterface_inst.daq_sample_delay_sync = iq_header.delay_sync_flag
                webInterface_inst.daq_iq_sync           = iq_header.iq_sync_flag
                webInterface_inst.daq_noise_source_state= iq_header.noise_source_state

                if webInterface_inst.daq_center_freq != iq_header.rf_center_freq/10**6:
                    freq_update = 1

                webInterface_inst.daq_center_freq       = iq_header.rf_center_freq/10**6
                webInterface_inst.daq_adc_fs            = iq_header.adc_sampling_freq/10**6
                webInterface_inst.daq_fs                = iq_header.sampling_freq/10**6
                webInterface_inst.daq_cpi               = int(iq_header.cpi_length*10**3/iq_header.sampling_freq)
                gain_list_str=""

                for m in range(iq_header.active_ant_chs):
                    gain_list_str+=str(iq_header.if_gains[m]/10)
                    gain_list_str+=", "

                webInterface_inst.daq_if_gains          =gain_list_str[:-2]
                daq_status_update_flag = 1
            elif data_entry[0] == "update_rate":
                webInterface_inst.daq_update_rate = data_entry[1]
            elif data_entry[0] == "latency":
                webInterface_inst.daq_dsp_latency = data_entry[1] + webInterface_inst.daq_cpi
            elif data_entry[0] == "max_amplitude":
                webInterface_inst.max_amplitude = data_entry[1]
            elif data_entry[0] == "avg_powers":
                avg_powers_str = ""
                for avg_power in data_entry[1]:
                    avg_powers_str+="{:.1f}".format(avg_power)
                    avg_powers_str+=", "
                webInterface_inst.avg_powers = avg_powers_str[:-2]
            elif data_entry[0] == "spectrum":
                webInterface_inst.logger.debug("Spectrum data fetched from signal processing que")
                spectrum_update_flag = 1
                webInterface_inst.spectrum = data_entry[1]
            elif data_entry[0] == "doa_thetas":
                webInterface_inst.doa_thetas= data_entry[1]
                doa_update_flag                   = 1
                webInterface_inst.doa_results     = []
                webInterface_inst.doa_labels      = []
                webInterface_inst.doas            = []
                webInterface_inst.max_doas_list   = []
                webInterface_inst.doa_confidences = []
                webInterface_inst.logger.debug("DoA estimation data fetched from signal processing que")
            elif data_entry[0] == "DoA Result":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "DoA Max":
                webInterface_inst.doas.append(data_entry[1])
            elif data_entry[0] == "DoA Confidence":
                webInterface_inst.doa_confidences.append(data_entry[1])
            elif data_entry[0] == "DoA Max List":
                webInterface_inst.max_doas_list = data_entry[1].copy()
            elif data_entry[0] == "DoA Squelch":
                webInterface_inst.squelch_update = data_entry[1].copy()
            else:
                webInterface_inst.logger.warning("Unknown data entry: {:s}".format(data_entry[0]))
    except queue.Empty:
        # Handle empty queue here
        webInterface_inst.logger.debug("Signal processing que is empty")
    else:
        pass
        # Handle task here and call q.task_done()

    if (webInterface_inst.pathname == "/config" or webInterface_inst.pathname == "/" or webInterface_inst.pathname == "/init") and daq_status_update_flag:
        update_daq_status()
    elif webInterface_inst.pathname == "/spectrum" and spectrum_update_flag:
        plot_spectrum()
    elif (webInterface_inst.pathname == "/doa" and doa_update_flag): #or (webInterface_inst.pathname == "/doa" and webInterface_inst.reset_doa_graph_flag):
        plot_doa()

    webInterface_inst.dsp_timer = Timer(.01, fetch_dsp_data)
    webInterface_inst.dsp_timer.start()

def settings_change_watcher():
    last_changed_time = os.stat(settings_file_path).st_mtime
    time_delta = last_changed_time-webInterface_inst.last_changed_time_previous

    # Load settings file
    if(time_delta > 0): # If > 0, file was changed
        global dsp_settings
        if os.path.exists(settings_file_path):
            with open(settings_file_path, 'r') as myfile:
                dsp_settings = json.loads(myfile.read()) # update global dsp_settings, to ensureother functions using it get the most up to date values??

        center_freq = dsp_settings.get("center_freq", 100.0)
        gain = dsp_settings.get("uniform_gain", 1.4)

        DOA_ant_alignment = dsp_settings.get("ant_arrangement")
        webInterface_inst.ant_spacing_meters = float(dsp_settings.get("ant_spacing_meters", 0.5))

        webInterface_inst.module_signal_processor.en_DOA_estimation    = dsp_settings.get("en_doa", 0)
        webInterface_inst.module_signal_processor.en_DOA_FB_avg        = dsp_settings.get("en_fbavg", 0)

        # Create a function called load conf file, where we load the json config into global variables, and use that in the main init too
        # WE NEED to put the DOA_ant_alignment text changer and ant_spacing_wavelength etc code into functions, since their used in multiple places in the code
        webInterface_inst.module_signal_processor.DOA_ant_alignment = dsp_settings.get("ant_arrangement", "ULA")
        webInterface_inst.ant_spacing_meters = float(dsp_settings.get("ant_spacing_meters", 0.5))

        webInterface_inst.custom_array_x_meters = np.float_(dsp_settings.get("custom_array_x_meters", "0.1,0.2,0.3,0.4,0.5").split(","))
        webInterface_inst.custom_array_y_meters = np.float_(dsp_settings.get("custom_array_y_meters", "0.1,0.2,0.3,0.4,0.5").split(","))
        webInterface_inst.module_signal_processor.custom_array_x = webInterface_inst.custom_array_x_meters / (300 / webInterface_inst.module_receiver.daq_center_freq)
        webInterface_inst.module_signal_processor.custom_array_y = webInterface_inst.custom_array_y_meters / (300 / webInterface_inst.module_receiver.daq_center_freq)

        # Station Information
        webInterface_inst.module_signal_processor.station_id    = dsp_settings.get("station_id", "NO-CALL")
        webInterface_inst.location_source                       = dsp_settings.get("location_source", "None")
        webInterface_inst.module_signal_processor.latitude      = dsp_settings.get("latitude", 0.0)
        webInterface_inst.module_signal_processor.longitude     = dsp_settings.get("longitude", 0.0)
        webInterface_inst.module_signal_processor.heading       = dsp_settings.get("heading", 0.0)
        webInterface_inst.module_signal_processor.krakenpro_key = dsp_settings.get("krakenpro_key", 0.0)

        # VFO Configuration
        webInterface_inst.module_signal_processor.spectrum_fig_type = dsp_settings.get("spectrum_calculation", "Single")
        webInterface_inst.module_signal_processor.vfo_mode = dsp_settings.get("vfo_mode", 'Standard')
        webInterface_inst.module_signal_processor.dsp_decimation = int(dsp_settings.get("dsp_decimation", 0))
        webInterface_inst.module_signal_processor.active_vfos = int(dsp_settings.get("active_vfos", 0))
        webInterface_inst.module_signal_processor.output_vfo = int(dsp_settings.get("output_vfo", 0))
        webInterface_inst.compass_ofset = dsp_settings.get("compass_offset", 0)
        webInterface_inst.module_signal_processor.optimize_short_bursts = dsp_settings.get("en_optimize_short_bursts", 0)

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            webInterface_inst.module_signal_processor.vfo_bw[i] = int(dsp_settings.get("vfo_bw_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_freq[i] = float(dsp_settings.get("vfo_freq_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_squelch[i] = int(dsp_settings.get("vfo_squelch_" + str(i), 0))


        webInterface_inst._doa_method = dsp_settings.get("doa_method", "MUSIC")
        webInterface_inst._doa_fig_type = dsp_settings.get("doa_fig_type", "Linear")
        webInterface_inst.module_signal_processor.ula_direction = dsp_settings.get("ula_direction", "Both")
        webInterface_inst.config_doa_in_signal_processor()

        freq_delta = webInterface_inst.daq_center_freq - center_freq
        gain_delta = webInterface_inst.module_receiver.daq_rx_gain - gain

        if(abs(freq_delta) > 0.001 or abs(gain_delta) > 0.001):
            webInterface_inst.daq_center_freq = center_freq
            webInterface_inst.config_daq_rf(center_freq, gain)

        webInterface_inst.needs_refresh = True

    webInterface_inst.last_changed_time_previous = last_changed_time

    webInterface_inst.settings_change_timer  = Timer(1, settings_change_watcher)
    webInterface_inst.settings_change_timer.start()



def fetch_gps_data():
    app.push_mods({
        'body_gps_latitude': {'children': webInterface_inst.module_signal_processor.latitude},
        'body_gps_longitude': {'children': webInterface_inst.module_signal_processor.longitude},
        'body_gps_heading': {'children': webInterface_inst.module_signal_processor.heading}
    })

    webInterface_inst.gps_timer = Timer(1, fetch_gps_data)
    webInterface_inst.gps_timer.start()

def update_daq_status():

    #############################################
    #      Prepare UI component properties      #
    #############################################

    if webInterface_inst.daq_conn_status == 1:

        if not webInterface_inst.daq_cfg_iface_status:
            daq_conn_status_str = "Connected"
            conn_status_style={"color": "#7ccc63"}
        else: # Config interface is busy
            daq_conn_status_str = "Reconfiguration.."
            conn_status_style={"color": "#f39c12"}
    else:
        daq_conn_status_str = "Disconnected"
        conn_status_style={"color": "#e74c3c"}

    if webInterface_inst.daq_restart:
        daq_conn_status_str = "Restarting.."
        conn_status_style={"color": "#f39c12"}

    if webInterface_inst.daq_update_rate < 1:
        daq_update_rate_str    = "{:d} ms".format(round(webInterface_inst.daq_update_rate*1000))
    else:
        daq_update_rate_str    = "{:.2f} s".format(webInterface_inst.daq_update_rate)

    daq_dsp_latency        = "{:d} ms".format(webInterface_inst.daq_dsp_latency)
    daq_frame_index_str    = str(webInterface_inst.daq_frame_index)

    daq_frame_type_str =  webInterface_inst.daq_frame_type
    if webInterface_inst.daq_frame_type == "Data":
        frame_type_style   = frame_type_style={"color": "#7ccc63"}
    elif webInterface_inst.daq_frame_type == "Dummy":
        frame_type_style   = frame_type_style={"color": "white"}
    elif webInterface_inst.daq_frame_type == "Calibration":
        frame_type_style   = frame_type_style={"color": "#f39c12"}
    elif webInterface_inst.daq_frame_type == "Trigger wait":
        frame_type_style   = frame_type_style={"color": "#f39c12"}
    else:
        frame_type_style   = frame_type_style={"color": "#e74c3c"}

    if webInterface_inst.daq_frame_sync:
        daq_frame_sync_str = "LOSS"
        frame_sync_style={"color": "#e74c3c"}
    else:
        daq_frame_sync_str = "Ok"
        frame_sync_style={"color": "#7ccc63"}
    if webInterface_inst.daq_sample_delay_sync:
        daq_delay_sync_str     = "Ok"
        delay_sync_style={"color": "#7ccc63"}
    else:
        daq_delay_sync_str     = "LOSS"
        delay_sync_style={"color": "#e74c3c"}

    if webInterface_inst.daq_iq_sync:
        daq_iq_sync_str        = "Ok"
        iq_sync_style={"color": "#7ccc63"}
    else:
        daq_iq_sync_str        = "LOSS"
        iq_sync_style={"color": "#e74c3c"}

    if webInterface_inst.daq_noise_source_state:
        daq_noise_source_str   = "Enabled"
        noise_source_style={"color": "#e74c3c"}
    else:
        daq_noise_source_str   = "Disabled"
        noise_source_style={"color": "#7ccc63"}

    if webInterface_inst.daq_power_level:
        daq_power_level_str = "Overdrive"
        daq_power_level_style={"color": "#e74c3c"}
    else:
        daq_power_level_str = "OK"
        daq_power_level_style={"color": "#7ccc63"}

    daq_rf_center_freq_str = str(webInterface_inst.daq_center_freq)
    daq_sampling_freq_str  = str(webInterface_inst.daq_fs)
    bw = webInterface_inst.daq_fs / webInterface_inst.module_signal_processor.dsp_decimation
    dsp_decimated_bw_str = '{0:.3f}'.format(bw)
    vfo_range_str          = '{0:.3f}'.format(webInterface_inst.daq_center_freq - bw/2) + " - " + '{0:.3f}'.format(webInterface_inst.daq_center_freq + bw/2)
    daq_cpi_str            = str(webInterface_inst.daq_cpi)
    daq_max_amp_str        = "{:.1f}".format(webInterface_inst.max_amplitude)
    daq_avg_powers_str     = webInterface_inst.avg_powers


    app.push_mods({
           'body_daq_update_rate': {'children': daq_update_rate_str},
           'body_daq_dsp_latency': {'children': daq_dsp_latency},
           'body_daq_frame_index': {'children': daq_frame_index_str},
           'body_daq_frame_sync': {'children': daq_frame_sync_str},
           'body_daq_frame_type': {'children': daq_frame_type_str},
           'body_daq_power_level': {'children': daq_power_level_str},
           'body_daq_conn_status': {'children': daq_conn_status_str },
           'body_daq_delay_sync': {'children': daq_delay_sync_str},
           'body_daq_iq_sync': {'children': daq_iq_sync_str},
           'body_daq_noise_source': {'children': daq_noise_source_str},
           'body_daq_rf_center_freq': {'children': daq_rf_center_freq_str},
           'body_daq_sampling_freq': {'children': daq_sampling_freq_str},
           'body_dsp_decimated_bw': {'children': dsp_decimated_bw_str},
           'body_vfo_range': {'children': vfo_range_str},
           'body_daq_cpi': {'children': daq_cpi_str},
           'body_daq_if_gain': {'children': webInterface_inst.daq_if_gains},
           'body_max_amp': {'children': daq_max_amp_str},
           'body_avg_powers': {'children': daq_avg_powers_str}
    })

    app.push_mods({
           'body_daq_frame_sync': {'style': frame_sync_style},
           'body_daq_frame_type': {'style': frame_type_style},
           'body_daq_power_level': {'style': daq_power_level_style},
           'body_daq_conn_status': {'style': conn_status_style},
           'body_daq_delay_sync': {'style': delay_sync_style},
           'body_daq_iq_sync': {'style': iq_sync_style},
           'body_daq_noise_source': {'style': noise_source_style},
    })


@app.callback_shared(
    #Output(component_id="placeholder_update_freq", component_property="children"),
    #None,
#    Output(component_id="body_ant_spacing_wavelength",  component_property='children'),
    None,
    [Input(component_id ="btn-update_rx_param"   , component_property="n_clicks")],
    [State(component_id ="daq_center_freq"       , component_property='value'),
    State(component_id ="daq_rx_gain"           , component_property='value')],
)
def update_daq_params(input_value, f0, gain):
    webInterface_inst.daq_center_freq = f0
    webInterface_inst.config_daq_rf(f0,gain)

    wavelength = 300 / webInterface_inst.daq_center_freq
    webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength
    ant_spacing_wavelength = round(webInterface_inst.ant_spacing_meters / wavelength, 3)
    app.push_mods({
           'body_ant_spacing_wavelength': {'children': str(ant_spacing_wavelength)},
    })

#    return str(ant_spacing_wavelength)

    #webInterface_inst.daq_center_freq
    #return '1'

# Set DOA Output Format
@app.callback_shared(None,
                     [Input(component_id="doa_format_type", component_property='value')])
def set_doa_format(doa_format):
    webInterface_inst.module_signal_processor.DOA_data_format = doa_format


# Update Station ID
@app.callback_shared(Output(component_id='station_header', component_property='children'),
                     [Input(component_id='station_id_input', component_property='value')])
def set_station_id(station_id):
    valid_id = re.sub('[^A-Za-z0-9\-]+', '-', station_id)
    webInterface_inst.module_signal_processor.station_id = valid_id
    return valid_id

@app.callback_shared(None,
                     [Input(component_id='krakenpro_key', component_property='value')])
def set_kraken_pro_key(key):
    webInterface_inst.module_signal_processor.krakenpro_key = key 


# Enable GPS Relevant fields
@app.callback([Output('fixed_heading_div', 'style'),
               Output('gps_status_info', 'style')],
              [Input('loc_src_dropdown', 'value')])
def toggle_gps_fields(toggle_value):
    if toggle_value == "gpsd":
        return [{'display': 'block'}, {'display': 'block'}]
    else:
        return [{'display': 'none'}, {'display': 'none'}]

# Enable of Disable Kraken Pro Key Box
@app.callback(Output('krakenpro_field', 'style'),
              [Input('doa_format_type', 'value')])
def toggle_kraken_pro_key(doa_format_type):
    if doa_format_type == "Kraken Pro Remote":
        return {'display': 'block'}
    else:
        return {'display': 'none'}



# Enable or Disable Heading Input Fields
@app.callback(Output('heading_field', 'style'),
              [Input('loc_src_dropdown', 'value'),
               Input(component_id='fixed_heading_check', component_property='value')])
def toggle_location_info(static_loc, fixed_heading):
    if static_loc == "Static":
        webInterface_inst.module_signal_processor.fixed_heading = True
        return {'display': 'block'}
    elif static_loc == "gpsd" and fixed_heading:
        return {'display': 'block'}
    elif static_loc == "None":
        webInterface_inst.module_signal_processor.fixed_heading = False
        return {'display': 'none'}
    else:
        return {'display': 'none'}


# Enable or Disable Location Input Fields
@app.callback(Output('location_fields', 'style'),
              [Input('loc_src_dropdown', 'value')])
def toggle_location_info(toggle_value):
    webInterface_inst.location_source = toggle_value
    if toggle_value == "Static":
        return {'display': 'block'}
    else:
        return {'display': 'none'}

# Set location data
@app.callback_shared(None,
                     [Input(component_id="latitude_input", component_property='value'),
                      Input(component_id="longitude_input", component_property='value')])
def set_static_location(lat, lon):
    webInterface_inst.module_signal_processor.latitude = lat
    webInterface_inst.module_signal_processor.longitude = lon


# Enable Fixed Heading
@app.callback(None,
              [Input(component_id='fixed_heading_check', component_property='value')])
def set_fixed_heading(fixed):
    if fixed:
        webInterface_inst.module_signal_processor.fixed_heading = True
    else:
        webInterface_inst.module_signal_processor.fixed_heading = False


# Set heading data
@app.callback_shared(None,
                     [Input(component_id="heading_input", component_property='value')])
def set_static_location(heading):
    webInterface_inst.module_signal_processor.heading = heading


# Enable GPS
@app.callback_shared([Output("gps_status", "children"),
                      Output("gps_status", "style")],
                     [Input('loc_src_dropdown', 'value')])
def enable_gps(toggle_value):
    if toggle_value == "gpsd":
        status = webInterface_inst.module_signal_processor.enable_gps()
        if status:
            return ["Enabled", {"color": "#7ccc63"}]
        else:
            return ["Error", {"color": "#e74c3c"}]
    else:
        return ["-", {"color": "white"}]

@app.callback_shared(
    None,
    webInterface_inst.vfo_cfg_inputs
)
def update_vfo_params(*args):

    # Get dict of input variables
    input_names = [item.component_id for item in webInterface_inst.vfo_cfg_inputs]
    kwargs_dict = dict(zip(input_names, args))

    webInterface_inst.module_signal_processor.spectrum_fig_type = kwargs_dict["spectrum_fig_type"]
    webInterface_inst.module_signal_processor.vfo_mode = kwargs_dict["vfo_mode"]

    active_vfos = kwargs_dict["active_vfos"]
    # If VFO mode is in the VFO-0 Auto Max mode, we active VFOs to 1 only
    if kwargs_dict["vfo_mode"] == 'Auto':
        active_vfos = 1
        app.push_mods({
            'active_vfos' : {'value': 1}
        })

    webInterface_inst.module_signal_processor.dsp_decimation = max(int(kwargs_dict["dsp_decimation"]), 1)
    webInterface_inst.module_signal_processor.active_vfos = active_vfos
    webInterface_inst.module_signal_processor.output_vfo = kwargs_dict["output_vfo"]

    en_optimize_short_bursts = kwargs_dict["en_optimize_short_bursts"]
    if en_optimize_short_bursts is not None and len(en_optimize_short_bursts):
        webInterface_inst.module_signal_processor.optimize_short_bursts   = True
    else:
        webInterface_inst.module_signal_processor.optimize_short_bursts   = False

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        if i < kwargs_dict["active_vfos"]:
            app.push_mods({
                'vfo'+str(i) : {'style': {'display': 'block'}}
            })
        else:
            app.push_mods({
                'vfo'+str(i) : {'style': {'display': 'none'}}
            })

    bw = webInterface_inst.daq_fs / webInterface_inst.module_signal_processor.dsp_decimation
    vfo_min = webInterface_inst.daq_center_freq - bw/2
    vfo_max = webInterface_inst.daq_center_freq + bw/2

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        webInterface_inst.module_signal_processor.vfo_bw[i] = int(min(kwargs_dict['vfo_'+str(i)+'_bw'], bw * 10**6))
        webInterface_inst.module_signal_processor.vfo_freq[i] = int(max(min(kwargs_dict['vfo_'+str(i)+'_freq'], vfo_max), vfo_min) * 10**6)
        webInterface_inst.module_signal_processor.vfo_squelch[i] = int(kwargs_dict['vfo_'+str(i)+'_squelch'])

@app.callback([Output("page-content"   , "children"),
              Output("header_config"  ,"className"),
              Output("header_spectrum","className"),
              Output("header_doa"     ,"className")],
              [Input("url"            , "pathname")],
)
def display_page(pathname):

    # CHECK CONTEXT, was this called by url or timer?

    #if self.needs_refresh:
    #    self.needs_refresh = False

    global spectrum_fig
    global doa_fig
    webInterface_inst.pathname = pathname

    if pathname == "/" or pathname == "/init":
        webInterface_inst.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(webInterface_inst), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/config":
        webInterface_inst.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(webInterface_inst), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/spectrum":
        webInterface_inst.module_signal_processor.en_spectrum = True
        webInterface_inst.reset_spectrum_graph_flag = True
        return [spectrum_page_layout, "header_inactive", "header_active", "header_inactive"]
    elif pathname == "/doa":
        webInterface_inst.module_signal_processor.en_spectrum = False
        webInterface_inst.reset_doa_graph_flag = True
        plot_doa()
        return [generate_doa_page_layout(webInterface_inst), "header_inactive", "header_inactive", "header_active"]
    return Output('dummy_output', 'children', '')

@app.callback_shared(
    None,
    [Input(component_id='btn-start_proc', component_property='n_clicks')],
)
def start_proc_btn(input_value):
    webInterface_inst.logger.info("Start pocessing btn pushed")
    webInterface_inst.start_processing()

@app.callback_shared(
    None,
    [Input(component_id='btn-stop_proc', component_property='n_clicks')],
)
def stop_proc_btn(input_value):
    webInterface_inst.logger.info("Stop pocessing btn pushed")
    webInterface_inst.stop_processing()

@app.callback_shared(
    None,
    [Input(component_id='btn-save_cfg'     , component_property='n_clicks')],
)
def save_config_btn(input_value):
    webInterface_inst.logger.info("Saving DAQ and DSP Configuration")
    webInterface_inst.save_configuration()

@app.callback_shared(
    None,
    [Input('spectrum-graph', 'clickData')]
)
def click_to_set_freq_spectrum(clickData):
    set_clicked(clickData)

@app.callback_shared(
    None,
    [Input('waterfall-graph', 'clickData')]
)
def click_to_set_waterfall_spectrum(clickData):
    set_clicked(clickData)

def set_clicked(clickData):
    M = webInterface_inst.module_receiver.M
    curveNumber = clickData["points"][0]["curveNumber"]

    if curveNumber >= M:
        vfo_idx = int((curveNumber - M) / 2)
        webInterface_inst.selected_vfo = vfo_idx
        if webInterface_inst.module_signal_processor.output_vfo >= 0:
            webInterface_inst.module_signal_processor.output_vfo = vfo_idx
    else:
        idx = 0
        if webInterface_inst.module_signal_processor.output_vfo >= 0:
            idx = max(webInterface_inst.module_signal_processor.output_vfo, 0)
        else:
            idx = webInterface_inst.selected_vfo
        webInterface_inst.module_signal_processor.vfo_freq[idx] = int(clickData["points"][0]["x"])


def plot_doa():
    global doa_fig

    if webInterface_inst.reset_doa_graph_flag == True:
        doa_fig.data = []
        #Just generate with junk data initially, as the spectrum array may not be ready yet if we have sqeulching active etc.
        if True: #webInterface_inst.doa_thetas is not None:
            # --- Linear plot ---
            if webInterface_inst._doa_fig_type == 'Linear':
                # Plot traces
                doa_fig.add_trace(go.Scattergl(x=x, #webInterface_inst.doa_thetas,
                                  y=y,
                            ))

                doa_fig.update_xaxes(title_text="Incident angle [deg]",
                            color='rgba(255,255,255,1)',
                            title_font_size=20,
                            tickfont_size=figure_font_size,
                            mirror=True,
                            ticks='outside',
                            showline=True)
                doa_fig.update_yaxes(title_text="Amplitude [dB]",
                            color='rgba(255,255,255,1)',
                            title_font_size=20,
                            tickfont_size=figure_font_size,
                            #range=[-5, 5],
                            mirror=True,
                            ticks='outside',
                            showline=True)
# --- Polar plot ---
            elif webInterface_inst._doa_fig_type == 'Polar':

                label = "DOA Angle" #webInterface_inst.doa_labels[i]
                doa_fig.add_trace(go.Scatterpolargl(theta=x, #webInterface_inst.doa_thetas,
                                             r=y, #doa_result,
                                             name=label,
                                             fill= 'toself'
                                             ))

                doa_fig.update_layout(polar = dict(radialaxis_tickfont_size = figure_font_size,
                                           angularaxis = dict(rotation=90,
                                                              tickfont_size = figure_font_size)
                                                             )
                                     )

            # --- Compass  ---
            elif webInterface_inst._doa_fig_type == 'Compass' :
                doa_fig.update_layout(polar = dict(radialaxis_tickfont_size = figure_font_size,
                                        angularaxis = dict(rotation=90+webInterface_inst.compass_ofset,
                                                            direction="clockwise",
                                                            tickfont_size = figure_font_size)
                                                          )
                                     )

                label = "DOA Angle"

                doa_fig.add_trace(go.Scatterpolargl(theta=x, #(360-webInterface_inst.doa_thetas+webInterface_inst.compass_ofset)%360,
                                                r=y, #doa_result,
                                                name= label,
                                               # line = dict(color = doa_trace_colors[webInterface_inst.doa_labels[i]]),
                                                fill= 'toself'
                                                ))

        webInterface_inst.reset_doa_graph_flag = False
    else:
        update_data = []
        fig_type = []
        doa_max_str = ""
        if webInterface_inst.doa_thetas is not None:
            doa_max_str = str(webInterface_inst.doas[0])+"°"
            update_data = dict(x=[webInterface_inst.doa_thetas], y=[webInterface_inst.doa_results[0]])

            if webInterface_inst._doa_fig_type == 'Polar' :
                update_data = dict(theta=[webInterface_inst.doa_thetas], r=[webInterface_inst.doa_results[0]])
            elif webInterface_inst._doa_fig_type == 'Compass' :
                doa_max_str = (360-webInterface_inst.doas[0]+webInterface_inst.compass_ofset)%360
                update_data = dict(theta=[(360-webInterface_inst.doa_thetas+webInterface_inst.compass_ofset)%360], r=[webInterface_inst.doa_results[0]])

            app.push_mods({
                'doa-graph': {'extendData': [update_data, [0], len(webInterface_inst.doa_thetas)]},
                'body_doa_max': {'children': doa_max_str}
            })

def plot_spectrum():
    global spectrum_fig
    global waterfall_fig
    #if spectrum_fig == None:
    if webInterface_inst.reset_spectrum_graph_flag:

        x=webInterface_inst.spectrum[0,:] + webInterface_inst.daq_center_freq*10**6

        # Plot traces
        for m in range(np.size(webInterface_inst.spectrum, 0)-1):
            spectrum_fig.data[m]['x'] = x

        # Hide non active traces
        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            if i < webInterface_inst.module_signal_processor.active_vfos:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i*2)]['visible'] = True
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i*2+1)]['visible'] = True
                spectrum_fig.layout.annotations[i]['visible'] = True
                spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos+i]['visible'] = True
            else:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i*2)]['visible'] = False
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i*2+1)]['visible'] = False
                spectrum_fig.layout.annotations[i]['visible'] = False
                spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos+i]['visible'] = False

        waterfall_fig.data[0]['x'] = x
        waterfall_fig.update_xaxes(tickfont_size=1, range=[np.min(x), np.max(x)], showgrid=False)

        webInterface_inst.reset_spectrum_graph_flag = False
        app.push_mods({
               'spectrum-graph': {'figure': spectrum_fig},
               'waterfall-graph': {'figure': waterfall_fig},
        })

    else:
        # Update entire graph to update VFO-0 text. There is no way to just update annotations in Dash, but updating the entire spectrum is fast
        # enough to do on click
        x = webInterface_inst.spectrum[0,:] + webInterface_inst.daq_center_freq*10**6
        for i in range(webInterface_inst.module_signal_processor.active_vfos):

            # Find center of VFO display window
            maxIndex = webInterface_inst.spectrum[webInterface_inst.module_receiver.M+(i*2+1),:].argmax()

            reverseSpectrum = webInterface_inst.spectrum[webInterface_inst.module_receiver.M+(i*2+1),::-1]
            maxIndexReverse = reverseSpectrum.argmax()
            maxIndexReverse = len(reverseSpectrum) - maxIndexReverse - 1
            maxIndexCenter = (maxIndex + maxIndexReverse)//2

            # Update VFO Text Bearing
            doa = webInterface_inst.max_doas_list[i]
            if webInterface_inst._doa_fig_type == "Compass":
                doa = (360-doa+webInterface_inst.compass_ofset)%360
            spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos + i]['text'] = \
                                  str(doa)+"°"

            maxX = x[maxIndexCenter]
            spectrum_fig.layout.annotations[i]['x'] = maxX
            spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos + i]['x'] = maxX

            # Update selected VFO border
            width = 0
            if webInterface_inst.selected_vfo == i:
                width = 3

            # Update squelch/active colors
            if webInterface_inst.squelch_update[i]:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i*2)]['line'] = dict(color='green', width=width)
            else:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i*2)]['line'] = dict(color='red', width=width)

        # Make y values too so that the graph does not rapidly flash with random data on every click
        spectrum_fig.data[0]['x'] = x
        for m in range(1, np.size(webInterface_inst.spectrum, 0)):
            spectrum_fig.data[m-1]['y'] = webInterface_inst.spectrum[m,:]

        z = webInterface_inst.spectrum[1, :]
        app.push_mods({
            'spectrum-graph': {'figure': spectrum_fig},
            'waterfall-graph': {'extendData': [dict(z = [[z]]), [0], 50]}, #Add up spectrum for waterfall
        })


# Enable custom input fields
@app.callback([Output('customx', 'style'),
               Output('customy', 'style'),
               Output('antspacing', 'style')],
              [Input('radio_ant_arrangement', 'value')])
def toggle_custom_array_fields(toggle_value):
    if toggle_value == "UCA" or toggle_value == "ULA":
        return [{'display': 'none'}, {'display': 'none'}, {'display': 'block'}]
    else:
        return [{'display': 'block'}, {'display': 'block'}, {'display': 'none'}]

@app.callback(
    [Output(component_id="body_ant_spacing_wavelength",  component_property='children'),
    Output(component_id="label_ant_spacing_meter",  component_property='children'),
    Output(component_id="ambiguity_warning",  component_property='children'),
    Output(component_id="en_fb_avg_check",  component_property="options")],
    [Input(component_id ="placeholder_update_freq"       , component_property='children'),
    Input(component_id ="en_doa_check"       , component_property='value'),
    Input(component_id ="en_fb_avg_check"           , component_property='value'),
    Input(component_id ="ant_spacing_meter"           , component_property='value'),
    Input(component_id ="radio_ant_arrangement"           , component_property='value'),
    Input(component_id ="doa_fig_type"           , component_property='value'),
    Input(component_id ="doa_method"           , component_property='value'),
    Input(component_id ="ula_direction"           , component_property='value'),
    Input(component_id ="compass_ofset"           , component_property='value'),
    Input(component_id ="custom_array_x_meters"           , component_property='value'),
    Input(component_id ="custom_array_y_meters"           , component_property='value')],
)
def update_dsp_params(update_freq, en_doa, en_fb_avg, spacing_meter, ant_arrangement, doa_fig_type, doa_method, ula_direction, compass_ofset, custom_array_x_meters, custom_array_y_meters): #, input_value):
    webInterface_inst.ant_spacing_meters = spacing_meter
    wavelength = 300 / webInterface_inst.daq_center_freq

    webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength
    ant_spacing_wavelength = round(webInterface_inst.ant_spacing_meters / wavelength, 3)

    spacing_label = ""

    # Split CSV input in custom array

    webInterface_inst.custom_array_x_meters = np.float_(custom_array_x_meters.split(","))
    webInterface_inst.custom_array_y_meters = np.float_(custom_array_y_meters.split(","))

    webInterface_inst.module_signal_processor.custom_array_x = webInterface_inst.custom_array_x_meters / wavelength
    webInterface_inst.module_signal_processor.custom_array_y = webInterface_inst.custom_array_y_meters / wavelength

    # Max phase diff and ambiguity warning and Spatial smoothing control
    if ant_arrangement == "ULA":
        max_phase_diff = webInterface_inst.ant_spacing_meters / wavelength
        smoothing_possibility = [{"label":"", "options": 1, "disabled": False}] # Enables the checkbox
        spacing_label = "Interelement Spacing [m]:"
    elif ant_arrangement == "UCA":
        UCA_ant_spacing = (np.sqrt(2)*webInterface_inst.ant_spacing_meters*np.sqrt(1-np.cos(np.deg2rad(360/webInterface_inst.module_signal_processor.channel_number))))
        max_phase_diff = UCA_ant_spacing/wavelength
        smoothing_possibility = [{"label":"", "options": 1, "disabled": True}] # Disables the checkbox
        spacing_label = "Array Radius [m]:"
    elif ant_arrangement == "Custom":
        max_phase_diff = 0.25 #ant_spacing_meter / wavelength
        smoothing_possibility = [{"label":"", "options": 1, "disabled": True}] # Disables the checkbox
        spacing_label = "Interelement Spacing [m]"

    if max_phase_diff > 0.5:
        ambiguity_warning= "WARNING: Array size is too large for this frequency. DoA estimation is ambiguous. Max phase difference:{:.1f}°.".format(np.rad2deg(2*np.pi*max_phase_diff))
    elif max_phase_diff < 0.1:
        ambiguity_warning= "WARNING: Array size may be too small.".format(np.rad2deg(2*np.pi*max_phase_diff))
    else:
        ambiguity_warning= ""

    if en_doa is not None and len(en_doa):
        webInterface_inst.logger.debug("DoA estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_estimation = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_estimation = False

    webInterface_inst._doa_method=doa_method
    webInterface_inst.config_doa_in_signal_processor()

    if en_fb_avg is not None and len(en_fb_avg):
        webInterface_inst.logger.debug("FB averaging enabled")
        webInterface_inst.module_signal_processor.en_DOA_FB_avg   = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_FB_avg   = False

    webInterface_inst.module_signal_processor.DOA_ant_alignment=ant_arrangement
    webInterface_inst._doa_fig_type = doa_fig_type
    webInterface_inst.compass_ofset = compass_ofset
    webInterface_inst.module_signal_processor.ula_direction = ula_direction


    return [str(ant_spacing_wavelength), spacing_label, ambiguity_warning, smoothing_possibility]

@app.callback(
    None,
    [Input('cfg_rx_channels'         ,'value'),
    Input('cfg_daq_buffer_size'      ,'value'),
    Input('cfg_sample_rate'          ,'value'),
    Input('en_noise_source_ctr'      ,'value'),
    Input('cfg_cpi_size'             ,'value'),
    Input('cfg_decimation_ratio'     ,'value'),
    Input('cfg_fir_bw'               ,'value'),
    Input('cfg_fir_tap_size'         ,'value'),
    Input('cfg_fir_window'           ,'value'),
    Input('en_filter_reset'          ,'value'),
    Input('cfg_corr_size'            ,'value'),
    Input('cfg_std_ch_ind'           ,'value'),
    Input('en_iq_cal'                ,'value'),
    Input('cfg_gain_lock'            ,'value'),
    Input('en_req_track_lock_intervention','value'),
    Input('cfg_cal_track_mode'       ,'value'),
    Input('cfg_amplitude_cal_mode'   ,'value'),
    Input('cfg_cal_frame_interval'   ,'value'),
    Input('cfg_cal_frame_burst_size' ,'value'),
    Input('cfg_amplitude_tolerance'  ,'value'),
    Input('cfg_phase_tolerance'      ,'value'),
    Input('cfg_max_sync_fails'       ,'value'),
    Input('cfg_data_block_len'       ,'value'),
    Input('cfg_decimated_bw'         ,'value'),
    Input('cfg_recal_interval'       ,'value')]
)
def update_daq_ini_params(
                    cfg_rx_channels,cfg_daq_buffer_size,cfg_sample_rate,en_noise_source_ctr, \
                    cfg_cpi_size,cfg_decimation_ratio, \
                    cfg_fir_bw,cfg_fir_tap_size,cfg_fir_window,en_filter_reset,cfg_corr_size, \
                    cfg_std_ch_ind,en_iq_cal,cfg_gain_lock,en_req_track_lock_intervention, \
                    cfg_cal_track_mode,cfg_amplitude_cal_mode,cfg_cal_frame_interval, \
                    cfg_cal_frame_burst_size, cfg_amplitude_tolerance,cfg_phase_tolerance, \
                    cfg_max_sync_fails, cfg_data_block_len, cfg_decimated_bw, cfg_recal_interval, \
                    config_fname=daq_config_filename):

    ctx = dash.callback_context
    component_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if ctx.triggered:
        if len(ctx.triggered) == 1: # User manually changed one parameter
            webInterface_inst.tmp_daq_ini_cfg = "Custom"

        # If is was the preconfig changed, just update the preconfig values
        if component_id == 'daq_cfg_files':
            webInterface_inst.daq_ini_cfg_dict = read_config_file_dict(config_fname)
            webInterface_inst.tmp_daq_ini_cfg = webInterface_inst.daq_ini_cfg_dict['config_name']
            daq_cf_dict = webInterface_inst.daq_ini_cfg_dict

            if daq_cfg_dict is not None:
                en_noise_src_values       =[1] if daq_cfg_dict['en_noise_source_ctr']  else []
                en_filter_rst_values      =[1] if daq_cfg_dict['en_filter_reset'] else []
                en_iq_cal_values          =[1] if daq_cfg_dict['en_iq_cal'] else []
                en_req_track_lock_values  =[1] if daq_cfg_dict['require_track_lock_intervention'] else []

            en_advanced_daq_cfg   =[1] if webInterface_inst.en_advanced_daq_cfg                       else []
            en_basic_daq_cfg   =[1] if webInterface_inst.en_basic_daq_cfg                       else []

            cfg_decimated_bw = ((daq_cfg_dict['sample_rate']) / daq_cfg_dict['decimation_ratio']) / 10**3
            cfg_data_block_len = ( daq_cfg_dict['cpi_size'] / (cfg_decimated_bw) )
            cfg_recal_interval =  (daq_cfg_dict['cal_frame_interval'] * (cfg_data_block_len/10**3)) / 60

            if daq_cfg_dict['cal_track_mode'] == 0: #If set to no tracking
                cfg_recal_interval = 1

            app.push_mods({
                'cfg_data_block_len': {'value': cfg_data_block_len},
                'cfg_decimated_bw': {'value': cfg_decimated_bw},
                'cfg_recal_interval': {'value': cfg_recal_interval},
                'cfg_rx_channels': {'value': daq_cfg_dict['num_ch']},
                'cfg_daq_buffer_size': {'value': daq_cfg_dict['daq_buffer_size']},
                'cfg_sample_rate': {'value': daq_cfg_dict['sample_rate']/10**6},
                'en_noise_source_ctr': {'value': en_noise_src_values},
                'cfg_cpi_size': {'value': daq_cfg_dict['cpi_size']},
                'cfg_decimation_ratio': {'value': daq_cfg_dict['decimation_ratio']},
                'cfg_fir_bw': {'value': daq_cfg_dict['fir_relative_bandwidth']},
                'cfg_fir_tap_size': {'value': daq_cfg_dict['fir_tap_size']},
                'cfg_fir_window': {'value': daq_cfg_dict['fir_window']},
                'en_filter_reset': {'value': en_filter_rst_values},
                'cfg_cal_frame_interval': {'value': daq_cfg_dict['cal_frame_interval']},
                'cfg_corr_size': {'value': daq_cfg_dict['corr_size']},
                'cfg_std_ch_ind': {'value': daq_cfg_dict['std_ch_ind']},
                'en_iq_cal': {'value': en_iq_cal_values},
                'cfg_gain_lock': {'value': daq_cfg_dict['gain_lock_interval']},
                'en_req_track_lock_intervention': {'value': en_req_track_lock_values},
                'cfg_cal_track_mode': {'value': daq_cfg_dict['cal_track_mode']},
                'cfg_amplitude_cal_mode': {'value': daq_cfg_dict['amplitude_cal_mode']},
                'cfg_cal_frame_interval': {'value': daq_cfg_dict['cal_frame_interval']},
                'cfg_cal_frame_burst_size': {'value': daq_cfg_dict['cal_frame_burst_size']},
                'cfg_amplitude_tolerance': {'value': daq_cfg_dict['amplitude_tolerance']},
                'cfg_phase_tolerance': {'value': daq_cfg_dict['phase_tolerance']},
                'cfg_max_sync_fails': {'value': daq_cfg_dict['maximum_sync_fails']},
            })

            return Output('dummy_output', 'children', '') #[no_update, no_update, no_update, no_update]


        # If the input was from basic DAQ config, update the actual DAQ params
        if component_id == "cfg_data_block_len" or component_id == "cfg_decimated_bw" or component_id == "cfg_recal_interval":
            if not cfg_data_block_len or not cfg_decimated_bw or not cfg_recal_interval:
                return Output('dummy_output', 'children', '') #[no_update, no_update, no_update, no_update]

            cfg_daq_buffer_size = 262144 # This is a reasonable DAQ buffer size to use
            cfg_corr_size = 32768 # Reasonable value that never has problems calibrating
            en_noise_source_ctr = [1]
            cfg_fir_bw = 1
            cfg_fir_window = 'hann'
            en_filter_reset = []
            cfg_std_ch_ind = 0
            en_iq_cal = [1]
            en_req_track_lock_intervention = []
            cfg_amplitude_cal_mode = 'channel_power'
            cfg_cal_frame_burst_size = 10
            cfg_amplitude_tolerance = 2
            cfg_phase_tolerance = 2
            cfg_max_sync_fails = 10

            # Set sample rate to something sensible for the desired decimated_bw

            cfg_decimation_ratio = round( (cfg_sample_rate*10**6) / (cfg_decimated_bw*10**3) )

            cfg_cpi_size = round( (cfg_data_block_len / 10**3) * cfg_decimated_bw*10**3 )
            cfg_cal_frame_interval = round((cfg_recal_interval*60) / (cfg_data_block_len/10**3))

            while cfg_decimation_ratio * cfg_cpi_size < cfg_daq_buffer_size:
                cfg_daq_buffer_size = (int) (cfg_daq_buffer_size / 2)

            cfg_corr_size = (int) (cfg_daq_buffer_size / 2)

            # Choose a tap size larger than the decimation ratio
            cfg_fir_tap_size = (int)(cfg_decimation_ratio * 1.2) + 8

            if cfg_decimation_ratio == 1:
                cfg_fir_tap_size = 1

            cfg_cal_track_mode = 0
            if cfg_cal_frame_interval > 1:
                cfg_cal_track_mode = 2 #[{'label': calibration_tack_modes[1], 'value': calibration_tack_modes[1]}]
            else:
                cfg_cal_track_mode = 0

    param_dict = webInterface_inst.daq_ini_cfg_dict
    param_dict['config_name'] = "Custom"
    param_dict['num_ch'] = cfg_rx_channels
    param_dict['daq_buffer_size'] = cfg_daq_buffer_size
    param_dict['sample_rate'] = int(cfg_sample_rate*10**6)
    param_dict['en_noise_source_ctr'] = 1 if len(en_noise_source_ctr) else 0
    param_dict['cpi_size'] = cfg_cpi_size
    param_dict['decimation_ratio'] = cfg_decimation_ratio
    param_dict['fir_relative_bandwidth'] = cfg_fir_bw
    param_dict['fir_tap_size'] = cfg_fir_tap_size
    param_dict['fir_window'] = cfg_fir_window
    param_dict['en_filter_reset'] = 1 if len(en_filter_reset) else 0
    param_dict['corr_size'] = cfg_corr_size
    param_dict['std_ch_ind'] = cfg_std_ch_ind
    param_dict['en_iq_cal'] = 1 if len(en_iq_cal) else 0
    param_dict['gain_lock_interval'] = cfg_gain_lock
    param_dict['require_track_lock_intervention'] = 1 if len(en_req_track_lock_intervention) else 0
    param_dict['cal_track_mode'] = cfg_cal_track_mode
    param_dict['amplitude_cal_mode'] = cfg_amplitude_cal_mode
    param_dict['cal_frame_interval'] = cfg_cal_frame_interval
    param_dict['cal_frame_burst_size'] = cfg_cal_frame_burst_size
    param_dict['amplitude_tolerance'] = cfg_amplitude_tolerance
    param_dict['phase_tolerance'] = cfg_phase_tolerance
    param_dict['maximum_sync_fails'] = cfg_max_sync_fails

    webInterface_inst.daq_ini_cfg_dict = param_dict

    if ctx.triggered:
        # If we updated advanced daq, update basic DAQ params
        if component_id  == "cfg_sample_rate" or component_id == "cfg_decimation_ratio" or component_id == "cfg_cpi_size" or component_id == "cfg_cal_frame_interval":
            if not cfg_sample_rate or not cfg_decimation_ratio or not cfg_cpi_size:
                return Output('dummy_output', 'children', '') #[no_update, no_update, no_update, no_update]

            cfg_decimated_bw = ((int(cfg_sample_rate*10**6)) / cfg_decimation_ratio) / 10**3
            cfg_data_block_len = ( cfg_cpi_size  / (cfg_decimated_bw) )
            cfg_recal_interval =  (cfg_cal_frame_interval * (cfg_data_block_len/10**3)) / 60

            app.push_mods({
               'cfg_data_block_len': {'value': cfg_data_block_len},
               'cfg_decimated_bw': {'value': cfg_decimated_bw},
               'cfg_recal_interval': {'value': cfg_recal_interval},
            })
        # If we updated basic DAQ, update advanced DAQ
        elif component_id == "cfg_data_block_len" or component_id == "cfg_decimated_bw" or component_id == "cfg_recal_interval":
            app.push_mods({
               'cfg_decimation_ratio': {'value': cfg_decimation_ratio},
               'cfg_cpi_size': {'value': cfg_cpi_size},
               'cfg_cal_frame_interval': {'value': cfg_cal_frame_interval},
               'cfg_fir_tap_size': {'value': cfg_fir_tap_size},
               'cfg_sample_rate': {'value': cfg_sample_rate},
               'cfg_daq_buffer_size': {'value': cfg_daq_buffer_size},
               'cfg_corr_size': {'value': cfg_corr_size},
               'en_noise_source_ctr': {'value': en_noise_source_ctr},
               'cfg_fir_bw': {'value': cfg_fir_bw},
               'cfg_fir_window': {'value': cfg_fir_window},
               'en_filter_reset': {'value': en_filter_reset},
               'cfg_std_ch_ind': {'value': cfg_std_ch_ind},
               'en_iq_cal': {'value': en_iq_cal},
               'en_req_track_lock_intervention': {'value': en_req_track_lock_intervention},
               'cfg_amplitude_cal_mode': {'value': cfg_amplitude_cal_mode},
               'cfg_cal_frame_burst_size': {'value': cfg_cal_frame_burst_size},
               'cfg_amplitude_tolerance': {'value': cfg_amplitude_tolerance},
               'cfg_phase_tolerance': {'value': cfg_phase_tolerance},
               'cfg_max_sync_fails': {'value': cfg_max_sync_fails},
            })


@app.callback(Output('adv-cfg-container', 'style'),
             [Input("en_advanced_daq_cfg", "value")]
)
def toggle_adv_daq(toggle_value):
    webInterface_inst.en_advanced_daq_cfg = toggle_value
    if toggle_value:
        return {'display': 'block'}
    else:
        return {'display': 'none'}


@app.callback(Output('basic-cfg-container', 'style'),
             [Input("en_basic_daq_cfg", "value")]
)
def toggle_basic_daq(toggle_value):
    webInterface_inst.en_basic_daq_cfg = toggle_value
    if toggle_value:
        return {'display': 'block'}
    else:
        return {'display': 'none'}


@app.callback([Output("url"                     , "pathname")],
              [Input("daq_cfg_files"            , "value"),
              Input("placeholder_recofnig_daq" , "children"),
              Input("placeholder_update_rx" , "children")]
)
def reload_cfg_page(config_fname, dummy_0, dummy_1):
    webInterface_inst.daq_ini_cfg_dict = read_config_file_dict(config_fname)
    webInterface_inst.tmp_daq_ini_cfg = webInterface_inst.daq_ini_cfg_dict['config_name']

    return ["/config"]


@app.callback([Output("placeholder_update_rx", "children")],
              [Input("settings-refresh-timer", "n_intervals")],
              [State("url", "pathname")],
)
def settings_change_refresh(toggle_value, pathname):
    if webInterface_inst.needs_refresh:
        webInterface_inst.needs_refresh = False

        if pathname == "/" or pathname == "/init":
            return ["upddate"]
        elif pathname == "/config":
            return ["update"]
    return Output('dummy_output', 'children', '')


@app.callback(
    None,
    [Input(component_id="btn_reconfig_daq_chain"    , component_property="n_clicks")],
    [State(component_id ="daq_center_freq"       , component_property='value'),
    State(component_id ="daq_rx_gain"           , component_property='value')]
)
def reconfig_daq_chain(input_value, freq, gain):

    if input_value is None:
        return Output('dummy_output', 'children', '') #[no_update, no_update, no_update, no_update]

    # TODO: Check data interface mode here !
    #    Update DAQ Subsystem config file
    config_res, config_err = write_config_file_dict(webInterface_inst.daq_ini_cfg_dict)
    if config_res:
        webInterface_inst.daq_cfg_ini_error = config_err[0]
        return Output("placeholder_recofnig_daq", "children", '-1')
    else:
        webInterface_inst.logger.info("DAQ Subsystem configuration file edited")

    webInterface_inst.daq_restart = 1
    #    Restart DAQ Subsystem

    # Stop signal processing
    webInterface_inst.stop_processing()
    webInterface_inst.logger.debug("Signal processing stopped")

    #time.sleep(2)

    # Close control and IQ data interfaces
    webInterface_inst.close_data_interfaces()
    webInterface_inst.logger.debug("Data interfaces are closed")

    os.chdir(daq_subsystem_path)
    # Kill DAQ subsystem
    daq_stop_script = subprocess.Popen(['bash', daq_stop_filename])#, stdout=subprocess.DEVNULL)
    daq_stop_script.wait()
    webInterface_inst.logger.debug("DAQ Subsystem halted")

    # Start DAQ subsystem
    daq_start_script = subprocess.Popen(['bash', daq_start_filename])#, stdout=subprocess.DEVNULL)
    daq_start_script.wait()
    webInterface_inst.logger.debug("DAQ Subsystem restarted")

    #time.sleep(3)

    os.chdir(root_path)

    #TODO: Try this reinit method again, if it works it would save us needing to restore variable states

    # Reinitialize receiver data interface
    #if webInterface_inst.module_receiver.init_data_iface() == -1:
    #    webInterface_inst.logger.critical("Failed to restart the DAQ data interface")
    #    webInterface_inst.daq_cfg_ini_error = "Failed to restart the DAQ data interface"
    #    return Output('dummy_output', 'children', '') #[no_update, no_update, no_update, no_update]

        #return [-1]

    # Reset channel number count
    #webInterface_inst.module_receiver.M = webInterface_inst.daq_ini_cfg_params[1]

    #webInterface_inst.module_receiver.M = 0
    #webInterface_inst.module_signal_processor.first_frame = 1

    #webInterface_inst.module_receiver.eth_connect()
    #time.sleep(2)
    #webInterface_inst.config_daq_rf(webInterface_inst.daq_center_freq, webInterface_inst.module_receiver.daq_rx_gain)

    # Recreate and reinit the receiver and signal processor modules from scratch, keeping current setting values
    daq_center_freq = webInterface_inst.module_receiver.daq_center_freq
    daq_rx_gain = webInterface_inst.module_receiver.daq_rx_gain
    rec_ip_addr = webInterface_inst.module_receiver.rec_ip_addr

    DOA_ant_alignment = webInterface_inst.module_signal_processor.DOA_ant_alignment
    DOA_inter_elem_space = webInterface_inst.module_signal_processor.DOA_inter_elem_space
    en_DOA_estimation = webInterface_inst.module_signal_processor.en_DOA_estimation
    en_DOA_FB_avg = webInterface_inst.module_signal_processor.en_DOA_FB_avg
    ula_direction = webInterface_inst.module_signal_processor.ula_direction

    doa_format = webInterface_inst.module_signal_processor.DOA_data_format
    doa_station_id = webInterface_inst.module_signal_processor.station_id
    doa_lat = webInterface_inst.module_signal_processor.latitude
    doa_lon = webInterface_inst.module_signal_processor.longitude
    doa_fixed_heading = webInterface_inst.module_signal_processor.fixed_heading
    doa_heading = webInterface_inst.module_signal_processor.heading
    #alt
    #speed
    doa_hasgps = webInterface_inst.module_signal_processor.hasgps
    doa_usegps = webInterface_inst.module_signal_processor.usegps
    doa_gps_connected = webInterface_inst.module_signal_processor.gps_connected
    logging_level = webInterface_inst.logging_level
    data_interface = webInterface_inst.data_interface

    webInterface_inst.module_receiver = ReceiverRTLSDR(data_que=webInterface_inst.rx_data_que, data_interface=data_interface, logging_level=logging_level)
    webInterface_inst.module_receiver.daq_center_freq   = daq_center_freq
    webInterface_inst.module_receiver.daq_rx_gain       = daq_rx_gain #settings.uniform_gain #daq_rx_gain
    webInterface_inst.module_receiver.rec_ip_addr       = rec_ip_addr

    webInterface_inst.module_signal_processor = SignalProcessor(data_que=webInterface_inst.sp_data_que, module_receiver=webInterface_inst.module_receiver, logging_level=logging_level)
    webInterface_inst.module_signal_processor.DOA_ant_alignment    = DOA_ant_alignment
    webInterface_inst.module_signal_processor.DOA_inter_elem_space = DOA_inter_elem_space
    webInterface_inst.module_signal_processor.en_DOA_estimation    = en_DOA_estimation
    webInterface_inst.module_signal_processor.en_DOA_FB_avg        = en_DOA_FB_avg
    webInterface_inst.module_signal_processor.ula_direction        = ula_direction


    webInterface_inst.module_signal_processor.DOA_data_format = doa_format
    webInterface_inst.module_signal_processor.station_id = doa_station_id
    webInterface_inst.module_signal_processor.latitude = doa_lat
    webInterface_inst.module_signal_processor.longitude = doa_lon
    webInterface_inst.module_signal_processor.fixed_heading = doa_fixed_heading
    webInterface_inst.module_signal_processor.heading = doa_heading
    webInterface_inst.module_signal_processor.hasgps = doa_hasgps
    webInterface_inst.module_signal_processor.usegps = doa_usegps
    webInterface_inst.module_signal_processor.gps_connected = doa_gps_connected

    # This must be here, otherwise the gains dont reinit properly?
    webInterface_inst.module_receiver.M = webInterface_inst.daq_ini_cfg_dict['num_ch']
    print("M: " + str(webInterface_inst.module_receiver.M))

    webInterface_inst.config_doa_in_signal_processor()
    webInterface_inst.module_signal_processor.start()

    # Reinit the spectrum fig, because number of traces may have changed if tuner count is different
    global spectrum_fig
    spectrum_fig = init_spectrum_fig(fig_layout, trace_colors)

    # Restart signal processing
    webInterface_inst.start_processing()
    webInterface_inst.logger.debug("Signal processing started")
    webInterface_inst.daq_restart = 0

    webInterface_inst.daq_cfg_ini_error = ""
    webInterface_inst.active_daq_ini_cfg = webInterface_inst.daq_ini_cfg_dict['config_name'] #webInterface_inst.tmp_daq_ini_cfg

    return Output("daq_cfg_files", "value", daq_config_filename), Output("active_daq_ini_cfg", "children", "Active Configuration: " + webInterface_inst.active_daq_ini_cfg)

if __name__ == "__main__":
    # Debug mode does not work when the data interface is set to shared-memory "shmem"! 
    app.run_server(debug=False, host="0.0.0.0", port=8080)

"""
html.Div([
    html.H2("System Logs"),
    dcc.Textarea(
        placeholder = "Enter a value...",
        value = "System logs .. - Curently NOT used",
        style = {"width": "100%", "background-color": "#000000", "color":"#02c93d"}
    )
], className="card")
"""
