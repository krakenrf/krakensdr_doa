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
from krakenSDR_signal_processor import xi
from krakenSDR_signal_processor import SignalProcessor
from krakenSDR_receiver import ReceiverRTLSDR
import logging
import queue
import time
import subprocess
import json

import dash_core_components as dcc
import dash_html_components as html

import dash_devices as dash
from dash_devices.dependencies import Input, Output, State

import plotly.graph_objects as go
import numpy as np
from utils import *
from configparser import ConfigParser
from variables import *
from threading import Timer
from kraken_web_spectrum import init_spectrum_fig, plot_spectrum
from kraken_web_doa import plot_doa, generate_doa_page_layout
from kraken_web_config import write_config_file_dict, generate_config_page_layout
from waterfall import init_waterfall

# Load settings file
settings_file_path = os.path.join(root_path, "settings.json")
settings_found = False
if os.path.exists(settings_file_path):
    settings_found = True
    with open(settings_file_path, 'r') as myfile:
        dsp_settings = json.loads(myfile.read())


class webInterface():

    def __init__(self):
        self.user_interface = None

        self.logging_level = dsp_settings.get("logging_level", 0) * 10
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

        self._doa_fig_type = dsp_settings.get("doa_fig_type", "Linear")

        # Que to communicate with the signal processing module
        self.sp_data_que = queue.Queue(1)
        # Que to communicate with the receiver modules
        self.rx_data_que = queue.Queue(1)

        self.data_interface = dsp_settings.get("data_interface", "shmem")

        # Instantiate and configure Kraken SDR modules
        self.module_receiver = ReceiverRTLSDR(
            data_que=self.rx_data_que,
            data_interface=self.data_interface,
            logging_level=self.logging_level)
        self.module_receiver.daq_center_freq = float(
            dsp_settings.get("center_freq", 100.0)) * 10**6
        self.module_receiver.daq_rx_gain = float(
            dsp_settings.get("uniform_gain", 1.4))
        self.module_receiver.rec_ip_addr = dsp_settings.get(
            "default_ip", "0.0.0.0")

        self.module_signal_processor = SignalProcessor(
            data_que=self.sp_data_que,
            module_receiver=self.module_receiver,
            logging_level=self.logging_level)
        self.module_signal_processor.DOA_ant_alignment = dsp_settings.get(
            "ant_arrangement", "ULA")
        self.ant_spacing_meters = float(
            dsp_settings.get("ant_spacing_meters", 0.5))

        if self.module_signal_processor.DOA_ant_alignment == "UCA":
            self.module_signal_processor.DOA_UCA_radius_m = self.ant_spacing_meters
            # Convert RADIUS to INTERELEMENT SPACING
            inter_elem_spacing = (
                np.sqrt(2) *
                self.ant_spacing_meters *
                np.sqrt(
                    1 -
                    np.cos(
                        np.deg2rad(
                            360 /
                            self.module_signal_processor.channel_number))))
            self.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / \
                (300 / float(dsp_settings.get("center_freq", 100.0)))
        else:
            self.module_signal_processor.DOA_UCA_radius_m = np.Infinity
            self.module_signal_processor.DOA_inter_elem_space = self.ant_spacing_meters / \
                (300 / float(dsp_settings.get("center_freq", 100.0)))

        self.module_signal_processor.ula_direction = dsp_settings.get(
            "ula_direction", "Both")
        self.module_signal_processor.DOA_algorithm = dsp_settings.get(
            "doa_method", "MUSIC")
        self.module_signal_processor.DOA_expected_num_of_sources = dsp_settings.get(
            "expected_num_of_sources", 1)

        self.custom_array_x_meters = np.float_(
            dsp_settings.get(
                "custom_array_x_meters",
                "0.1,0.2,0.3,0.4,0.5").split(","))
        self.custom_array_y_meters = np.float_(
            dsp_settings.get(
                "custom_array_y_meters",
                "0.1,0.2,0.3,0.4,0.5").split(","))
        self.module_signal_processor.custom_array_x = self.custom_array_x_meters / \
            (300 / float(dsp_settings.get("center_freq", 100.0)))
        self.module_signal_processor.custom_array_y = self.custom_array_y_meters / \
            (300 / float(dsp_settings.get("center_freq", 100.0)))
        self.module_signal_processor.array_offset = int(
            dsp_settings.get("array_offset", 0))

        self.module_signal_processor.en_DOA_estimation = dsp_settings.get(
            "en_doa", 0)
        self.module_signal_processor.DOA_decorrelation_method = dsp_settings.get(
            "doa_decorrelation_method", "Off")
        self.module_signal_processor.start()

        #############################################
        #       UI Status and Config variables      #
        #############################################

        # Output Data format.
        self.module_signal_processor.DOA_data_format = dsp_settings.get(
            "doa_data_format", "Kraken App")

        # Station Information
        self.module_signal_processor.station_id = dsp_settings.get(
            "station_id", "NO-CALL")
        self.location_source = dsp_settings.get("location_source", "None")
        self.module_signal_processor.latitude = dsp_settings.get(
            "latitude", 0.0)
        self.module_signal_processor.longitude = dsp_settings.get(
            "longitude", 0.0)
        self.module_signal_processor.heading = dsp_settings.get("heading", 0.0)

        # Kraken Pro Remote Key
        self.module_signal_processor.krakenpro_key = dsp_settings.get(
            "krakenpro_key", 0.0)

        # VFO Configuration
        self.module_signal_processor.spectrum_fig_type = dsp_settings.get(
            "spectrum_calculation", "Single")
        self.module_signal_processor.vfo_mode = dsp_settings.get(
            "vfo_mode", 'Standard')
        self.module_signal_processor.dsp_decimation = int(
            dsp_settings.get("dsp_decimation", 0))
        self.module_signal_processor.active_vfos = int(
            dsp_settings.get("active_vfos", 0))
        self.module_signal_processor.output_vfo = int(
            dsp_settings.get("output_vfo", 0))
        self.module_signal_processor.optimize_short_bursts = dsp_settings.get(
            "en_optimize_short_bursts", 0)
        self.module_signal_processor.en_peak_hold = dsp_settings.get(
            "en_peak_hold", 0)
        self.selected_vfo = 0

        for i in range(self.module_signal_processor.max_vfos):
            self.module_signal_processor.vfo_bw[i] = int(
                dsp_settings.get("vfo_bw_" + str(i), 0))
            self.module_signal_processor.vfo_freq[i] = float(
                dsp_settings.get("vfo_freq_" + str(i), 0))
            self.module_signal_processor.vfo_squelch[i] = int(
                dsp_settings.get("vfo_squelch_" + str(i), 0))

        # DAQ Subsystem status parameters
        self.daq_conn_status = 0
        self.daq_cfg_iface_status = 0  # 0- ready, 1-busy
        self.daq_restart = 0  # 1-restarting
        self.daq_update_rate = 0
        self.daq_frame_sync = 1  # Active low
        self.daq_frame_index = 0
        self.daq_frame_type = "-"
        self.daq_power_level = 0
        self.daq_sample_delay_sync = 0
        self.daq_iq_sync = 0
        self.daq_noise_source_state = 0
        self.daq_center_freq = float(dsp_settings.get("center_freq", 100.0))
        self.daq_adc_fs = 0  # "-"
        self.daq_fs = 0  # "-"
        self.daq_cpi = 0  # "-"
        self.daq_if_gains = "[,,,,]"
        self.en_advanced_daq_cfg = False
        self.en_basic_daq_cfg = False
        self.en_system_control = []
        self.daq_ini_cfg_dict = read_config_file_dict()
        # "Default" # Holds the string identifier of the actively loaded DAQ ini configuration
        self.active_daq_ini_cfg = self.daq_ini_cfg_dict['config_name']
        self.tmp_daq_ini_cfg = "Default"
        self.daq_cfg_ini_error = ""

        # DSP Processing Parameters and Results
        self.spectrum = None
        self.doa_thetas = None
        self.doa_results = []
        self.doa_labels = []
        self.doas = []  # Final measured DoAs [deg]
        self.max_doas_list = []
        self.doa_confidences = []
        self.compass_offset = dsp_settings.get("compass_offset", 0)
        self.daq_dsp_latency = 0  # [ms]
        self.max_amplitude = 0  # Used to help setting the threshold level of the squelch
        self.avg_powers = []
        self.squelch_update = []
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
        self.vfo_cfg_inputs.append(
            Input(
                component_id="spectrum_fig_type",
                component_property="value"))
        self.vfo_cfg_inputs.append(
            Input(
                component_id="vfo_mode",
                component_property="value"))
        self.vfo_cfg_inputs.append(
            Input(
                component_id="dsp_decimation",
                component_property="value"))
        self.vfo_cfg_inputs.append(
            Input(
                component_id="active_vfos",
                component_property="value"))
        self.vfo_cfg_inputs.append(
            Input(
                component_id="output_vfo",
                component_property="value"))
        self.vfo_cfg_inputs.append(
            Input(
                component_id="en_optimize_short_bursts",
                component_property="value"))

        for i in range(self.module_signal_processor.max_vfos):
            self.vfo_cfg_inputs.append(
                Input(
                    component_id="vfo_" +
                    str(i) +
                    "_bw",
                    component_property="value"))
            self.vfo_cfg_inputs.append(
                Input(
                    component_id="vfo_" +
                    str(i) +
                    "_freq",
                    component_property="value"))
            self.vfo_cfg_inputs.append(
                Input(
                    component_id="vfo_" +
                    str(i) +
                    "_squelch",
                    component_property="value"))

    def save_configuration(self):
        data = {}

        # DAQ Configuration
        data["center_freq"] = self.module_receiver.daq_center_freq / 10**6
        data["uniform_gain"] = self.module_receiver.daq_rx_gain
        data["data_interface"] = dsp_settings.get("data_interface", "shmem")
        data["default_ip"] = dsp_settings.get("default_ip", "0.0.0.0")

        # DOA Estimation
        data["en_doa"] = self.module_signal_processor.en_DOA_estimation
        data["ant_arrangement"] = self.module_signal_processor.DOA_ant_alignment
        data["ula_direction"] = self.module_signal_processor.ula_direction
        # self.module_signal_processor.DOA_inter_elem_space
        data["ant_spacing_meters"] = self.ant_spacing_meters
        data["custom_array_x_meters"] = ','.join(
            ['%.2f' % num for num in self.custom_array_x_meters])
        data["custom_array_y_meters"] = ','.join(
            ['%.2f' % num for num in self.custom_array_y_meters])
        data["array_offset"] = int(self.module_signal_processor.array_offset)

        data["doa_method"] = self.module_signal_processor.DOA_algorithm
        data["doa_decorrelation_method"] = self.module_signal_processor.DOA_decorrelation_method
        data["compass_offset"] = self.compass_offset
        data["doa_fig_type"] = self._doa_fig_type
        data["en_peak_hold"] = self.module_signal_processor.en_peak_hold
        data["expected_num_of_sources"] = self.module_signal_processor.DOA_expected_num_of_sources

        # Web Interface
        data["en_hw_check"] = dsp_settings.get("en_hw_check", 0)
        data["logging_level"] = dsp_settings.get("logging_level", 0)
        data["disable_tooltips"] = dsp_settings.get("disable_tooltips", 0)

        # Output Data format. XML for Kerberos, CSV for Kracken, JSON future
        # XML, CSV, or JSON
        data["doa_data_format"] = self.module_signal_processor.DOA_data_format

        # Station Information
        data["station_id"] = self.module_signal_processor.station_id
        data["location_source"] = self.location_source
        data["latitude"] = self.module_signal_processor.latitude
        data["longitude"] = self.module_signal_processor.longitude
        data["heading"] = self.module_signal_processor.heading
        data["krakenpro_key"] = self.module_signal_processor.krakenpro_key
        data["rdf_mapper_server"] = self.module_signal_processor.RDF_mapper_server

        # VFO Information
        data["spectrum_calculation"] = self.module_signal_processor.spectrum_fig_type
        data["vfo_mode"] = self.module_signal_processor.vfo_mode
        data["dsp_decimation"] = self.module_signal_processor.dsp_decimation
        data["active_vfos"] = self.module_signal_processor.active_vfos
        data["output_vfo"] = self.module_signal_processor.output_vfo
        data["en_optimize_short_bursts"] = self.module_signal_processor.optimize_short_bursts

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            data["vfo_bw_" + str(i)] = self.module_signal_processor.vfo_bw[i]
            data["vfo_freq_" +
                 str(i)] = self.module_signal_processor.vfo_freq[i]
            data["vfo_squelch_" +
                 str(i)] = self.module_signal_processor.vfo_squelch[i]

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
        self.module_signal_processor.run_processing = True

    def stop_processing(self):
        self.module_signal_processor.run_processing = False
        while self.module_signal_processor.is_running:
            # Block until signal processor run_processing while loop ends
            time.sleep(0.01)

    def close_data_interfaces(self):
        self.module_receiver.eth_close()

    def close(self):
        pass

    def config_daq_rf(self, f0, gain):
        """
            Configures the RF parameters in the DAQ module
        """
        self.daq_cfg_iface_status = 1
        self.module_receiver.set_center_freq(int(f0 * 10**6))
        self.module_receiver.set_if_gain(gain)

        webInterface_inst.logger.info("Updating receiver parameters")
        webInterface_inst.logger.info("Center frequency: {:f} MHz".format(f0))
        webInterface_inst.logger.info("Gain: {:f} dB".format(gain))


