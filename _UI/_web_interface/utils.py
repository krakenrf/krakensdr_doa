from configparser import ConfigParser

from variables import daq_config_filename


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
