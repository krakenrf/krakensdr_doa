import queue
import os
import json
import numpy as np

from threading import Timer
from configparser import ConfigParser

from krakenSDR_signal_processor import DEFAULT_VFO_FIR_ORDER_FACTOR
from kraken_web_spectrum import plot_spectrum
from kraken_web_doa import plot_doa

from variables import (
    doa_fig,
    daq_config_filename
)

def read_config_file_dict(config_fname=daq_config_filename):
    parser = ConfigParser()
    found = parser.read([config_fname])
    ini_data = {}
    if not found:
        return None

    ini_data["config_name"] = parser.get("meta", "config_name")
    ini_data["num_ch"] = parser.getint("hw", "num_ch")
    ini_data["en_bias_tee"] = parser.get("hw", "en_bias_tee")
    ini_data["daq_buffer_size"] = parser.getint("daq", "daq_buffer_size")
    ini_data["sample_rate"] = parser.getint("daq", "sample_rate")
    ini_data["en_noise_source_ctr"] = parser.getint("daq", "en_noise_source_ctr")
    ini_data["cpi_size"] = parser.getint("pre_processing", "cpi_size")
    ini_data["decimation_ratio"] = parser.getint("pre_processing", "decimation_ratio")
    ini_data["fir_relative_bandwidth"] = parser.getfloat("pre_processing", "fir_relative_bandwidth")
    ini_data["fir_tap_size"] = parser.getint("pre_processing", "fir_tap_size")
    ini_data["fir_window"] = parser.get("pre_processing", "fir_window")
    ini_data["en_filter_reset"] = parser.getint("pre_processing", "en_filter_reset")
    ini_data["corr_size"] = parser.getint("calibration", "corr_size")
    ini_data["std_ch_ind"] = parser.getint("calibration", "std_ch_ind")
    ini_data["en_iq_cal"] = parser.getint("calibration", "en_iq_cal")
    ini_data["gain_lock_interval"] = parser.getint("calibration", "gain_lock_interval")
    ini_data["require_track_lock_intervention"] = parser.getint("calibration", "require_track_lock_intervention")
    ini_data["cal_track_mode"] = parser.getint("calibration", "cal_track_mode")
    ini_data["amplitude_cal_mode"] = parser.get("calibration", "amplitude_cal_mode")
    ini_data["cal_frame_interval"] = parser.getint("calibration", "cal_frame_interval")
    ini_data["cal_frame_burst_size"] = parser.getint("calibration", "cal_frame_burst_size")
    ini_data["amplitude_tolerance"] = parser.getint("calibration", "amplitude_tolerance")
    ini_data["phase_tolerance"] = parser.getint("calibration", "phase_tolerance")
    ini_data["maximum_sync_fails"] = parser.getint("calibration", "maximum_sync_fails")
    ini_data["iq_adjust_source"] = parser.get("calibration", "iq_adjust_source")
    ini_data["iq_adjust_amplitude"] = parser.get("calibration", "iq_adjust_amplitude")
    ini_data["iq_adjust_time_delay_ns"] = parser.get("calibration", "iq_adjust_time_delay_ns")

    ini_data["adpis_gains_init"] = parser.get("adpis", "adpis_gains_init")

    ini_data["out_data_iface_type"] = parser.get("data_interface", "out_data_iface_type")

    return ini_data


def set_clicked(webInterface_inst, clickData):
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

def fetch_dsp_data(app, webInterface_inst, spectrum_fig, waterfall_fig):
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
                webInterface_inst.logger.debug("Iq header data fetched from signal processing que")
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
                webInterface_inst.daq_cpi = int(iq_header.cpi_length * 10**3 / iq_header.sampling_freq)
                gain_list_str = ""

                for m in range(iq_header.active_ant_chs):
                    gain_list_str += str(iq_header.if_gains[m] / 10)
                    gain_list_str += ", "

                webInterface_inst.daq_if_gains = gain_list_str[:-2]
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
                    avg_powers_str += "{:.1f}".format(avg_power)
                    avg_powers_str += ", "
                webInterface_inst.avg_powers = avg_powers_str[:-2]
            elif data_entry[0] == "spectrum":
                webInterface_inst.logger.debug("Spectrum data fetched from signal processing que")
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

    if (
        webInterface_inst.pathname == "/config"
        or webInterface_inst.pathname == "/"
        or webInterface_inst.pathname == "/init"
    ) and daq_status_update_flag:
        update_daq_status(app, webInterface_inst)
    elif webInterface_inst.pathname == "/spectrum" and spectrum_update_flag:
        plot_spectrum(app, webInterface_inst, spectrum_fig, waterfall_fig)
    # or (webInterface_inst.pathname == "/doa" and
    # webInterface_inst.reset_doa_graph_flag):
    elif webInterface_inst.pathname == "/doa" and doa_update_flag:
        plot_doa(app, webInterface_inst, doa_fig)

    webInterface_inst.dsp_timer = Timer(0.01, fetch_dsp_data, args=(app, webInterface_inst, spectrum_fig, waterfall_fig))
    webInterface_inst.dsp_timer.start()