#############################################
#          Prepare Dash application         #
############################################
webInterface_inst = webInterface()

#############################################
#       Prepare component dependencies      #
#############################################

spectrum_fig = init_spectrum_fig(webInterface_inst, fig_layout, trace_colors)
waterfall_fig = init_waterfall(webInterface_inst)

# app = dash.Dash(__name__, suppress_callback_exceptions=True,
# compress=True, update_title="") # cannot use update_title with
# dash_devices
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "KrakenSDR DoA"

app.config.suppress_callback_exceptions = True


# app_log = logger.getLogger('werkzeug')
# app_log.setLevel(settings.logging_level*10)
# app_log.setLevel(30) # TODO: Only during dev time
app.layout = html.Div([
    dcc.Location(id='url', children='/config', refresh=True),

    html.Div([html.Img(src="assets/kraken_interface_bw.png",
                       style={"display": "block",
                              "margin-left": "auto",
                              "margin-right": "auto",
                              "height": "60px"})]),
    html.Div([html.A("Configuration", className="header_active", id="header_config", href="/config"),
              html.A(
        "Spectrum",
        className="header_inactive",
        id="header_spectrum",
        href="/spectrum"),
        html.A(
        "DoA Estimation",
        className="header_inactive",
        id="header_doa",
        href="/doa"),
    ], className="header"),

    dcc.Interval(id="settings-refresh-timer", interval=5000, n_intervals=0),

    html.Div(id="placeholder_start", style={"display": "none"}),
    html.Div(id="placeholder_stop", style={"display": "none"}),
    html.Div(id="placeholder_save", style={"display": "none"}),
    html.Div(id="placeholder_update_rx", style={"display": "none"}),
    html.Div(id="placeholder_recofnig_daq", style={"display": "none"}),
    html.Div(
        id="placeholder_update_daq_ini_params",
        style={
            "display": "none"}),
    html.Div(id="placeholder_update_freq", style={"display": "none"}),
    html.Div(id="placeholder_update_dsp", style={"display": "none"}),
    html.Div(id="placeholder_config_page_upd", style={"display": "none"}),
    html.Div(id="placeholder_spectrum_page_upd", style={"display": "none"}),
    html.Div(id="placeholder_doa_page_upd", style={"display": "none"}),
    html.Div(id="dummy_output", style={"display": "none"}),


    html.Div(id='page-content')
])

spectrum_page_layout = html.Div([
    html.Div([
        dcc.Graph(
            id="spectrum-graph",
            style={'width': '100%', 'height': '45%'},
            figure=spectrum_fig  # fig_dummy #spectrum_fig #fig_dummy
        ),
        dcc.Graph(
            id="waterfall-graph",
            style={'width': '100%', 'height': '65%'},
            figure=waterfall_fig  # waterfall fig remains unchanged always due to slow speed to update entire graph #fig_dummy #spectrum_fig #fig_dummy
        ),
    ], style={'width': '100%', 'height': '80vh'}),
])
# ============================================
#          CALLBACK FUNCTIONS
# ============================================


