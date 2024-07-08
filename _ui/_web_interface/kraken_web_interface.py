import json
import logging
import queue
import time

import numpy as np

# isort: off
from variables import (
    settings_file_path,
    dsp_settings,
    DEFAULT_MAPPING_SERVER_ENDPOINT,
    AUTO_GAIN_VALUE,
    INVALID_SETTINGS_FILE_TIMESTAMP,
)

# isort: on

from dash_devices.dependencies import Input
from kraken_sdr_receiver import ReceiverRTLSDR

# Import built-in modules
from kraken_sdr_signal_processor import SignalProcessor
from utils import read_config_file_dict, settings_change_watcher


class WebInterface:
    def __init__(self):
        self.user_interface = None

        self.logging_level = dsp_settings.get("logging_level", 5) * 10
        logging.basicConfig(level=self.logging_level)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.logging_level)
        self.logger.info("Inititalizing web interface ")

        if dsp_settings["timestamp"] == INVALID_SETTINGS_FILE_TIMESTAMP:
            self.logger.warning("Settings file is not found or corrupted!")

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

        default_center_frequency_mhz = 416.588
        # Instantiate and configure Kraken SDR modules
        self.module_receiver = ReceiverRTLSDR(
            data_que=self.rx_data_que, data_interface=self.data_interface, logging_level=self.logging_level
        )
        self.module_receiver.daq_center_freq = (
            float(dsp_settings.get("center_freq", default_center_frequency_mhz)) * 10**6
        )
        self.module_receiver.daq_rx_gain = (
            float(dsp_settings.get("uniform_gain", 15.7))
            if dsp_settings.get("uniform_gain", 15.7) != "Auto"
            else AUTO_GAIN_VALUE
        )
        self.module_receiver.rec_ip_addr = dsp_settings.get("default_ip", "0.0.0.0")

        # Remote Control
        self.remote_control = dsp_settings.get("en_remote_control", False)

        self.module_signal_processor = SignalProcessor(
            data_que=self.sp_data_que, module_receiver=self.module_receiver, logging_level=self.logging_level
        )
        self.module_signal_processor.DOA_ant_alignment = dsp_settings.get("ant_arrangement", "UCA")
        self.module_signal_processor.doa_measure = self._doa_fig_type
        self.ant_spacing_meters = float(dsp_settings.get("ant_spacing_meters", 0.21))

        if self.module_signal_processor.DOA_ant_alignment == "UCA":
            self.module_signal_processor.DOA_UCA_radius_m = self.ant_spacing_meters
            # Convert RADIUS to INTERELEMENT SPACING
            inter_elem_spacing = (
                np.sqrt(2)
                * self.ant_spacing_meters
                * np.sqrt(1 - np.cos(np.deg2rad(360 / self.module_signal_processor.channel_number)))
            )
            self.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / (
                300 / float(dsp_settings.get("center_freq", 100.0))
            )
        else:
            self.module_signal_processor.DOA_UCA_radius_m = np.Infinity
            self.module_signal_processor.DOA_inter_elem_space = self.ant_spacing_meters / (
                300 / float(dsp_settings.get("center_freq", 100.0))
            )

        self.module_signal_processor.ula_direction = dsp_settings.get("ula_direction", "Both")
        self.module_signal_processor.DOA_algorithm = dsp_settings.get("doa_method", "MUSIC")
        self.module_signal_processor.DOA_expected_num_of_sources = dsp_settings.get("expected_num_of_sources", 1)

        self.custom_array_x_meters = np.float_(
            dsp_settings.get("custom_array_x_meters", "0.21,0.06,-0.17,-0.17,0.07").split(",")
        )
        self.custom_array_y_meters = np.float_(
            dsp_settings.get("custom_array_y_meters", "0.00,-0.20,-0.12,0.12,0.20").split(",")
        )
        self.module_signal_processor.custom_array_x = self.custom_array_x_meters / (
            300 / float(dsp_settings.get("center_freq", 100.0))
        )
        self.module_signal_processor.custom_array_y = self.custom_array_y_meters / (
            300 / float(dsp_settings.get("center_freq", 100.0))
        )
        self.module_signal_processor.array_offset = int(dsp_settings.get("array_offset", 0))

        self.module_signal_processor.en_DOA_estimation = dsp_settings.get("en_doa", True)
        self.module_signal_processor.DOA_decorrelation_method = dsp_settings.get("doa_decorrelation_method", "Off")

        # Output Data format.
        self.module_signal_processor.DOA_data_format = dsp_settings.get("doa_data_format", "Kraken App")

        # Station Information
        self.module_signal_processor.station_id = dsp_settings.get("station_id", "NOCALL")
        self.location_source = dsp_settings.get("location_source", "None")
        self.module_signal_processor.latitude = dsp_settings.get("latitude", 0.0)
        self.module_signal_processor.longitude = dsp_settings.get("longitude", 0.0)
        self.module_signal_processor.heading = dsp_settings.get("heading", 0.0)
        self.module_signal_processor.fixed_heading = dsp_settings.get("gps_fixed_heading", False)
        self.module_signal_processor.gps_min_speed_for_valid_heading = dsp_settings.get("gps_min_speed", 2)
        self.module_signal_processor.gps_min_duration_for_valid_heading = dsp_settings.get("gps_min_speed_duration", 3)

        # Kraken Pro Remote Key
        self.module_signal_processor.krakenpro_key = dsp_settings.get("krakenpro_key", "0ae4ca6b3")

        # Mapping Server URL
        self.mapping_server_url = dsp_settings.get("mapping_server_url", DEFAULT_MAPPING_SERVER_ENDPOINT)

        # VFO Configuration
        self.module_signal_processor.spectrum_fig_type = dsp_settings.get("spectrum_calculation", "Single")
        self.module_signal_processor.vfo_mode = dsp_settings.get("vfo_mode", "Standard")
        self.module_signal_processor.vfo_default_squelch_mode = dsp_settings.get("vfo_default_squelch_mode", "Auto")
        self.module_signal_processor.vfo_default_demod = dsp_settings.get("vfo_default_demod", "None")
        self.module_signal_processor.vfo_default_iq = dsp_settings.get("vfo_default_iq", "False")
        self.module_signal_processor.max_demod_timeout = int(dsp_settings.get("max_demod_timeout", 60))
        self.module_signal_processor.dsp_decimation = int(dsp_settings.get("dsp_decimation", 1))
        self.module_signal_processor.active_vfos = int(dsp_settings.get("active_vfos", 1))
        self.module_signal_processor.output_vfo = int(dsp_settings.get("output_vfo", 0))
        self.module_signal_processor.optimize_short_bursts = dsp_settings.get("en_optimize_short_bursts", False)
        self.module_signal_processor.en_peak_hold = dsp_settings.get("en_peak_hold", False)
        self.selected_vfo = 0
        self.module_signal_processor.vfo_default_squelch_mode = dsp_settings.get("vfo_default_squelch_mode", "Auto")

        for i in range(self.module_signal_processor.max_vfos):
            self.module_signal_processor.vfo_bw[i] = int(
                dsp_settings.get("vfo_bw_" + str(i), self.module_signal_processor.vfo_bw[i])
            )
            self.module_signal_processor.vfo_fir_order_factor[i] = int(
                dsp_settings.get("vfo_fir_order_factor_" + str(i), self.module_signal_processor.vfo_fir_order_factor[i])
            )
            self.module_signal_processor.vfo_freq[i] = float(
                dsp_settings.get("vfo_freq_" + str(i), self.module_receiver.daq_center_freq)
            )
            self.module_signal_processor.vfo_squelch_mode[i] = dsp_settings.get("vfo_squelch_mode_" + str(i), "Default")
            self.module_signal_processor.vfo_squelch[i] = int(
                dsp_settings.get("vfo_squelch_" + str(i), self.module_signal_processor.vfo_squelch[i])
            )
            self.module_signal_processor.vfo_demod[i] = dsp_settings.get("vfo_demod_" + str(i), "Default")
            self.module_signal_processor.vfo_iq[i] = dsp_settings.get("vfo_iq_" + str(i), "Default")

        self.module_signal_processor.start()

        #############################################
        #       UI Status and Config variables      #
        #############################################

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
        self.en_system_control = [1] if dsp_settings.get("en_system_control", False) else []
        self.en_beta_features = [1] if dsp_settings.get("en_beta_features", False) else []

        self.daq_ini_cfg_dict = read_config_file_dict()
        # "Default" # Holds the string identifier of the actively loaded DAQ ini configuration
        self.active_daq_ini_cfg = self.daq_ini_cfg_dict["config_name"]
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
        self.module_signal_processor.compass_offset = self.compass_offset
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
        self.needs_refresh = False

        # Basic DAQ Config
        self.decimated_bandwidth = 12.5

        if self.daq_ini_cfg_dict is not None:
            self.logger.info("Config file found and read succesfully")
            """
             Set the number of channels in the receiver module because it is required
             to produce the initial gain configuration message (Only needed in shared-memory mode)
            """
            self.module_receiver.M = self.daq_ini_cfg_dict["num_ch"]

        # Populate vfo_cfg_inputs array for VFO setting callback
        self.vfo_cfg_inputs = []
        self.vfo_cfg_inputs.append(Input(component_id="spectrum_fig_type", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="vfo_mode", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="vfo_default_squelch_mode", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="vfo_default_demod", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="vfo_default_iq", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="max_demod_timeout", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="dsp_decimation", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="active_vfos", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="output_vfo", component_property="value"))
        self.vfo_cfg_inputs.append(Input(component_id="en_optimize_short_bursts", component_property="value"))

        for i in range(self.module_signal_processor.max_vfos):
            self.vfo_cfg_inputs.append(Input(component_id="vfo_" + str(i) + "_bw", component_property="value"))
            self.vfo_cfg_inputs.append(
                Input(component_id="vfo_" + str(i) + "_fir_order_factor", component_property="value")
            )
            self.vfo_cfg_inputs.append(Input(component_id="vfo_" + str(i) + "_freq", component_property="value"))
            self.vfo_cfg_inputs.append(Input(component_id=f"vfo_squelch_mode_{i}", component_property="value"))
            self.vfo_cfg_inputs.append(Input(component_id="vfo_" + str(i) + "_squelch", component_property="value"))
            self.vfo_cfg_inputs.append(Input(component_id="vfo_" + str(i) + "_demod", component_property="value"))
            self.vfo_cfg_inputs.append(Input(component_id="vfo_" + str(i) + "_iq", component_property="value"))

        self.save_configuration()
        settings_change_watcher(self, settings_file_path)

    def save_configuration(self):
        data = {}

        # DAQ Configurations
        data["center_freq"] = self.module_receiver.daq_center_freq / 10**6
        data["uniform_gain"] = (
            self.module_receiver.daq_rx_gain if self.module_receiver.daq_rx_gain != AUTO_GAIN_VALUE else "Auto"
        )
        data["data_interface"] = dsp_settings.get("data_interface", "shmem")
        data["default_ip"] = dsp_settings.get("default_ip", "0.0.0.0")

        # Remote Control
        data["en_remote_control"] = self.remote_control

        # DOA Estimation
        data["en_doa"] = self.module_signal_processor.en_DOA_estimation
        data["ant_arrangement"] = self.module_signal_processor.DOA_ant_alignment
        data["ula_direction"] = self.module_signal_processor.ula_direction
        # self.module_signal_processor.DOA_inter_elem_space
        data["ant_spacing_meters"] = self.ant_spacing_meters
        data["custom_array_x_meters"] = ",".join(["%.2f" % num for num in self.custom_array_x_meters])
        data["custom_array_y_meters"] = ",".join(["%.2f" % num for num in self.custom_array_y_meters])
        data["array_offset"] = int(self.module_signal_processor.array_offset)

        data["doa_method"] = self.module_signal_processor.DOA_algorithm
        data["doa_decorrelation_method"] = self.module_signal_processor.DOA_decorrelation_method
        data["compass_offset"] = self.compass_offset
        data["doa_fig_type"] = self._doa_fig_type
        data["en_peak_hold"] = self.module_signal_processor.en_peak_hold
        data["expected_num_of_sources"] = self.module_signal_processor.DOA_expected_num_of_sources

        # Open System Control
        data["en_system_control"] = True if self.en_system_control == [1] else False
        data["en_beta_features"] = True if self.en_beta_features == [1] else False

        # Web Interface
        data["en_hw_check"] = dsp_settings.get("en_hw_check", 0)
        data["logging_level"] = dsp_settings.get("logging_level", 5)
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
        data["mapping_server_url"] = self.mapping_server_url
        data["rdf_mapper_server"] = self.module_signal_processor.RDF_mapper_server
        data["gps_fixed_heading"] = self.module_signal_processor.fixed_heading
        data["gps_min_speed"] = self.module_signal_processor.gps_min_speed_for_valid_heading
        data["gps_min_speed_duration"] = self.module_signal_processor.gps_min_duration_for_valid_heading

        # VFO Information
        data["spectrum_calculation"] = self.module_signal_processor.spectrum_fig_type
        data["vfo_mode"] = self.module_signal_processor.vfo_mode
        data["vfo_default_squelch_mode"] = self.module_signal_processor.vfo_default_squelch_mode
        data["vfo_default_demod"] = self.module_signal_processor.vfo_default_demod
        data["vfo_default_iq"] = self.module_signal_processor.vfo_default_iq
        data["max_demod_timeout"] = self.module_signal_processor.max_demod_timeout
        data["dsp_decimation"] = self.module_signal_processor.dsp_decimation
        data["active_vfos"] = self.module_signal_processor.active_vfos
        data["output_vfo"] = self.module_signal_processor.output_vfo
        data["en_optimize_short_bursts"] = self.module_signal_processor.optimize_short_bursts

        for i in range(self.module_signal_processor.max_vfos):
            data["vfo_bw_" + str(i)] = self.module_signal_processor.vfo_bw[i]
            data["vfo_fir_order_factor_" + str(i)] = self.module_signal_processor.vfo_fir_order_factor[i]
            data["vfo_freq_" + str(i)] = self.module_signal_processor.vfo_freq[i]
            data["vfo_squelch_mode_" + str(i)] = self.module_signal_processor.vfo_squelch_mode[i]
            data["vfo_squelch_" + str(i)] = self.module_signal_processor.vfo_squelch[i]
            data["vfo_demod_" + str(i)] = self.module_signal_processor.vfo_demod[i]
            data["vfo_iq_" + str(i)] = self.module_signal_processor.vfo_iq[i]

        data["ext_upd_flag"] = False

        with open(settings_file_path, "w") as outfile:
            json.dump(data, outfile, indent=2)

    def load_default_configuration(self):
        data = {}

        # DAQ Configurations
        data["center_freq"] = 416.588
        data["uniform_gain"] = 15.7
        data["data_interface"] = dsp_settings.get("data_interface", "shmem")
        data["default_ip"] = dsp_settings.get("default_ip", "0.0.0.0")

        # Remote Control
        data["en_remote_control"] = False

        # DOA Estimation
        data["en_doa"] = True
        data["ant_arrangement"] = "UCA"
        data["ula_direction"] = "Both"
        # self.module_signal_processor.DOA_inter_elem_space
        data["ant_spacing_meters"] = 0.21
        data["custom_array_x_meters"] = "0.21,0.06,-0.17,-0.17,0.07"
        data["custom_array_y_meters"] = "0.00,-0.20,-0.12,0.12,0.20"
        data["array_offset"] = 0

        data["doa_method"] = "MUSIC"
        data["doa_decorrelation_method"] = "Off"
        data["compass_offset"] = 0
        data["doa_fig_type"] = "Linear"
        data["en_peak_hold"] = False
        data["expected_num_of_sources"] = 1

        # Open System Control
        data["en_system_control"] = False
        data["en_beta_features"] = False

        # Web Interface
        data["en_hw_check"] = 0
        data["logging_level"] = 5
        data["disable_tooltips"] = 0

        # Output Data format. XML for Kerberos, CSV for Kracken, JSON future
        # XML, CSV, or JSON
        data["doa_data_format"] = "Kraken App"

        # Station Information
        data["station_id"] = "NOCALL"
        data["location_source"] = "None"
        data["latitude"] = 0
        data["longitude"] = 0
        data["heading"] = 0
        data["krakenpro_key"] = "cb97235a"
        data["mapping_server_url"] = "wss://map.krakenrf.com:2096"
        data["rdf_mapper_server"] = "http://MY_RDF_MAPPER_SERVER.com/save.php"
        data["gps_fixed_heading"] = False
        data["gps_min_speed"] = 2
        data["gps_min_speed_duration"] = 3

        # VFO Information
        data["spectrum_calculation"] = "Single"
        data["vfo_mode"] = "Standard"
        data["vfo_default_squelch_mode"] = "Auto"
        data["vfo_default_demod"] = "None"
        data["vfo_default_iq"] = "False"
        data["max_demod_timeout"] = 60
        data["dsp_decimation"] = 1
        data["active_vfos"] = 1
        data["output_vfo"] = 0
        data["en_optimize_short_bursts"] = False

        for i in range(self.module_signal_processor.max_vfos):
            data["vfo_bw_" + str(i)] = 12500
            data["vfo_fir_order_factor_" + str(i)] = 2
            data["vfo_freq_" + str(i)] = 416588000
            data["vfo_squelch_mode_" + str(i)] = "Default"
            data["vfo_squelch_" + str(i)] = -80
            data["vfo_demod_" + str(i)] = "Default"
            data["vfo_iq_" + str(i)] = "Default"

        data["ext_upd_flag"] = True

        with open(settings_file_path, "w") as outfile:
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

        self.logger.info("Updating receiver parameters")
        self.logger.info("Center frequency: {:f} MHz".format(f0))
        self.logger.info("Gain: {:f} dB".format(gain))
        
        
    def update_mrflo(self, input_freq):
        self.module_receiver.set_mrflo_freq(input_freq)
        
    def update_array_sel(self, array_sel):
        self.module_receiver.set_array_sel(array_sel)