def fetch_gps_data(app, webInterface_inst):
    app.push_mods(
        {
            "body_gps_latitude": {"children": webInterface_inst.module_signal_processor.latitude},
            "body_gps_longitude": {"children": webInterface_inst.module_signal_processor.longitude},
            "body_gps_heading": {"children": webInterface_inst.module_signal_processor.heading},
        }
    )

    webInterface_inst.gps_timer = Timer(1, fetch_gps_data, args=(app, webInterface_inst))
    webInterface_inst.gps_timer.start()

def settings_change_watcher(webInterface_inst, settings_file_path):
    last_changed_time = os.stat(settings_file_path).st_mtime
    time_delta = last_changed_time - webInterface_inst.last_changed_time_previous

    # Load settings file
    if time_delta > 0:  # If > 0, file was changed
        global dsp_settings
        if os.path.exists(settings_file_path):
            with open(settings_file_path, "r") as myfile:
                # update global dsp_settings, to ensureother functions using it
                # get the most up to date values??
                dsp_settings = json.loads(myfile.read())

        center_freq = float(dsp_settings.get("center_freq", 100.0))
        gain = float(dsp_settings.get("uniform_gain", 1.4))

        webInterface_inst.ant_spacing_meters = float(dsp_settings.get("ant_spacing_meters", 0.5))

        webInterface_inst.module_signal_processor.en_DOA_estimation = dsp_settings.get("en_doa", 0)
        webInterface_inst.module_signal_processor.DOA_decorrelation_method = dsp_settings.get(
            "doa_decorrelation_method", 0
        )

        webInterface_inst.module_signal_processor.DOA_ant_alignment = dsp_settings.get("ant_arrangement", "ULA")
        webInterface_inst.ant_spacing_meters = float(dsp_settings.get("ant_spacing_meters", 0.5))

        webInterface_inst.custom_array_x_meters = np.float_(
            dsp_settings.get("custom_array_x_meters", "0.1,0.2,0.3,0.4,0.5").split(",")
        )
        webInterface_inst.custom_array_y_meters = np.float_(
            dsp_settings.get("custom_array_y_meters", "0.1,0.2,0.3,0.4,0.5").split(",")
        )
        webInterface_inst.module_signal_processor.custom_array_x = webInterface_inst.custom_array_x_meters / (
            300 / webInterface_inst.module_receiver.daq_center_freq
        )
        webInterface_inst.module_signal_processor.custom_array_y = webInterface_inst.custom_array_y_meters / (
            300 / webInterface_inst.module_receiver.daq_center_freq
        )

        # Station Information
        webInterface_inst.module_signal_processor.station_id = dsp_settings.get("station_id", "NO-CALL")
        webInterface_inst.location_source = dsp_settings.get("location_source", "None")
        webInterface_inst.module_signal_processor.latitude = dsp_settings.get("latitude", 0.0)
        webInterface_inst.module_signal_processor.longitude = dsp_settings.get("longitude", 0.0)
        webInterface_inst.module_signal_processor.heading = dsp_settings.get("heading", 0.0)
        webInterface_inst.module_signal_processor.krakenpro_key = dsp_settings.get("krakenpro_key", 0.0)
        webInterface_inst.module_signal_processor.RDF_mapper_server = dsp_settings.get(
            "rdf_mapper_server", "http://RDF_MAPPER_SERVER.com/save.php"
        )

        # VFO Configuration
        webInterface_inst.module_signal_processor.spectrum_fig_type = dsp_settings.get("spectrum_calculation", "Single")
        webInterface_inst.module_signal_processor.vfo_mode = dsp_settings.get("vfo_mode", "Standard")
        webInterface_inst.module_signal_processor.vfo_default_demod = dsp_settings.get("vfo_default_demod", "None")
        webInterface_inst.module_signal_processor.vfo_default_iq = dsp_settings.get("vfo_default_iq", "False")
        webInterface_inst.module_signal_processor.max_demod_timeout = int(dsp_settings.get("max_demod_timeout", 60))
        webInterface_inst.module_signal_processor.dsp_decimation = int(dsp_settings.get("dsp_decimation", 0))
        webInterface_inst.module_signal_processor.active_vfos = int(dsp_settings.get("active_vfos", 0))
        webInterface_inst.module_signal_processor.output_vfo = int(dsp_settings.get("output_vfo", 0))
        webInterface_inst.compass_offset = dsp_settings.get("compass_offset", 0)
        webInterface_inst.module_signal_processor.compass_offset = webInterface_inst.compass_offset
        webInterface_inst.module_signal_processor.optimize_short_bursts = dsp_settings.get(
            "en_optimize_short_bursts", 0
        )
        webInterface_inst.module_signal_processor.en_peak_hold = dsp_settings.get("en_peak_hold", 0)

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            webInterface_inst.module_signal_processor.vfo_bw[i] = int(dsp_settings.get("vfo_bw_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_fir_order_factor[i] = int(
                dsp_settings.get("vfo_fir_order_factor_" + str(i), DEFAULT_VFO_FIR_ORDER_FACTOR)
            )
            webInterface_inst.module_signal_processor.vfo_freq[i] = float(dsp_settings.get("vfo_freq_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_squelch[i] = int(dsp_settings.get("vfo_squelch_" + str(i), 0))
            webInterface_inst.module_signal_processor.vfo_demod[i] = dsp_settings.get("vfo_demod_" + str(i), "Default")
            webInterface_inst.module_signal_processor.vfo_iq[i] = dsp_settings.get("vfo_iq_" + str(i), "Default")

        webInterface_inst.module_signal_processor.DOA_algorithm = dsp_settings.get("doa_method", "MUSIC")
        webInterface_inst.module_signal_processor.DOA_expected_num_of_sources = dsp_settings.get(
            "expected_num_of_sources", 1
        )
        webInterface_inst._doa_fig_type = dsp_settings.get("doa_fig_type", "Linear")
        webInterface_inst.module_signal_processor.doa_measure = webInterface_inst._doa_fig_type
        webInterface_inst.module_signal_processor.ula_direction = dsp_settings.get("ula_direction", "Both")
        webInterface_inst.module_signal_processor.array_offset = int(dsp_settings.get("array_offset", 0))

        freq_delta = webInterface_inst.daq_center_freq - center_freq
        gain_delta = webInterface_inst.module_receiver.daq_rx_gain - gain

        if abs(freq_delta) > 0.001 or abs(gain_delta) > 0.001:
            webInterface_inst.daq_center_freq = center_freq
            webInterface_inst.config_daq_rf(center_freq, gain)

        webInterface_inst.needs_refresh = True

    webInterface_inst.last_changed_time_previous = last_changed_time

    webInterface_inst.settings_change_timer = Timer(1, settings_change_watcher, args=(webInterface_inst, settings_file_path))
    webInterface_inst.settings_change_timer.start()

def update_daq_status(app, webInterface_inst):
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
        daq_update_rate_str = "{:d} ms".format(round(webInterface_inst.daq_update_rate * 1000))
    else:
        daq_update_rate_str = "{:.2f} s".format(webInterface_inst.daq_update_rate)

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
    bw = webInterface_inst.daq_fs / webInterface_inst.module_signal_processor.dsp_decimation
    dsp_decimated_bw_str = "{0:.3f}".format(bw)
    vfo_range_str = (
        "{0:.3f}".format(webInterface_inst.daq_center_freq - bw / 2)
        + " - "
        + "{0:.3f}".format(webInterface_inst.daq_center_freq + bw / 2)
    )
    daq_cpi_str = str(webInterface_inst.daq_cpi)
    daq_max_amp_str = "{:.1f}".format(webInterface_inst.max_amplitude)
    daq_avg_powers_str = webInterface_inst.avg_powers

    app.push_mods(
        {
            "body_daq_update_rate": {"children": daq_update_rate_str},
            "body_daq_dsp_latency": {"children": daq_dsp_latency},
            "body_daq_frame_index": {"children": daq_frame_index_str},
            "body_daq_frame_sync": {"children": daq_frame_sync_str},
            "body_daq_frame_type": {"children": daq_frame_type_str},
            "body_daq_power_level": {"children": daq_power_level_str},
            "body_daq_conn_status": {"children": daq_conn_status_str},
            "body_daq_delay_sync": {"children": daq_delay_sync_str},
            "body_daq_iq_sync": {"children": daq_iq_sync_str},
            "body_daq_noise_source": {"children": daq_noise_source_str},
            "body_daq_rf_center_freq": {"children": daq_rf_center_freq_str},
            "body_daq_sampling_freq": {"children": daq_sampling_freq_str},
            "body_dsp_decimated_bw": {"children": dsp_decimated_bw_str},
            "body_vfo_range": {"children": vfo_range_str},
            "body_daq_cpi": {"children": daq_cpi_str},
            "body_daq_if_gain": {"children": webInterface_inst.daq_if_gains},
            "body_max_amp": {"children": daq_max_amp_str},
            "body_avg_powers": {"children": daq_avg_powers_str},
            "gps_status": {"children": gps_en_str},
        }
    )

    app.push_mods(
        {
            "body_daq_frame_sync": {"style": frame_sync_style},
            "body_daq_frame_type": {"style": frame_type_style},
            "body_daq_power_level": {"style": daq_power_level_style},
            "body_daq_conn_status": {"style": conn_status_style},
            "body_daq_delay_sync": {"style": delay_sync_style},
            "body_daq_iq_sync": {"style": iq_sync_style},
            "body_daq_noise_source": {"style": noise_source_style},
            "gps_status": {"style": gps_en_str_style},
        }
    )

    # Update local recording file size
    recording_file_size = webInterface_inst.module_signal_processor.get_recording_filesize()
    app.push_mods({"body_file_size": {"children": recording_file_size}})