@app.callback_connect
def func(client, connect):
    if connect and len(app.clients) == 1:
        fetch_dsp_data()
        fetch_gps_data()
        settings_change_watcher()
    elif not connect and len(app.clients) == 0:
        webInterface_inst.dsp_timer.cancel()
        webInterface_inst.gps_timer.cancel()
        webInterface_inst.settings_change_timer.cancel()


def fetch_dsp_data():
    daq_status_update_flag = 0
    spectrum_update_flag = 0
    doa_update_flag = 0
    # freq_update            = 0 #no_update
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
    if webInterface_inst.daq_restart:  # Set by the restarting script
        daq_status_update_flag = 1
    try:
        # Fetch new data from the signal processing module
        que_data_packet = webInterface_inst.sp_data_que.get(False)
        for data_entry in que_data_packet:
            if data_entry[0] == "iq_header":
                webInterface_inst.logger.debug(
                    "Iq header data fetched from signal processing que")
                iq_header = data_entry[1]
                # Unpack header
                webInterface_inst.daq_frame_index = iq_header.cpi_index
                if iq_header.frame_type == iq_header.FRAME_TYPE_DATA:
                    webInterface_inst.daq_frame_type = "Data"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_DUMMY:
                    webInterface_inst.daq_frame_type = "Dummy"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_CAL:
                    webInterface_inst.daq_frame_type = "Calibration"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_TRIGW:
                    webInterface_inst.daq_frame_type = "Trigger wait"
                else:
                    webInterface_inst.daq_frame_type = "Unknown"

                webInterface_inst.daq_frame_sync = iq_header.check_sync_word()
                webInterface_inst.daq_power_level = iq_header.adc_overdrive_flags
                webInterface_inst.daq_sample_delay_sync = iq_header.delay_sync_flag
                webInterface_inst.daq_iq_sync = iq_header.iq_sync_flag
                webInterface_inst.daq_noise_source_state = iq_header.noise_source_state

                # if webInterface_inst.daq_center_freq != iq_header.rf_center_freq/10**6:
                #    freq_update = 1

                webInterface_inst.daq_center_freq = iq_header.rf_center_freq / 10**6
                webInterface_inst.daq_adc_fs = iq_header.adc_sampling_freq / 10**6
                webInterface_inst.daq_fs = iq_header.sampling_freq / 10**6
                webInterface_inst.daq_cpi = int(
                    iq_header.cpi_length * 10**3 / iq_header.sampling_freq)
                gain_list_str = ""

                for m in range(iq_header.active_ant_chs):
                    gain_list_str += str(iq_header.if_gains[m] / 10)
                    gain_list_str += ", "

                webInterface_inst.daq_if_gains = gain_list_str[:-2]
                daq_status_update_flag = 1
            elif data_entry[0] == "update_rate":
                webInterface_inst.daq_update_rate = data_entry[1]
            elif data_entry[0] == "latency":
                webInterface_inst.daq_dsp_latency = data_entry[1] + \
                    webInterface_inst.daq_cpi
            elif data_entry[0] == "max_amplitude":
                webInterface_inst.max_amplitude = data_entry[1]
            elif data_entry[0] == "avg_powers":
                avg_powers_str = ""
                for avg_power in data_entry[1]:
                    avg_powers_str += "{:.1f}".format(avg_power)
                    avg_powers_str += ", "
                webInterface_inst.avg_powers = avg_powers_str[:-2]
            elif data_entry[0] == "spectrum":
                webInterface_inst.logger.debug(
                    "Spectrum data fetched from signal processing que")
                spectrum_update_flag = 1
                webInterface_inst.spectrum = data_entry[1]
            elif data_entry[0] == "doa_thetas":
                webInterface_inst.doa_thetas = data_entry[1]
                doa_update_flag = 1
                webInterface_inst.doa_results = []
                webInterface_inst.doa_labels = []
                webInterface_inst.doas = []
                webInterface_inst.max_doas_list = []
                webInterface_inst.doa_confidences = []
                webInterface_inst.logger.debug(
                    "DoA estimation data fetched from signal processing que")
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
                webInterface_inst.logger.warning(
                    "Unknown data entry: {:s}".format(data_entry[0]))
    except queue.Empty:
        # Handle empty queue here
        webInterface_inst.logger.debug("Signal processing que is empty")
    else:
        pass
        # Handle task here and call q.task_done()

    if (webInterface_inst.pathname == "/config" or webInterface_inst.pathname ==
            "/" or webInterface_inst.pathname == "/init") and daq_status_update_flag:
        update_daq_status()
    elif webInterface_inst.pathname == "/spectrum" and spectrum_update_flag:
        plot_spectrum(app, webInterface_inst, spectrum_fig, waterfall_fig)
    # or (webInterface_inst.pathname == "/doa" and
    # webInterface_inst.reset_doa_graph_flag):
    elif (webInterface_inst.pathname == "/doa" and doa_update_flag):
        plot_doa(app, webInterface_inst, doa_fig)

    webInterface_inst.dsp_timer = Timer(.01, fetch_dsp_data)
    webInterface_inst.dsp_timer.start()


def settings_change_watcher():
    last_changed_time = os.stat(settings_file_path).st_mtime
    time_delta = last_changed_time - webInterface_inst.last_changed_time_previous

    # Load settings file
    if (time_delta > 0):  # If > 0, file was changed
        global dsp_settings
        if os.path.exists(settings_file_path):
            with open(settings_file_path, 'r') as myfile:
                # update global dsp_settings, to ensureother functions using it
                # get the most up to date values??
                dsp_settings = json.loads(myfile.read())

        center_freq = float(dsp_settings.get("center_freq", 100.0))
        gain = float(dsp_settings.get("uniform_gain", 1.4))

        DOA_ant_alignment = dsp_settings.get("ant_arrangement")
        webInterface_inst.ant_spacing_meters = float(
            dsp_settings.get("ant_spacing_meters", 0.5))

        webInterface_inst.module_signal_processor.en_DOA_estimation = dsp_settings.get(
            "en_doa", 0)
        webInterface_inst.module_signal_processor.DOA_decorrelation_method = dsp_settings.get(
            "doa_decorrelation_method", 0)

        webInterface_inst.module_signal_processor.DOA_ant_alignment = dsp_settings.get(
            "ant_arrangement", "ULA")
        webInterface_inst.ant_spacing_meters = float(
            dsp_settings.get("ant_spacing_meters", 0.5))

        webInterface_inst.custom_array_x_meters = np.float_(dsp_settings.get(
            "custom_array_x_meters", "0.1,0.2,0.3,0.4,0.5").split(","))
        webInterface_inst.custom_array_y_meters = np.float_(dsp_settings.get(
            "custom_array_y_meters", "0.1,0.2,0.3,0.4,0.5").split(","))
        webInterface_inst.module_signal_processor.custom_array_x = webInterface_inst.custom_array_x_meters / \
            (300 / webInterface_inst.module_receiver.daq_center_freq)
        webInterface_inst.module_signal_processor.custom_array_y = webInterface_inst.custom_array_y_meters / \
            (300 / webInterface_inst.module_receiver.daq_center_freq)

        # Station Information
        webInterface_inst.module_signal_processor.station_id = dsp_settings.get(
            "station_id", "NO-CALL")
        webInterface_inst.location_source = dsp_settings.get(
            "location_source", "None")
        webInterface_inst.module_signal_processor.latitude = dsp_settings.get(
            "latitude", 0.0)
        webInterface_inst.module_signal_processor.longitude = dsp_settings.get(
            "longitude", 0.0)
        webInterface_inst.module_signal_processor.heading = dsp_settings.get(
            "heading", 0.0)
        webInterface_inst.module_signal_processor.krakenpro_key = dsp_settings.get(
            "krakenpro_key", 0.0)
        webInterface_inst.module_signal_processor.RDF_mapper_server = dsp_settings.get(
            "rdf_mapper_server", "http://RDF_MAPPER_SERVER.com/save.php")

        # VFO Configuration
        webInterface_inst.module_signal_processor.spectrum_fig_type = dsp_settings.get(
            "spectrum_calculation", "Single")
        webInterface_inst.module_signal_processor.vfo_mode = dsp_settings.get(
            "vfo_mode", 'Standard')
        webInterface_inst.module_signal_processor.dsp_decimation = int(
            dsp_settings.get("dsp_decimation", 0))
        webInterface_inst.module_signal_processor.active_vfos = int(
            dsp_settings.get("active_vfos", 0))
        webInterface_inst.module_signal_processor.output_vfo = int(
            dsp_settings.get("output_vfo", 0))
        webInterface_inst.compass_offset = dsp_settings.get(
            "compass_offset", 0)
        webInterface_inst.module_signal_processor.optimize_short_bursts = dsp_settings.get(
            "en_optimize_short_bursts", 0)
        webInterface_inst.module_signal_processor.en_peak_hold = dsp_settings.get(
            "en_peak_hold", 0)

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            webInterface_inst.module_signal_processor.vfo_bw[i] = int(
                dsp_settings.get("vfo_bw_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_freq[i] = float(
                dsp_settings.get("vfo_freq_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_squelch[i] = int(
                dsp_settings.get("vfo_squelch_" + str(i), 0))

        webInterface_inst.module_signal_processor.DOA_algorithm = dsp_settings.get(
            "doa_method", "MUSIC")
        webInterface_inst.module_signal_processor.DOA_expected_num_of_sources = dsp_settings.get(
            "expected_num_of_sources", 1)
        webInterface_inst._doa_fig_type = dsp_settings.get(
            "doa_fig_type", "Linear")
        webInterface_inst.module_signal_processor.ula_direction = dsp_settings.get(
            "ula_direction", "Both")
        webInterface_inst.module_signal_processor.array_offset = int(
            dsp_settings.get("array_offset", 0))

        freq_delta = webInterface_inst.daq_center_freq - center_freq
        gain_delta = webInterface_inst.module_receiver.daq_rx_gain - gain

        if (abs(freq_delta) > 0.001 or abs(gain_delta) > 0.001):
            webInterface_inst.daq_center_freq = center_freq
            webInterface_inst.config_daq_rf(center_freq, gain)

        webInterface_inst.needs_refresh = True

    webInterface_inst.last_changed_time_previous = last_changed_time

    webInterface_inst.settings_change_timer = Timer(1, settings_change_watcher)
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
            conn_status_style = {"color": "#7ccc63"}
        else:  # Config interface is busy
            daq_conn_status_str = "Reconfiguration.."
            conn_status_style = {"color": "#f39c12"}
    else:
        daq_conn_status_str = "Disconnected"
        conn_status_style = {"color": "#e74c3c"}

    if webInterface_inst.daq_restart:
        daq_conn_status_str = "Restarting.."
        conn_status_style = {"color": "#f39c12"}

    if webInterface_inst.daq_update_rate < 1:
        daq_update_rate_str = "{:d} ms".format(
            round(webInterface_inst.daq_update_rate * 1000))
    else:
        daq_update_rate_str = "{:.2f} s".format(
            webInterface_inst.daq_update_rate)

    daq_dsp_latency = "{:d} ms".format(webInterface_inst.daq_dsp_latency)
    daq_frame_index_str = str(webInterface_inst.daq_frame_index)

    daq_frame_type_str = webInterface_inst.daq_frame_type
    if webInterface_inst.daq_frame_type == "Data":
        frame_type_style = frame_type_style = {"color": "#7ccc63"}
    elif webInterface_inst.daq_frame_type == "Dummy":
        frame_type_style = frame_type_style = {"color": "white"}
    elif webInterface_inst.daq_frame_type == "Calibration":
        frame_type_style = frame_type_style = {"color": "#f39c12"}
    elif webInterface_inst.daq_frame_type == "Trigger wait":
        frame_type_style = frame_type_style = {"color": "#f39c12"}
    else:
        frame_type_style = frame_type_style = {"color": "#e74c3c"}

    if webInterface_inst.daq_frame_sync:
        daq_frame_sync_str = "LOSS"
        frame_sync_style = {"color": "#e74c3c"}
    else:
        daq_frame_sync_str = "Ok"
        frame_sync_style = {"color": "#7ccc63"}
    if webInterface_inst.daq_sample_delay_sync:
        daq_delay_sync_str = "Ok"
        delay_sync_style = {"color": "#7ccc63"}
    else:
        daq_delay_sync_str = "LOSS"
        delay_sync_style = {"color": "#e74c3c"}

    if webInterface_inst.daq_iq_sync:
        daq_iq_sync_str = "Ok"
        iq_sync_style = {"color": "#7ccc63"}
    else:
        daq_iq_sync_str = "LOSS"
        iq_sync_style = {"color": "#e74c3c"}

    if webInterface_inst.daq_noise_source_state:
        daq_noise_source_str = "Enabled"
        noise_source_style = {"color": "#e74c3c"}
    else:
        daq_noise_source_str = "Disabled"
        noise_source_style = {"color": "#7ccc63"}

    if webInterface_inst.daq_power_level:
        daq_power_level_str = "Overdrive"
        daq_power_level_style = {"color": "#e74c3c"}
    else:
        daq_power_level_str = "OK"
        daq_power_level_style = {"color": "#7ccc63"}

    # webInterface_inst.module_signal_processor.usegps:
    if webInterface_inst.module_signal_processor.gps_status == "Connected":
        gps_en_str = "Connected"
        gps_en_str_style = {"color": "#7ccc63"}
    else:
        gps_en_str = webInterface_inst.module_signal_processor.gps_status
        gps_en_str_style = {"color": "#e74c3c"}

    daq_rf_center_freq_str = str(webInterface_inst.daq_center_freq)
    daq_sampling_freq_str = str(webInterface_inst.daq_fs)
    bw = webInterface_inst.daq_fs / \
        webInterface_inst.module_signal_processor.dsp_decimation
    dsp_decimated_bw_str = '{0:.3f}'.format(bw)
    vfo_range_str = '{0:.3f}'.format(
        webInterface_inst.daq_center_freq - bw / 2) + " - " + '{0:.3f}'.format(
        webInterface_inst.daq_center_freq + bw / 2)
    daq_cpi_str = str(webInterface_inst.daq_cpi)
    daq_max_amp_str = "{:.1f}".format(webInterface_inst.max_amplitude)
    daq_avg_powers_str = webInterface_inst.avg_powers

    app.push_mods({
        'body_daq_update_rate': {'children': daq_update_rate_str},
        'body_daq_dsp_latency': {'children': daq_dsp_latency},
        'body_daq_frame_index': {'children': daq_frame_index_str},
        'body_daq_frame_sync': {'children': daq_frame_sync_str},
        'body_daq_frame_type': {'children': daq_frame_type_str},
        'body_daq_power_level': {'children': daq_power_level_str},
        'body_daq_conn_status': {'children': daq_conn_status_str},
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
        'body_avg_powers': {'children': daq_avg_powers_str},
        'gps_status': {'children': gps_en_str}
    })

    app.push_mods({
        'body_daq_frame_sync': {'style': frame_sync_style},
        'body_daq_frame_type': {'style': frame_type_style},
        'body_daq_power_level': {'style': daq_power_level_style},
        'body_daq_conn_status': {'style': conn_status_style},
        'body_daq_delay_sync': {'style': delay_sync_style},
        'body_daq_iq_sync': {'style': iq_sync_style},
        'body_daq_noise_source': {'style': noise_source_style},
        'gps_status': {'style': gps_en_str_style},
    })

    # Update local recording file size
    recording_file_size = webInterface_inst.module_signal_processor.get_recording_filesize()
    app.push_mods({
        'body_file_size': {'children': recording_file_size}
    })


@app.callback_shared(
    # Output(component_id="placeholder_update_freq", component_property="children"),
    # None,
    #    Output(component_id="body_ant_spacing_wavelength",  component_property='children'),
    None,
    [Input(component_id="btn-update_rx_param", component_property="n_clicks")],
    [State(component_id="daq_center_freq", component_property='value'),
     State(component_id="daq_rx_gain", component_property='value')],
)
def update_daq_params(input_value, f0, gain):
    if webInterface_inst.module_signal_processor.run_processing:
        webInterface_inst.daq_center_freq = f0
        webInterface_inst.config_daq_rf(f0, gain)

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            webInterface_inst.module_signal_processor.vfo_freq[i] = f0
            app.push_mods({
                f"vfo_{i}_freq": {'value': f0}
            })

        wavelength = 300 / webInterface_inst.daq_center_freq
        # webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength

        if webInterface_inst.module_signal_processor.DOA_ant_alignment == "UCA":
            # Convert RADIUS to INTERELEMENT SPACING
            inter_elem_spacing = (
                np.sqrt(2) *
                webInterface_inst.ant_spacing_meters *
                np.sqrt(
                    1 -
                    np.cos(
                        np.deg2rad(
                            360 /
                            webInterface_inst.module_signal_processor.channel_number))))
            webInterface_inst.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / wavelength
        else:
            webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength

        ant_spacing_wavelength = round(
            webInterface_inst.module_signal_processor.DOA_inter_elem_space, 3)
        app.push_mods({
            'body_ant_spacing_wavelength': {'children': str(ant_spacing_wavelength)},
        })


@app.callback_shared(
    None,
    [Input(component_id="filename_input", component_property="value"),
     Input(component_id="en_data_record", component_property="value"),
     Input(component_id="write_interval_input", component_property="value")]
)
def update_data_recording_params(filename, en_data_record, write_interval):
    # webInterface_inst.module_signal_processor.data_recording_file_name = filename
    webInterface_inst.module_signal_processor.update_recording_filename(
        filename)
    # TODO: Call sig processor file update function here

    if en_data_record is not None and len(en_data_record):
        webInterface_inst.module_signal_processor.en_data_record = True
    else:
        webInterface_inst.module_signal_processor.en_data_record = False

    webInterface_inst.module_signal_processor.write_interval = float(
        write_interval)


@app.callback_shared(
    Output("download_recorded_file", "data"),
    [Input("btn_download_file", "n_clicks")]
)
def send_recorded_file(n_clicks):
    return dcc.send_file(os.path.join(os.path.join(webInterface_inst.module_signal_processor.root_path,
                         webInterface_inst.module_signal_processor.data_recording_file_name)))

# Set DOA Output Format


@app.callback_shared(None,
                     [Input(component_id="doa_format_type", component_property='value')])
def set_doa_format(doa_format):
    webInterface_inst.module_signal_processor.DOA_data_format = doa_format


# Update Station ID
@app.callback_shared(None,
                     [Input(component_id='station_id_input', component_property='value')])
def set_station_id(station_id):
    webInterface_inst.module_signal_processor.station_id = station_id


@app.callback_shared(None,
                     [Input(component_id='krakenpro_key', component_property='value')])
def set_kraken_pro_key(key):
    webInterface_inst.module_signal_processor.krakenpro_key = key


@app.callback_shared(None,
                     [Input(component_id='rdf_mapper_server_address', component_property='value')])
def set_rdf_mapper_server(url):
    webInterface_inst.module_signal_processor.RDF_mapper_server = url

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


# Enable of Disable Kraken Pro Key Box
@app.callback(Output('rdf_mapper_server_address_field', 'style'),
              [Input('doa_format_type', 'value')])
def toggle_kraken_pro_key(doa_format_type):
    if doa_format_type == "RDF Mapper" or doa_format_type == "Full POST":
        return {'display': 'block'}
    else:
        return {'display': 'none'}


# Enable or Disable Heading Input Fields
@app.callback(Output('heading_field', 'style'),
              [Input('loc_src_dropdown', 'value'),
               Input(component_id='fixed_heading_check', component_property='value')],
              [State('heading_input', component_property='value')])
def toggle_location_info(static_loc, fixed_heading, heading):
    if static_loc == "Static":
        webInterface_inst.module_signal_processor.fixed_heading = True
        webInterface_inst.module_signal_processor.heading = heading
        return {'display': 'block'}
    elif static_loc == "gpsd" and fixed_heading:
        webInterface_inst.module_signal_processor.heading = heading
        return {'display': 'block'}
    elif static_loc == "gpsd" and not fixed_heading:
        webInterface_inst.module_signal_processor.fixed_heading = False
        return {'display': 'none'}
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
                      Input(
                         component_id="longitude_input",
                         component_property='value'),
                         Input('loc_src_dropdown', 'value')])
def set_static_location(lat, lon, toggle_value):
    if toggle_value == "Static":
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


# Enable GPS (note that we need this to fire on load, so we cannot use
# callback_shared!)
@app.callback([Output("gps_status", "children"),
               Output("gps_status", "style")],
              [Input('loc_src_dropdown', 'value')])
def enable_gps(toggle_value):
    if toggle_value == "gpsd":
        status = webInterface_inst.module_signal_processor.enable_gps()
        if status:
            webInterface_inst.module_signal_processor.usegps = True
            return ["Connected", {"color": "#7ccc63"}]
        else:
            return ["Error", {"color": "#e74c3c"}]
    else:
        webInterface_inst.module_signal_processor.usegps = False
        return ["-", {"color": "white"}]


@app.callback_shared(
    None,
    webInterface_inst.vfo_cfg_inputs
)
def update_vfo_params(*args):

    # Get dict of input variables
    input_names = [
        item.component_id for item in webInterface_inst.vfo_cfg_inputs]
    kwargs_dict = dict(zip(input_names, args))

    webInterface_inst.module_signal_processor.spectrum_fig_type = kwargs_dict[
        "spectrum_fig_type"]
    webInterface_inst.module_signal_processor.vfo_mode = kwargs_dict["vfo_mode"]

    active_vfos = kwargs_dict["active_vfos"]
    # If VFO mode is in the VFO-0 Auto Max mode, we active VFOs to 1 only
    if kwargs_dict["vfo_mode"] == 'Auto':
        active_vfos = 1
        app.push_mods({
            'active_vfos': {'value': 1}
        })

    webInterface_inst.module_signal_processor.dsp_decimation = max(
        int(kwargs_dict["dsp_decimation"]), 1)
    webInterface_inst.module_signal_processor.active_vfos = active_vfos
    webInterface_inst.module_signal_processor.output_vfo = kwargs_dict["output_vfo"]

    en_optimize_short_bursts = kwargs_dict["en_optimize_short_bursts"]
    if en_optimize_short_bursts is not None and len(en_optimize_short_bursts):
        webInterface_inst.module_signal_processor.optimize_short_bursts = True
    else:
        webInterface_inst.module_signal_processor.optimize_short_bursts = False

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        if i < kwargs_dict["active_vfos"]:
            app.push_mods({
                'vfo' + str(i): {'style': {'display': 'block'}}
            })
        else:
            app.push_mods({
                'vfo' + str(i): {'style': {'display': 'none'}}
            })

    if webInterface_inst.daq_fs > 0:
        bw = webInterface_inst.daq_fs / \
            webInterface_inst.module_signal_processor.dsp_decimation
        vfo_min = webInterface_inst.daq_center_freq - bw / 2
        vfo_max = webInterface_inst.daq_center_freq + bw / 2

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            webInterface_inst.module_signal_processor.vfo_bw[i] = int(
                min(kwargs_dict['vfo_' + str(i) + '_bw'], bw * 10**6))
            webInterface_inst.module_signal_processor.vfo_freq[i] = int(
                max(min(kwargs_dict['vfo_' + str(i) + '_freq'], vfo_max), vfo_min) * 10**6)
            webInterface_inst.module_signal_processor.vfo_squelch[i] = int(
                kwargs_dict['vfo_' + str(i) + '_squelch'])


@app.callback([Output("page-content", "children"),
              Output("header_config", "className"),
              Output("header_spectrum", "className"),
              Output("header_doa", "className")],
              [Input("url", "pathname")],
              )
def display_page(pathname):

    # CHECK CONTEXT, was this called by url or timer?

    # if self.needs_refresh:
    #    self.needs_refresh = False

    global spectrum_fig
    global doa_fig
    webInterface_inst.pathname = pathname

    if pathname == "/" or pathname == "/init":
        webInterface_inst.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(
            webInterface_inst), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/config":
        webInterface_inst.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(
            webInterface_inst), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/spectrum":
        webInterface_inst.module_signal_processor.en_spectrum = True
        webInterface_inst.reset_spectrum_graph_flag = True
        return [spectrum_page_layout, "header_inactive",
                "header_active", "header_inactive"]
    elif pathname == "/doa":
        webInterface_inst.module_signal_processor.en_spectrum = False
        webInterface_inst.reset_doa_graph_flag = True
        plot_doa(app, webInterface_inst, doa_fig)
        return [generate_doa_page_layout(
            webInterface_inst), "header_inactive", "header_inactive", "header_active"]
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
    [Input(component_id='btn-save_cfg', component_property='n_clicks')],
)
def save_config_btn(input_value):
    webInterface_inst.logger.info("Saving DAQ and DSP Configuration")
    webInterface_inst.save_configuration()


@app.callback_shared(
    None,
    [Input(component_id='btn-restart_sw', component_property='n_clicks')],
)
def restart_sw_btn(input_value):
    webInterface_inst.logger.info("Restarting Software")
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
    os.chdir(root_path)
    daq_start_script = subprocess.Popen(['bash', "kraken_doa_start.sh"])  # ,


@app.callback_shared(
    None,
    [Input(component_id='btn-restart_system', component_property='n_clicks')],
)
def restart_system_btn(input_value):
    webInterface_inst.logger.info("Restarting System")
    subprocess.call(["reboot"])


@app.callback_shared(
    None,
    [Input(component_id='btn-shtudown_system', component_property='n_clicks')],
)
def shutdown_system_btn(input_value):
    webInterface_inst.logger.info("Shutting System Down")
    subprocess.call(["shutdown", "now"])


@app.callback_shared(
    None,
    [Input(component_id='btn-clear_cache', component_property='n_clicks')],
)
def clear_cache_btn(input_value):
    webInterface_inst.logger.info("Clearing Python and Numba Caches")
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
    os.chdir(root_path)
    daq_start_script = subprocess.Popen(
        ['bash', "kraken_doa_start.sh", "-c"])  # ,


@app.callback_shared(
    None,
    [Input('spectrum-graph', 'clickData')]
)
def click_to_set_freq_spectrum(clickData):
    set_clicked(webInterface_inst, clickData)


@app.callback_shared(
    None,
    [Input('waterfall-graph', 'clickData')]
)
def click_to_set_waterfall_spectrum(clickData):
    set_clicked(webInterface_inst, clickData)


# Enable custom input fields
@app.callback([Output('customx', 'style'),
               Output('customy', 'style'),
               Output('antspacing', 'style')],
              [Input('radio_ant_arrangement', 'value')])
def toggle_custom_array_fields(toggle_value):
    if toggle_value == "UCA" or toggle_value == "ULA":
        return [{'display': 'none'}, {'display': 'none'}, {'display': 'block'}]
    else:
        return [{'display': 'block'}, {
            'display': 'block'}, {'display': 'none'}]


@app.callback(
    [Output(component_id="body_ant_spacing_wavelength", component_property='children'),
     Output(
        component_id="label_ant_spacing_meter",
     component_property='children'),
     Output(component_id="ambiguity_warning", component_property='children'),
     Output(
        component_id="doa_decorrelation_method",
     component_property="options"),
     Output(
        component_id="doa_decorrelation_method",
     component_property="disabled"),
     Output(
        component_id="uca_decorrelation_warning",
     component_property="children"),
     Output(
        component_id="expected_num_of_sources",
     component_property="options"),
     Output(component_id="expected_num_of_sources", component_property="disabled"),],
    [Input(component_id="placeholder_update_freq", component_property='children'),
     Input(component_id="en_doa_check", component_property='value'),
     Input(component_id="doa_decorrelation_method", component_property='value'),
     Input(component_id="ant_spacing_meter", component_property='value'),
     Input(component_id="radio_ant_arrangement", component_property='value'),
     Input(component_id="doa_fig_type", component_property='value'),
     Input(component_id="doa_method", component_property='value'),
     Input(component_id="ula_direction", component_property='value'),
     Input(component_id="expected_num_of_sources", component_property='value'),
     Input(component_id="array_offset", component_property='value'),
     Input(component_id="compass_offset", component_property='value'),
     Input(component_id="custom_array_x_meters", component_property='value'),
     Input(component_id="custom_array_y_meters", component_property='value'),
     Input(component_id="en_peak_hold", component_property='value')],
)
def update_dsp_params(update_freq, en_doa, doa_decorrelation_method, spacing_meter, ant_arrangement, doa_fig_type, doa_method, ula_direction,
                      expected_num_of_sources, array_offset, compass_offset, custom_array_x_meters, custom_array_y_meters, en_peak_hold):  # , input_value):
    webInterface_inst.ant_spacing_meters = spacing_meter
    wavelength = 300 / webInterface_inst.daq_center_freq

    # webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength

    if ant_arrangement == "UCA":
        webInterface_inst.module_signal_processor.DOA_UCA_radius_m = webInterface_inst.ant_spacing_meters
        # Convert RADIUS to INTERELEMENT SPACING
        inter_elem_spacing = (np.sqrt(2) * webInterface_inst.ant_spacing_meters * np.sqrt(
            1 - np.cos(np.deg2rad(360 / webInterface_inst.module_signal_processor.channel_number))))
        webInterface_inst.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / wavelength
    else:
        webInterface_inst.module_signal_processor.DOA_UCA_radius_m = np.Infinity
        webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength

    ant_spacing_wavelength = round(
        webInterface_inst.module_signal_processor.DOA_inter_elem_space, 3)

    spacing_label = ""

    # Split CSV input in custom array

    webInterface_inst.custom_array_x_meters = np.float_(
        custom_array_x_meters.split(","))
    webInterface_inst.custom_array_y_meters = np.float_(
        custom_array_y_meters.split(","))

    webInterface_inst.module_signal_processor.custom_array_x = webInterface_inst.custom_array_x_meters / wavelength
    webInterface_inst.module_signal_processor.custom_array_y = webInterface_inst.custom_array_y_meters / wavelength

    # Max phase diff and ambiguity warning and Spatial smoothing control
    if ant_arrangement == "ULA":
        max_phase_diff = webInterface_inst.ant_spacing_meters / wavelength
        spacing_label = "Interelement Spacing [m]:"
    elif ant_arrangement == "UCA":
        UCA_ant_spacing = (
            np.sqrt(2) *
            webInterface_inst.ant_spacing_meters *
            np.sqrt(
                1 -
                np.cos(
                    np.deg2rad(
                        360 /
                        webInterface_inst.module_signal_processor.channel_number))))
        max_phase_diff = UCA_ant_spacing / wavelength
        spacing_label = "Array Radius [m]:"
    elif ant_arrangement == "Custom":
        max_phase_diff = 0.25  # ant_spacing_meter / wavelength
        spacing_label = "Interelement Spacing [m]"

    if max_phase_diff > 0.5:
        ambiguity_warning = "WARNING: Array size is too large for this frequency. DoA estimation is ambiguous. Max phase difference:{:.1f}°.".format(
            np.rad2deg(2 * np.pi * max_phase_diff))
    elif max_phase_diff < 0.1:
        ambiguity_warning = "WARNING: Array size may be too small.".format(
            np.rad2deg(2 * np.pi * max_phase_diff))
    else:
        ambiguity_warning = ""

    if en_doa is not None and len(en_doa):
        webInterface_inst.logger.debug("DoA estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_estimation = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_estimation = False

    webInterface_inst.module_signal_processor.DOA_algorithm = doa_method

    is_odd_number_of_channels = (
        webInterface_inst.module_signal_processor.channel_number % 2 != 0)
    is_decorrelation_applicable = (
        ant_arrangement != "Custom" and is_odd_number_of_channels)
    # UCA->VULA transformation works best if we have odd number of channels
    webInterface_inst.module_signal_processor.DOA_decorrelation_method = doa_decorrelation_method if is_decorrelation_applicable else DECORRELATION_OPTIONS[
        0]['value']

    doa_decorrelation_method_options = DECORRELATION_OPTIONS if is_decorrelation_applicable else [
        {
            **DECORRELATION_OPTION, 'label': 'N/A'
        } for DECORRELATION_OPTION in DECORRELATION_OPTIONS
    ]
    doa_decorrelation_method_state = False if is_decorrelation_applicable else True

    if ant_arrangement == "UCA" and webInterface_inst.module_signal_processor.DOA_decorrelation_method != DECORRELATION_OPTIONS[
            0]['value']:
        uca_decorrelation_warning = "WARNING: Using decorrelation methods with UCA array is still experimental as it might produce inconsistent results."
        _, L = xi(webInterface_inst.ant_spacing_meters,
                  webInterface_inst.daq_center_freq * 1.0e6)
        M = webInterface_inst.module_signal_processor.channel_number // 2
        if L < M:
            if ambiguity_warning != "":
                ambiguity_warning += "\n"
            ambiguity_warning += "WARNING: If decorrelation is used with UCA, please try to keep radius of the array as large as possible."
    else:
        uca_decorrelation_warning = ""

    webInterface_inst.module_signal_processor.DOA_ant_alignment = ant_arrangement
    webInterface_inst._doa_fig_type = doa_fig_type
    webInterface_inst.compass_offset = compass_offset
    webInterface_inst.module_signal_processor.ula_direction = ula_direction
    webInterface_inst.module_signal_processor.array_offset = array_offset

    if en_peak_hold is not None and len(en_peak_hold):
        webInterface_inst.module_signal_processor.en_peak_hold = True
    else:
        webInterface_inst.module_signal_processor.en_peak_hold = False

    webInterface_inst.module_signal_processor.DOA_expected_num_of_sources = expected_num_of_sources
    num_of_sources = [
        {
            "label": f"{c}",
            "value": c,
        } for c in range(
            1, webInterface_inst.module_signal_processor.channel_number)
    ] if doa_method == "MUSIC" else [{
        "label": 'N/A',
        "value": c,
    } for c in range(1,
                     webInterface_inst.module_signal_processor.channel_number)]

    num_of_sources_state = False if doa_method == "MUSIC" else True

    return [
        str(ant_spacing_wavelength), spacing_label, ambiguity_warning,
        doa_decorrelation_method_options, doa_decorrelation_method_state,
        uca_decorrelation_warning,
        num_of_sources, num_of_sources_state
    ]


@app.callback(
    None,
    [Input('cfg_rx_channels', 'value'),
     Input('cfg_daq_buffer_size', 'value'),
     Input('cfg_sample_rate', 'value'),
     Input('en_noise_source_ctr', 'value'),
     Input('cfg_cpi_size', 'value'),
     Input('cfg_decimation_ratio', 'value'),
     Input('cfg_fir_bw', 'value'),
     Input('cfg_fir_tap_size', 'value'),
     Input('cfg_fir_window', 'value'),
     Input('en_filter_reset', 'value'),
     Input('cfg_corr_size', 'value'),
     Input('cfg_std_ch_ind', 'value'),
     Input('en_iq_cal', 'value'),
     Input('cfg_gain_lock', 'value'),
     Input('en_req_track_lock_intervention', 'value'),
     Input('cfg_cal_track_mode', 'value'),
     Input('cfg_amplitude_cal_mode', 'value'),
     Input('cfg_cal_frame_interval', 'value'),
     Input('cfg_cal_frame_burst_size', 'value'),
     Input('cfg_amplitude_tolerance', 'value'),
     Input('cfg_phase_tolerance', 'value'),
     Input('cfg_max_sync_fails', 'value'),
     Input('cfg_data_block_len', 'value'),
     Input('cfg_recal_interval', 'value'),
     Input('cfg_en_bias_tee', 'value'),
     Input('cfg_iq_adjust_source', 'value'),
     Input('cfg_iq_adjust_amplitude', 'value'),
     Input('cfg_iq_adjust_time_delay_ns', 'value'),]
)
def update_daq_ini_params(
    cfg_rx_channels, cfg_daq_buffer_size, cfg_sample_rate, en_noise_source_ctr,
        cfg_cpi_size, cfg_decimation_ratio,
    cfg_fir_bw, cfg_fir_tap_size, cfg_fir_window, en_filter_reset, cfg_corr_size,
    cfg_std_ch_ind, en_iq_cal, cfg_gain_lock, en_req_track_lock_intervention,
    cfg_cal_track_mode, cfg_amplitude_cal_mode, cfg_cal_frame_interval,
        cfg_cal_frame_burst_size, cfg_amplitude_tolerance, cfg_phase_tolerance,
        cfg_max_sync_fails, cfg_data_block_len, cfg_recal_interval,
        cfg_en_bias_tee, cfg_iq_adjust_source, cfg_iq_adjust_amplitude, cfg_iq_adjust_time_delay_ns,
        config_fname=daq_config_filename):

    ctx = dash.callback_context
    component_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if ctx.triggered:
        if len(ctx.triggered) == 1:  # User manually changed one parameter
            webInterface_inst.tmp_daq_ini_cfg = "Custom"

        # If the input was from basic DAQ config, update the actual DAQ params
        if component_id == "cfg_data_block_len" or component_id == "cfg_recal_interval":
            if not cfg_data_block_len or not cfg_recal_interval:
                # [no_update, no_update, no_update, no_update]
                return Output('dummy_output', 'children', '')

            cfg_daq_buffer_size = 262144  # This is a reasonable DAQ buffer size to use

            decimated_bw = ((cfg_sample_rate * 10**6) /
                            cfg_decimation_ratio) / 10**3
            cfg_cpi_size = round(
                (cfg_data_block_len / 10**3) * decimated_bw * 10**3)
            cfg_cal_frame_interval = round(
                (cfg_recal_interval * 60) / (cfg_data_block_len / 10**3))

            while cfg_decimation_ratio * cfg_cpi_size < cfg_daq_buffer_size:
                cfg_daq_buffer_size = (int)(cfg_daq_buffer_size / 2)

            app.push_mods({
                'cfg_cpi_size': {'value': cfg_cpi_size},
                'cfg_cal_frame_interval': {'value': cfg_cal_frame_interval},
                'cfg_fir_tap_size': {'value': cfg_fir_tap_size},
                'cfg_daq_buffer_size': {'value': cfg_daq_buffer_size},
            })

        # If we updated advanced daq, update basic DAQ params
        elif component_id == "cfg_sample_rate" or component_id == "cfg_decimation_ratio" or component_id == "cfg_cpi_size" or component_id == "cfg_cal_frame_interval":
            if not cfg_sample_rate or not cfg_decimation_ratio or not cfg_cpi_size:
                # [no_update, no_update, no_update, no_update]
                return Output('dummy_output', 'children', '')

            decimated_bw = ((cfg_sample_rate * 10**6) /
                            cfg_decimation_ratio) / 10**3

            cfg_data_block_len = (cfg_cpi_size / (decimated_bw))
            cfg_recal_interval = (
                cfg_cal_frame_interval * (cfg_data_block_len / 10**3)) / 60

            app.push_mods({
                'cfg_data_block_len': {'value': cfg_data_block_len},
                'cfg_recal_interval': {'value': cfg_recal_interval},
            })

    # Write calculated daq params to the ini param_dict
    param_dict = webInterface_inst.daq_ini_cfg_dict
    param_dict['config_name'] = "Custom"
    param_dict['num_ch'] = cfg_rx_channels
    param_dict['en_bias_tee'] = cfg_en_bias_tee
    param_dict['daq_buffer_size'] = cfg_daq_buffer_size
    param_dict['sample_rate'] = int(cfg_sample_rate * 10**6)
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
    param_dict['require_track_lock_intervention'] = 1 if len(
        en_req_track_lock_intervention) else 0
    param_dict['cal_track_mode'] = cfg_cal_track_mode
    param_dict['amplitude_cal_mode'] = cfg_amplitude_cal_mode
    param_dict['cal_frame_interval'] = cfg_cal_frame_interval
    param_dict['cal_frame_burst_size'] = cfg_cal_frame_burst_size
    param_dict['amplitude_tolerance'] = cfg_amplitude_tolerance
    param_dict['phase_tolerance'] = cfg_phase_tolerance
    param_dict['maximum_sync_fails'] = cfg_max_sync_fails
    param_dict['iq_adjust_source'] = cfg_iq_adjust_source
    param_dict['iq_adjust_amplitude'] = cfg_iq_adjust_amplitude
    param_dict['iq_adjust_time_delay_ns'] = cfg_iq_adjust_time_delay_ns

    webInterface_inst.daq_ini_cfg_dict = param_dict


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


@app.callback([Output("url", "pathname")],
              [Input("daq_cfg_files", "value"),
              Input("placeholder_recofnig_daq", "children"),
              Input("placeholder_update_rx", "children")]
              )
def reload_cfg_page(config_fname, dummy_0, dummy_1):
    webInterface_inst.daq_ini_cfg_dict = read_config_file_dict(config_fname)
    webInterface_inst.tmp_daq_ini_cfg = webInterface_inst.daq_ini_cfg_dict['config_name']
    webInterface_inst.needs_refresh = False

    return ["/config"]


@app.callback(Output('system_control_container', 'style'),
              [Input("en_system_control", "value")]
              )
def toggle_system_control(toggle_value):
    webInterface_inst.en_system_control = toggle_value
    if toggle_value:
        return {'display': 'block'}
    else:
        return {'display': 'none'}


@app.callback([Output("placeholder_update_rx", "children")],
              [Input("settings-refresh-timer", "n_intervals")],
              [State("url", "pathname")]
              )
def settings_change_refresh(toggle_value, pathname):
    if webInterface_inst.needs_refresh:
        if pathname == "/" or pathname == "/init" or pathname == "/config":
            return ["upd"]

    return Output('dummy_output', 'children', '')


@app.callback(
    None,
    [Input(component_id="btn_reconfig_daq_chain", component_property="n_clicks")],
    [State(component_id="daq_center_freq", component_property='value'),
     State(component_id="daq_rx_gain", component_property='value')]
)
def reconfig_daq_chain(input_value, freq, gain):

    if input_value is None:
        # [no_update, no_update, no_update, no_update]
        return Output('dummy_output', 'children', '')

    # TODO: Check data interface mode here !
    #    Update DAQ Subsystem config file
    config_res, config_err = write_config_file_dict(
        webInterface_inst.daq_ini_cfg_dict, dsp_settings)
    if config_res:
        webInterface_inst.daq_cfg_ini_error = config_err[0]
        return Output("placeholder_recofnig_daq", "children", '-1')
    else:
        webInterface_inst.logger.info(
            "DAQ Subsystem configuration file edited")

    webInterface_inst.daq_restart = 1
    #    Restart DAQ Subsystem

    # Stop signal processing
    webInterface_inst.stop_processing()
    webInterface_inst.logger.debug("Signal processing stopped")

    # time.sleep(2)

    # Close control and IQ data interfaces
    webInterface_inst.close_data_interfaces()
    webInterface_inst.logger.debug("Data interfaces are closed")

    os.chdir(daq_subsystem_path)
    # Kill DAQ subsystem
    # , stdout=subprocess.DEVNULL)
    daq_stop_script = subprocess.Popen(['bash', daq_stop_filename])
    daq_stop_script.wait()
    webInterface_inst.logger.debug("DAQ Subsystem halted")

    # Start DAQ subsystem
    # , stdout=subprocess.DEVNULL)
    daq_start_script = subprocess.Popen(['bash', daq_start_filename])
    daq_start_script.wait()
    webInterface_inst.logger.debug("DAQ Subsystem restarted")

    # time.sleep(3)

    os.chdir(root_path)

    # TODO: Try this reinit method again, if it works it would save us needing
    # to restore variable states

    # Reinitialize receiver data interface
    # if webInterface_inst.module_receiver.init_data_iface() == -1:
    #    webInterface_inst.logger.critical("Failed to restart the DAQ data interface")
    #    webInterface_inst.daq_cfg_ini_error = "Failed to restart the DAQ data interface"
    # return Output('dummy_output', 'children', '') #[no_update, no_update,
    # no_update, no_update]

    # return [-1]

    # Reset channel number count
    # webInterface_inst.module_receiver.M = webInterface_inst.daq_ini_cfg_params[1]

    # webInterface_inst.module_receiver.M = 0
    # webInterface_inst.module_signal_processor.first_frame = 1

    # webInterface_inst.module_receiver.eth_connect()
    # time.sleep(2)
    # webInterface_inst.config_daq_rf(webInterface_inst.daq_center_freq, webInterface_inst.module_receiver.daq_rx_gain)

    # Recreate and reinit the receiver and signal processor modules from
    # scratch, keeping current setting values
    daq_center_freq = webInterface_inst.module_receiver.daq_center_freq
    daq_rx_gain = webInterface_inst.module_receiver.daq_rx_gain
    rec_ip_addr = webInterface_inst.module_receiver.rec_ip_addr

    DOA_ant_alignment = webInterface_inst.module_signal_processor.DOA_ant_alignment
    DOA_inter_elem_space = webInterface_inst.module_signal_processor.DOA_inter_elem_space
    en_DOA_estimation = webInterface_inst.module_signal_processor.en_DOA_estimation
    doa_decorrelation_method = webInterface_inst.module_signal_processor.DOA_decorrelation_method
    ula_direction = webInterface_inst.module_signal_processor.ula_direction

    doa_format = webInterface_inst.module_signal_processor.DOA_data_format
    doa_station_id = webInterface_inst.module_signal_processor.station_id
    doa_lat = webInterface_inst.module_signal_processor.latitude
    doa_lon = webInterface_inst.module_signal_processor.longitude
    doa_fixed_heading = webInterface_inst.module_signal_processor.fixed_heading
    doa_heading = webInterface_inst.module_signal_processor.heading
    # alt
    # speed
    doa_hasgps = webInterface_inst.module_signal_processor.hasgps
    doa_usegps = webInterface_inst.module_signal_processor.usegps
    doa_gps_connected = webInterface_inst.module_signal_processor.gps_connected
    logging_level = webInterface_inst.logging_level
    data_interface = webInterface_inst.data_interface

    webInterface_inst.module_receiver = ReceiverRTLSDR(
        data_que=webInterface_inst.rx_data_que,
        data_interface=data_interface,
        logging_level=logging_level)
    webInterface_inst.module_receiver.daq_center_freq = daq_center_freq
    # settings.uniform_gain #daq_rx_gain
    webInterface_inst.module_receiver.daq_rx_gain = daq_rx_gain
    webInterface_inst.module_receiver.rec_ip_addr = rec_ip_addr

    webInterface_inst.module_signal_processor = SignalProcessor(
        data_que=webInterface_inst.sp_data_que,
        module_receiver=webInterface_inst.module_receiver,
        logging_level=logging_level)
    webInterface_inst.module_signal_processor.DOA_ant_alignment = DOA_ant_alignment
    webInterface_inst.module_signal_processor.DOA_inter_elem_space = DOA_inter_elem_space
    webInterface_inst.module_signal_processor.en_DOA_estimation = en_DOA_estimation
    webInterface_inst.module_signal_processor.DOA_decorrelation_method = doa_decorrelation_method
    webInterface_inst.module_signal_processor.ula_direction = ula_direction

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

    webInterface_inst.module_signal_processor.start()

    # Reinit the spectrum fig, because number of traces may have changed if
    # tuner count is different
    global spectrum_fig
    spectrum_fig = init_spectrum_fig(
        webInterface_inst, fig_layout, trace_colors)

    # Restart signal processing
    webInterface_inst.start_processing()
    webInterface_inst.logger.debug("Signal processing started")
    webInterface_inst.daq_restart = 0

    webInterface_inst.daq_cfg_ini_error = ""
    # webInterface_inst.tmp_daq_ini_cfg
    webInterface_inst.active_daq_ini_cfg = webInterface_inst.daq_ini_cfg_dict['config_name']

    return Output("daq_cfg_files", "value", daq_config_filename), Output(
        "active_daq_ini_cfg", "children", "Active Configuration: " + webInterface_inst.active_daq_ini_cfg)


if __name__ == "__main__":
    # Debug mode does not work when the data interface is set to shared-memory
    # "shmem"!
    app.run_server(debug=False, host="0.0.0.0", port=8080)
