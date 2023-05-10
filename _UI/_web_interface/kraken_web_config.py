import os
from configparser import ConfigParser

import dash_core_components as dcc
import dash_html_components as html
import ini_checker
import tooltips
from variables import (
    DECORRELATION_OPTIONS,
    calibration_tack_modes,
    daq_config_filename,
    daq_preconfigs_path,
    option,
    valid_daq_buffer_sizes,
    valid_fir_windows,
    valid_sample_rates,
)


def get_preconfigs(config_files_path):
    parser = ConfigParser()
    preconfigs = []
    preconfigs.append([daq_config_filename, "Current"])
    for root, _, files in os.walk(config_files_path):
        if len(files):
            config_file_path = os.path.join(root, files[0])
            parser.read([config_file_path])
            parameters = parser._sections
            preconfigs.append([config_file_path, parameters["meta"]["config_name"]])
    return preconfigs


def write_config_file_dict(webInterface_inst, param_dict, dsp_settings):
    webInterface_inst.logger.info("Write config file: {0}".format(param_dict))
    parser = ConfigParser()
    found = parser.read([daq_config_filename])
    if not found:
        return -1

    # DONT FORGET TO REWRITE en_bias_tee and adpis_gains_init

    parser["meta"]["config_name"] = str(param_dict["config_name"])
    parser["hw"]["num_ch"] = str(param_dict["num_ch"])
    parser["hw"]["en_bias_tee"] = str(param_dict["en_bias_tee"])
    parser["daq"]["daq_buffer_size"] = str(param_dict["daq_buffer_size"])
    parser["daq"]["sample_rate"] = str(param_dict["sample_rate"])
    parser["daq"]["en_noise_source_ctr"] = str(param_dict["en_noise_source_ctr"])
    # Set these for reconfigure
    parser["daq"]["center_freq"] = str(int(webInterface_inst.module_receiver.daq_center_freq))
    parser["pre_processing"]["cpi_size"] = str(param_dict["cpi_size"])
    parser["pre_processing"]["decimation_ratio"] = str(param_dict["decimation_ratio"])
    parser["pre_processing"]["fir_relative_bandwidth"] = str(param_dict["fir_relative_bandwidth"])
    parser["pre_processing"]["fir_tap_size"] = str(param_dict["fir_tap_size"])
    parser["pre_processing"]["fir_window"] = str(param_dict["fir_window"])
    parser["pre_processing"]["en_filter_reset"] = str(param_dict["en_filter_reset"])
    parser["calibration"]["corr_size"] = str(param_dict["corr_size"])
    parser["calibration"]["std_ch_ind"] = str(param_dict["std_ch_ind"])
    parser["calibration"]["en_iq_cal"] = str(param_dict["en_iq_cal"])
    parser["calibration"]["gain_lock_interval"] = str(param_dict["gain_lock_interval"])
    parser["calibration"]["require_track_lock_intervention"] = str(param_dict["require_track_lock_intervention"])
    parser["calibration"]["cal_track_mode"] = str(param_dict["cal_track_mode"])
    parser["calibration"]["amplitude_cal_mode"] = str(param_dict["amplitude_cal_mode"])
    parser["calibration"]["cal_frame_interval"] = str(param_dict["cal_frame_interval"])
    parser["calibration"]["cal_frame_burst_size"] = str(param_dict["cal_frame_burst_size"])
    parser["calibration"]["amplitude_tolerance"] = str(param_dict["amplitude_tolerance"])
    parser["calibration"]["phase_tolerance"] = str(param_dict["phase_tolerance"])
    parser["calibration"]["maximum_sync_fails"] = str(param_dict["maximum_sync_fails"])
    parser["calibration"]["iq_adjust_source"] = str(param_dict["iq_adjust_source"])
    parser["calibration"]["iq_adjust_amplitude"] = str(param_dict["iq_adjust_amplitude"])
    parser["calibration"]["iq_adjust_time_delay_ns"] = str(param_dict["iq_adjust_time_delay_ns"])
    parser["adpis"]["adpis_gains_init"] = str(param_dict["adpis_gains_init"])

    ini_parameters = parser._sections

    error_list = ini_checker.check_ini(ini_parameters, dsp_settings.get("en_hw_check", 0))  # settings.en_hw_check)

    if len(error_list):
        for e in error_list:
            webInterface_inst.logger.error(e)
        return -1, error_list
    else:
        with open(daq_config_filename, "w") as configfile:
            parser.write(configfile)
        return 0, []


def generate_config_page_layout(webInterface_inst):
    # Read DAQ config file
    daq_cfg_dict = webInterface_inst.daq_ini_cfg_dict

    if daq_cfg_dict is not None:
        en_noise_src_values = [1] if daq_cfg_dict["en_noise_source_ctr"] else []
        en_filter_rst_values = [1] if daq_cfg_dict["en_filter_reset"] else []
        en_iq_cal_values = [1] if daq_cfg_dict["en_iq_cal"] else []
        en_req_track_lock_values = [1] if daq_cfg_dict["require_track_lock_intervention"] else []

        # Read available preconfig files
        preconfigs = get_preconfigs(daq_preconfigs_path)

    en_data_record = [1] if webInterface_inst.module_signal_processor.en_data_record else []
    en_doa_values = [1] if webInterface_inst.module_signal_processor.en_DOA_estimation else []

    en_optimize_short_bursts = [1] if webInterface_inst.module_signal_processor.optimize_short_bursts else []
    en_peak_hold = [1] if webInterface_inst.module_signal_processor.en_peak_hold else []

    en_fixed_heading = [1] if webInterface_inst.module_signal_processor.fixed_heading else []

    en_advanced_daq_cfg = [1] if webInterface_inst.en_advanced_daq_cfg else []
    en_basic_daq_cfg = [1] if webInterface_inst.en_basic_daq_cfg else []
    # Calulcate spacings
    ant_spacing_meter = webInterface_inst.ant_spacing_meters

    decimated_bw = ((daq_cfg_dict["sample_rate"]) / daq_cfg_dict["decimation_ratio"]) / 10**3
    cfg_data_block_len = daq_cfg_dict["cpi_size"] / (decimated_bw)
    cfg_recal_interval = (daq_cfg_dict["cal_frame_interval"] * (cfg_data_block_len / 10**3)) / 60

    if daq_cfg_dict["cal_track_mode"] == 0:  # If set to no tracking
        cfg_recal_interval = 1

    # -----------------------------
    #   Start/Stop Configuration Card
    # -----------------------------
    start_stop_card = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [html.Button("Start Processing", id="btn-start_proc", className="btn_start", n_clicks=0)],
                        className="ctr_toolbar_item",
                    ),
                    html.Div(
                        [html.Button("Stop Processing", id="btn-stop_proc", className="btn_stop", n_clicks=0)],
                        className="ctr_toolbar_item",
                    ),
                    html.Div(
                        [html.Button("Save Configuration", id="btn-save_cfg", className="btn_save_cfg", n_clicks=0)],
                        className="ctr_toolbar_item",
                    ),
                ],
                className="ctr_toolbar",
            ),
        ]
    )
    # -----------------------------
    #   DAQ Configuration Card
    # -----------------------------
    # -- > Main Card Layout < --
    daq_config_card_list = [
        html.H2("RF Receiver Configuration", id="init_title_c"),
        html.Div(
            [
                html.Div("Center Frequency [MHz]:", className="field-label"),
                dcc.Input(
                    id="daq_center_freq",
                    value=webInterface_inst.module_receiver.daq_center_freq / 10**6,
                    type="number",
                    debounce=True,
                    className="field-body-textbox",
                ),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Receiver Gain:", className="field-label"),
                dcc.Dropdown(
                    id="daq_rx_gain",
                    options=[
                        {"label": "0 dB", "value": 0},
                        {"label": "0.9 dB", "value": 0.9},
                        {"label": "1.4 dB", "value": 1.4},
                        {"label": "2.7 dB", "value": 2.7},
                        {"label": "3.7 dB", "value": 3.7},
                        {"label": "7.7 dB", "value": 7.7},
                        {"label": "8.7 dB", "value": 8.7},
                        {"label": "12.5 dB", "value": 12.5},
                        {"label": "14.4 dB", "value": 14.4},
                        {"label": "15.7 dB", "value": 15.7},
                        {"label": "16.6 dB", "value": 16.6},
                        {"label": "19.7 dB", "value": 19.7},
                        {"label": "20.7 dB", "value": 20.7},
                        {"label": "22.9 dB", "value": 22.9},
                        {"label": "25.4 dB", "value": 25.4},
                        {"label": "28.0 dB", "value": 28.0},
                        {"label": "29.7 dB", "value": 29.7},
                        {"label": "32.8 dB", "value": 32.8},
                        {"label": "33.8 dB", "value": 33.8},
                        {"label": "36.4 dB", "value": 36.4},
                        {"label": "37.2 dB", "value": 37.2},
                        {"label": "38.6 dB", "value": 38.6},
                        {"label": "40.2 dB", "value": 40.2},
                        {"label": "42.1 dB", "value": 42.1},
                        {"label": "43.4 dB", "value": 43.4},
                        {"label": "43.9 dB", "value": 43.9},
                        {"label": "44.5 dB", "value": 44.5},
                        {"label": "48.0 dB", "value": 48.0},
                        {"label": "49.6 dB", "value": 49.6},
                    ],
                    value=webInterface_inst.module_receiver.daq_rx_gain,
                    clearable=False,
                    style={"display": "inline-block"},
                    className="field-body",
                ),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Button("Update Receiver Parameters", id="btn-update_rx_param", className="btn"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Basic DAQ Configuration", id="label_en_basic_daq_cfg", className="field-label"),
                dcc.Checklist(options=option, id="en_basic_daq_cfg", className="field-body", value=en_basic_daq_cfg),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div("Preconfigured DAQ Files", className="field-label"),
                        dcc.Dropdown(
                            id="daq_cfg_files",
                            options=[{"label": str(i[1]), "value": i[0]} for i in preconfigs],
                            clearable=False,
                            value=preconfigs[0][0],
                            placeholder="Select Configuration File",
                            persistence=True,
                            className="field-body-wide",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div(
                            "Active Configuration: " + webInterface_inst.active_daq_ini_cfg,
                            id="active_daq_ini_cfg",
                            className="field-label",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div(
                            webInterface_inst.daq_cfg_ini_error,
                            id="daq_ini_check",
                            className="field-label",
                            style={"color": "#e74c3c"},
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [html.Div("Basic Custom DAQ Configuration", id="label_en_basic_daq_cfg", className="field-label")]
                ),
                html.Div(
                    [
                        html.Div(
                            "Data Block Length [ms]:", id="label_daq_config_data_block_len", className="field-label"
                        ),
                        dcc.Input(
                            id="cfg_data_block_len",
                            value=cfg_data_block_len,
                            type="number",
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("Recalibration Interval [mins]:", id="label_recal_interval", className="field-label"),
                        dcc.Input(
                            id="cfg_recal_interval",
                            value=cfg_recal_interval,
                            type="number",
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div(
                            "Advanced Custom DAQ Configuration", id="label_en_advanced_daq_cfg", className="field-label"
                        ),
                        dcc.Checklist(
                            options=option, id="en_advanced_daq_cfg", className="field-body", value=en_advanced_daq_cfg
                        ),
                    ],
                    className="field",
                ),
                # --> Optional DAQ Subsystem reconfiguration fields <--
                # daq_subsystem_reconfiguration_options = [ \
                html.Div(
                    [
                        html.H2("DAQ Subsystem Reconfiguration", id="init_title_reconfig"),
                        html.H3("HW", id="cfg_group_hw"),
                        html.Div(
                            [
                                html.Div("# RX Channels:", className="field-label"),
                                dcc.Input(
                                    id="cfg_rx_channels",
                                    value=daq_cfg_dict["num_ch"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Bias Tee Control:", className="field-label"),
                                dcc.Input(
                                    id="cfg_en_bias_tee",
                                    value=daq_cfg_dict["en_bias_tee"],
                                    type="text",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.H3("DAQ", id="cfg_group_daq"),
                        html.Div(
                            [
                                html.Div("DAQ Buffer Size:", className="field-label", id="label_daq_buffer_size"),
                                dcc.Dropdown(
                                    id="cfg_daq_buffer_size",
                                    options=[{"label": i, "value": i} for i in valid_daq_buffer_sizes],
                                    value=daq_cfg_dict["daq_buffer_size"],
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Sample Rate [MHz]:", className="field-label", id="label_sample_rate"),
                                dcc.Dropdown(
                                    id="cfg_sample_rate",
                                    options=[{"label": i, "value": i} for i in valid_sample_rates],
                                    value=daq_cfg_dict["sample_rate"] / 10**6,
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Enable Noise Source Control:",
                                    className="field-label",
                                    id="label_en_noise_source_ctr",
                                ),
                                dcc.Checklist(
                                    options=option,
                                    id="en_noise_source_ctr",
                                    className="field-body",
                                    value=en_noise_src_values,
                                ),
                            ],
                            className="field",
                        ),
                        html.H3("Pre Processing"),
                        html.Div(
                            [
                                html.Div("CPI Size [sample]:", className="field-label", id="label_cpi_size"),
                                dcc.Input(
                                    id="cfg_cpi_size",
                                    value=daq_cfg_dict["cpi_size"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Decimation Ratio:", className="field-label", id="label_decimation_ratio"),
                                dcc.Input(
                                    id="cfg_decimation_ratio",
                                    value=daq_cfg_dict["decimation_ratio"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "FIR Relative Bandwidth:", className="field-label", id="label_fir_relative_bw"
                                ),
                                dcc.Input(
                                    id="cfg_fir_bw",
                                    value=daq_cfg_dict["fir_relative_bandwidth"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("FIR Tap Size:", className="field-label", id="label_fir_tap_size"),
                                dcc.Input(
                                    id="cfg_fir_tap_size",
                                    value=daq_cfg_dict["fir_tap_size"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("FIR Window:", className="field-label", id="label_fir_window"),
                                dcc.Dropdown(
                                    id="cfg_fir_window",
                                    options=[{"label": i, "value": i} for i in valid_fir_windows],
                                    value=daq_cfg_dict["fir_window"],
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Enable Filter Reset:", className="field-label", id="label_en_filter_reset"),
                                dcc.Checklist(
                                    options=option,
                                    id="en_filter_reset",
                                    className="field-body",
                                    value=en_filter_rst_values,
                                ),
                            ],
                            className="field",
                        ),
                        html.H3("Calibration"),
                        html.Div(
                            [
                                html.Div(
                                    "Correlation Size [sample]:", className="field-label", id="label_correlation_size"
                                ),
                                dcc.Input(
                                    id="cfg_corr_size",
                                    value=daq_cfg_dict["corr_size"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Standard Channel Index:", className="field-label", id="label_std_ch_index"),
                                dcc.Input(
                                    id="cfg_std_ch_ind",
                                    value=daq_cfg_dict["std_ch_ind"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Enable IQ Calibration:", className="field-label", id="label_en_iq_calibration"
                                ),
                                dcc.Checklist(
                                    options=option, id="en_iq_cal", className="field-body", value=en_iq_cal_values
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Gain Lock Interval [frame]:",
                                    className="field-label",
                                    id="label_gain_lock_interval",
                                ),
                                dcc.Input(
                                    id="cfg_gain_lock",
                                    value=daq_cfg_dict["gain_lock_interval"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Require Track Lock Intervention (For Kerberos):",
                                    className="field-label",
                                    id="label_require_track_lock",
                                ),
                                dcc.Checklist(
                                    options=option,
                                    id="en_req_track_lock_intervention",
                                    className="field-body",
                                    value=en_req_track_lock_values,
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Calibration Track Mode:",
                                    className="field-label",
                                    id="label_calibration_track_mode",
                                ),
                                dcc.Dropdown(
                                    id="cfg_cal_track_mode",
                                    options=[{"label": i[0], "value": i[1]} for i in calibration_tack_modes],
                                    value=daq_cfg_dict["cal_track_mode"],
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Amplitude Calibration Mode :",
                                    className="field-label",
                                    id="label_amplitude_calibration_mode",
                                ),
                                dcc.Dropdown(
                                    id="cfg_amplitude_cal_mode",
                                    options=[
                                        {"label": "default", "value": "default"},
                                        {"label": "disabled", "value": "disabled"},
                                        {"label": "channel_power", "value": "channel_power"},
                                    ],
                                    value=daq_cfg_dict["amplitude_cal_mode"],
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Calibration Frame Interval:",
                                    className="field-label",
                                    id="label_calibration_frame_interval",
                                ),
                                dcc.Input(
                                    id="cfg_cal_frame_interval",
                                    value=daq_cfg_dict["cal_frame_interval"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Calibration Frame Burst Size:",
                                    className="field-label",
                                    id="label_calibration_frame_burst_size",
                                ),
                                dcc.Input(
                                    id="cfg_cal_frame_burst_size",
                                    value=daq_cfg_dict["cal_frame_burst_size"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Amplitude Tolerance [dB]:", className="field-label", id="label_amplitude_tolerance"
                                ),
                                dcc.Input(
                                    id="cfg_amplitude_tolerance",
                                    value=daq_cfg_dict["amplitude_tolerance"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Phase Tolerance [deg]:", className="field-label", id="label_phase_tolerance"),
                                dcc.Input(
                                    id="cfg_phase_tolerance",
                                    value=daq_cfg_dict["phase_tolerance"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div("Maximum Sync Fails:", className="field-label", id="label_max_sync_fails"),
                                dcc.Input(
                                    id="cfg_max_sync_fails",
                                    value=daq_cfg_dict["maximum_sync_fails"],
                                    type="number",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "IQ Adjustment Source :", className="field-label", id="label_iq_adjust_source"
                                ),
                                dcc.Dropdown(
                                    id="cfg_iq_adjust_source",
                                    options=[
                                        {"label": "touchstone", "value": "touchstone"},
                                        {"label": "explicit-time-delay", "value": "explicit-time-delay"},
                                    ],
                                    value=daq_cfg_dict["iq_adjust_source"],
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "IQ Adjust Amplitude :", className="field-label", id="label_iq_adjust_amplitude"
                                ),
                                dcc.Input(
                                    id="cfg_iq_adjust_amplitude",
                                    value=daq_cfg_dict["iq_adjust_amplitude"],
                                    type="text",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "IQ Adjust Time Delay (ns) :",
                                    className="field-label",
                                    id="label_iq_adjust_time_delay_ns",
                                ),
                                dcc.Input(
                                    id="cfg_iq_adjust_time_delay_ns",
                                    value=daq_cfg_dict["iq_adjust_time_delay_ns"],
                                    type="text",
                                    debounce=True,
                                    className="field-body-textbox",
                                ),
                            ],
                            className="field",
                        ),
                    ],
                    style={"width": "100%"},
                    id="adv-cfg-container",
                ),
                # Reconfigure Button
                html.Div(
                    [
                        html.Button("Reconfigure & Restart DAQ chain", id="btn_reconfig_daq_chain", className="btn"),
                    ],
                    className="field",
                ),
            ],
            id="basic-cfg-container",
        ),
    ]

    daq_config_card = html.Div(daq_config_card_list, className="card")
    # -----------------------------
    #       DAQ Status Card
    # -----------------------------
    daq_status_card = html.Div(
        [
            html.H2("DAQ Subsystem Status", id="init_title_s"),
            html.Div(
                [
                    html.Div("Update Rate:", id="label_daq_update_rate", className="field-label"),
                    html.Div("- ms", id="body_daq_update_rate", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Latency:", id="label_daq_dsp_latency", className="field-label"),
                    html.Div("- ms", id="body_daq_dsp_latency", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Frame Index:", id="label_daq_frame_index", className="field-label"),
                    html.Div("-", id="body_daq_frame_index", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Frame Type:", id="label_daq_frame_type", className="field-label"),
                    html.Div("-", id="body_daq_frame_type", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Frame Sync:", id="label_daq_frame_sync", className="field-label"),
                    html.Div("LOSS", id="body_daq_frame_sync", className="field-body", style={"color": "#e74c3c"}),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Power Level:", id="label_daq_power_level", className="field-label"),
                    html.Div("-", id="body_daq_power_level", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Connection Status:", id="label_daq_conn_status", className="field-label"),
                    html.Div(
                        "Disconnected", id="body_daq_conn_status", className="field-body", style={"color": "#e74c3c"}
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Sample Delay Sync:", id="label_daq_delay_sync", className="field-label"),
                    html.Div("LOSS", id="body_daq_delay_sync", className="field-body", style={"color": "#e74c3c"}),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("IQ Sync:", id="label_daq_iq_sync", className="field-label"),
                    html.Div("LOSS", id="body_daq_iq_sync", className="field-body", style={"color": "#e74c3c"}),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Noise Source State:", id="label_daq_noise_source", className="field-label"),
                    html.Div(
                        "Disabled", id="body_daq_noise_source", className="field-body", style={"color": "#7ccc63"}
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Center Frequecy [MHz]:", id="label_daq_rf_center_freq", className="field-label"),
                    html.Div("- MHz", id="body_daq_rf_center_freq", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Sampling Frequency [MHz]:", id="label_daq_sampling_freq", className="field-label"),
                    html.Div("- MHz", id="body_daq_sampling_freq", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("DSP Decimated BW [MHz]:", id="label_dsp_decimated_bw", className="field-label"),
                    html.Div("- MHz", id="body_dsp_decimated_bw", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("VFO Range [MHz]:", id="label_vfo_range", className="field-label"),
                    html.Div("- MHz", id="body_vfo_range", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Data Block Length [ms]:", id="label_daq_cpi", className="field-label"),
                    html.Div("- ms", id="body_daq_cpi", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("RF Gains [dB]:", id="label_daq_if_gain", className="field-label"),
                    html.Div("[,] dB", id="body_daq_if_gain", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("VFO-0 Power [dB]:", id="label_max_amp", className="field-label"),
                    html.Div("-", id="body_max_amp", className="field-body"),
                ],
                className="field",
            ),
        ],
        className="card",
    )

    # -----------------------------
    #    DSP Confugartion Card
    # -----------------------------

    dsp_config_card = html.Div(
        [
            html.H2("DoA Configuration", id="init_title_d"),
            html.Div(
                [
                    html.Span("Array Configuration: ", id="label_ant_arrangement", className="field-label"),
                    dcc.RadioItems(
                        options=[
                            {"label": "ULA", "value": "ULA"},
                            {"label": "UCA", "value": "UCA"},
                            {"label": "Custom", "value": "Custom"},
                        ],
                        value=webInterface_inst.module_signal_processor.DOA_ant_alignment,
                        className="field-body",
                        labelStyle={"display": "inline-block", "vertical-align": "middle"},
                        id="radio_ant_arrangement",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Custom X [m]:", className="field-label"),
                    dcc.Input(
                        id="custom_array_x_meters",
                        value=",".join(["%.2f" % num for num in webInterface_inst.custom_array_x_meters]),
                        type="text",
                        debounce=True,
                        className="field-body-textbox",
                    ),
                ],
                id="customx",
                className="field",
            ),
            html.Div(
                [
                    html.Div("Custom Y [m]:", className="field-label"),
                    dcc.Input(
                        id="custom_array_y_meters",
                        value=",".join(["%.2f" % num for num in webInterface_inst.custom_array_y_meters]),
                        type="text",
                        debounce=True,
                        className="field-body-textbox",
                    ),
                ],
                id="customy",
                className="field",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("[meter]:", id="label_ant_spacing_meter", className="field-label"),
                            dcc.Input(
                                id="ant_spacing_meter",
                                value=ant_spacing_meter,
                                type="number",
                                step=0.01,
                                debounce=True,
                                className="field-body-textbox",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Wavelength Multiplier:", id="label_ant_spacing_wavelength", className="field-label"
                            ),
                            html.Div("1", id="body_ant_spacing_wavelength", className="field-body"),
                        ],
                        className="field",
                    ),
                ],
                id="antspacing",
                className="field",
            ),
            html.Div([html.Div("", id="ambiguity_warning", className="field", style={"color": "#f39c12"})]),
            # --> DoA estimation configuration checkboxes <--
            # Note: Individual checkboxes are created due to layout
            # considerations, correct if extist a better solution
            html.Div(
                [
                    html.Div("Enable DoA Estimation:", id="label_en_doa", className="field-label"),
                    dcc.Checklist(options=option, id="en_doa_check", className="field-body", value=en_doa_values),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("DoA Algorithm:", id="label_doa_method", className="field-label"),
                    dcc.Dropdown(
                        id="doa_method",
                        options=[
                            {"label": "Bartlett", "value": "Bartlett"},
                            {"label": "Capon", "value": "Capon"},
                            {"label": "MEM", "value": "MEM"},
                            {"label": "TNA", "value": "TNA"},
                            {"label": "MUSIC", "value": "MUSIC"},
                        ],
                        value=webInterface_inst.module_signal_processor.DOA_algorithm,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Decorrelation:", id="label_decorrelation", className="field-label"),
                    dcc.Dropdown(
                        id="doa_decorrelation_method",
                        options=DECORRELATION_OPTIONS,
                        value=webInterface_inst.module_signal_processor.DOA_decorrelation_method,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div([html.Div("", id="uca_decorrelation_warning", className="field", style={"color": "#f39c12"})]),
            html.Div(
                [
                    html.Div("ULA Output Direction:", id="label_ula_direction", className="field-label"),
                    dcc.Dropdown(
                        id="ula_direction",
                        options=[
                            {"label": "Both", "value": "Both"},
                            {"label": "Forward", "value": "Forward"},
                            {"label": "Backward", "value": "Backward"},
                        ],
                        value=webInterface_inst.module_signal_processor.ula_direction,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Array Offset:", id="label_array_offset", className="field-label"),
                    dcc.Input(
                        id="array_offset",
                        value=webInterface_inst.module_signal_processor.array_offset,
                        # webInterface_inst.module_signal_processor.station_id,
                        type="number",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div(
                        "Expected number of RF sources:", id="label_expected_num_of_sources", className="field-label"
                    ),
                    dcc.Dropdown(
                        id="expected_num_of_sources",
                        options=[
                            {"label": "1", "value": 1},
                            {"label": "2", "value": 2},
                            {"label": "3", "value": 3},
                            {"label": "4", "value": 4},
                        ],
                        value=webInterface_inst.module_signal_processor.DOA_expected_num_of_sources,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
        ],
        className="card",
    )

    # -----------------------------
    #    Display Options Card
    # -----------------------------
    display_options_card = html.Div(
        [
            html.H2("Display Options", id="init_title_disp"),
            html.Div(
                [
                    html.Div("DoA Graph Type:", id="label_doa_graph_type", className="field-label"),
                    dcc.Dropdown(
                        id="doa_fig_type",
                        options=[
                            {"label": "Linear", "value": "Linear"},
                            {"label": "Polar", "value": "Polar"},
                            {"label": "Compass", "value": "Compass"},
                        ],
                        value=webInterface_inst._doa_fig_type,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Compass Offset [deg]:", className="field-label"),
                    dcc.Input(
                        id="compass_offset",
                        value=webInterface_inst.compass_offset,
                        type="number",
                        debounce=True,
                        className="field-body-textbox",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Spectrum Peak Hold:", id="label_peak_hold", className="field-label"),
                    dcc.Checklist(options=option, id="en_peak_hold", className="field-body", value=en_peak_hold),
                ],
                className="field",
            ),
        ],
        className="card",
    )

    # --------------------------------
    # Misc station config parameters
    # --------------------------------
    station_config_card = html.Div(
        [
            html.H2("Station Information", id="station_conf_title"),
            html.Div(
                [
                    html.Div("Station ID:", id="station_id_label", className="field-label"),
                    dcc.Input(
                        id="station_id_input",
                        value=webInterface_inst.module_signal_processor.station_id,
                        pattern="[A-Za-z0-9\\-]*",
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("DOA Data Format:", id="doa_format_label", className="field-label"),
                    dcc.Dropdown(
                        id="doa_format_type",
                        options=[
                            {"label": "Kraken App", "value": "Kraken App"},
                            {"label": "Kraken Pro Local", "value": "Kraken Pro Local"},
                            {"label": "Kraken Pro Remote", "value": "Kraken Pro Remote"},
                            {"label": "Kerberos App", "value": "Kerberos App"},
                            {"label": "DF Aggregator", "value": "DF Aggregator"},
                            {"label": "RDF Mapper", "value": "RDF Mapper"},
                            {"label": "Full POST", "value": "Full POST"},
                        ],
                        value=webInterface_inst.module_signal_processor.DOA_data_format,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("RDF Mapper / Generic Server URL:", className="field-label"),
                    dcc.Input(
                        id="rdf_mapper_server_address",
                        value=webInterface_inst.module_signal_processor.RDF_mapper_server,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                id="rdf_mapper_server_address_field",
                className="field",
            ),
            html.Div(
                [
                    html.Div("Kraken Pro Key:", className="field-label"),
                    dcc.Input(
                        id="krakenpro_key",
                        value=webInterface_inst.module_signal_processor.krakenpro_key,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                id="krakenpro_field",
                className="field",
            ),
            html.Div(
                [
                    html.Div("Location Source:", id="location_src_label", className="field-label"),
                    dcc.Dropdown(
                        id="loc_src_dropdown",
                        options=[
                            {"label": "None", "value": "None"},
                            {"label": "Static", "value": "Static"},
                            {
                                "label": "GPS",
                                "value": "gpsd",
                                "disabled": not webInterface_inst.module_signal_processor.hasgps,
                            },
                        ],
                        value=webInterface_inst.location_source,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Fixed Heading", id="fixed_heading_label", className="field-label"),
                    dcc.Checklist(
                        options=option, id="fixed_heading_check", className="field-body", value=en_fixed_heading
                    ),
                    # html.Div("Fixed Heading:", className="field-label"),
                    # daq.BooleanSwitch(id="fixed_heading_check",
                    #                   on=webInterface_inst.module_signal_processor.fixed_heading,
                    #                   label="Use Fixed Heading",
                    #                   labelPosition="right"),
                ],
                className="field",
                id="fixed_heading_div",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Latitude:", className="field-label"),
                            dcc.Input(
                                id="latitude_input",
                                value=webInterface_inst.module_signal_processor.latitude,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                            ),
                        ],
                        id="latitude_field",
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Longitude:", className="field-label"),
                            dcc.Input(
                                id="longitude_input",
                                value=webInterface_inst.module_signal_processor.longitude,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                            ),
                        ],
                        id="logitude_field",
                        className="field",
                    ),
                ],
                id="location_fields",
            ),
            html.Div(
                [
                    html.Div("Heading:", className="field-label"),
                    dcc.Input(
                        id="heading_input",
                        value=webInterface_inst.module_signal_processor.heading,
                        type="number",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                id="heading_field",
                className="field",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("GPS:", className="field-label"),
                            html.Div("-", id="gps_status", className="field-body"),
                        ],
                        id="gps_status_field",
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Latitude:", id="label_gps_latitude", className="field-label"),
                            html.Div("-", id="body_gps_latitude", className="field-body"),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Longitude:", id="label_gps_longitude", className="field-label"),
                            html.Div("-", id="body_gps_longitude", className="field-body"),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Heading:", id="label_gps_heading", className="field-label"),
                            html.Div("-", id="body_gps_heading", className="field-body"),
                        ],
                        className="field",
                    ),
                ],
                id="gps_status_info",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Min speed for heading [m/s]:", className="field-label"),
                            dcc.Input(
                                id="min_speed_input",
                                value=webInterface_inst.module_signal_processor.gps_min_speed_for_valid_heading,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                            ),
                        ],
                        id="min_speed_field",
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Min speed duration for heading [s]", className="field-label"),
                            dcc.Input(
                                id="min_speed_duration_input",
                                value=webInterface_inst.module_signal_processor.gps_min_duration_for_valid_heading,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                            ),
                        ],
                        id="min_speed_duration_field",
                        className="field",
                    ),
                ],
                id="min_speed_heading_fields",
            ),
        ],
        className="card",
    )

    recording_config_card = html.Div(
        [
            html.H2("Local Data Recording", id="data_recording_title"),
            html.Div(
                [
                    html.Div("Filename:", id="filename_label", className="field-label"),
                    dcc.Input(
                        id="filename_input",
                        value=webInterface_inst.module_signal_processor.data_recording_file_name,
                        # webInterface_inst.module_signal_processor.station_id,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Data Format:", id="data_format_label", className="field-label"),
                    dcc.Dropdown(
                        id="data_format_type",
                        options=[
                            {"label": "Kraken App", "value": "Kraken App"},
                        ],
                        value="Kraken App",  # webInterface_inst.module_signal_processor.DOA_data_format,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Write Interval (s):", id="write_interval_label", className="field-label"),
                    dcc.Input(
                        id="write_interval_input",
                        value=webInterface_inst.module_signal_processor.write_interval,
                        # webInterface_inst.module_signal_processor.station_id,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Enable Local Data Recording:", id="label_en_data_record", className="field-label"),
                    dcc.Checklist(options=option, id="en_data_record", className="field-body", value=en_data_record),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("File Size (MB):", id="label_file_size", className="field-label"),
                    html.Div("- MB", id="body_file_size", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Button("Download File", id="btn_download_file", className="btn"),
                    dcc.Download(id="download_recorded_file"),
                ],
                className="field",
            ),
        ],
        className="card",
    )

    # -----------------------------
    #  VFO Configuration Card
    # -----------------------------
    vfo_config_card = html.Div(
        [
            html.H2("VFO Configuration", id="init_title_sq"),
            html.Div(
                [
                    html.Div("Spectrum Calculation:", id="label_spectrum_calculation", className="field-label"),
                    dcc.Dropdown(
                        id="spectrum_fig_type",
                        options=[
                            {"label": "Single Ch", "value": "Single"},
                            {"label": "All Ch (TEST ONLY)", "value": "All"},
                        ],
                        value=webInterface_inst.module_signal_processor.spectrum_fig_type,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("VFO Mode:", id="label_vfo_mode", className="field-label"),
                    dcc.Dropdown(
                        id="vfo_mode",
                        options=[
                            {"label": "Standard", "value": "Standard"},
                            {"label": "VFO-0 Auto Max", "value": "Auto"},
                        ],
                        value=webInterface_inst.module_signal_processor.vfo_mode,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("VFO Default Demod:", id="label_vfo_default_demod", className="field-label"),
                    dcc.Dropdown(
                        id="vfo_default_demod",
                        options=[
                            {"label": "None", "value": "None"},
                            {"label": "FM", "value": "FM"},
                        ],
                        value=webInterface_inst.module_signal_processor.vfo_default_demod,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("VFO Default IQ Channel:", id="label_vfo_default_iq", className="field-label"),
                    dcc.Dropdown(
                        id="vfo_default_iq",
                        options=[
                            {"label": "False", "value": "False"},
                            {"label": "True", "value": "True"},
                        ],
                        value=webInterface_inst.module_signal_processor.vfo_default_iq,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Active VFOs:", id="label_active_vfos", className="field-label"),
                    dcc.Dropdown(
                        id="active_vfos",
                        options=[
                            {"label": "1", "value": 1},
                            {"label": "2", "value": 2},
                            {"label": "3", "value": 3},
                            {"label": "4", "value": 4},
                            {"label": "5", "value": 5},
                            {"label": "6", "value": 6},
                            {"label": "7", "value": 7},
                            {"label": "8", "value": 8},
                            {"label": "9", "value": 9},
                            {"label": "10", "value": 10},
                            {"label": "11", "value": 11},
                            {"label": "12", "value": 12},
                            {"label": "13", "value": 13},
                            {"label": "14", "value": 14},
                            {"label": "15", "value": 15},
                            {"label": "16", "value": 16},
                        ],
                        value=webInterface_inst.module_signal_processor.active_vfos,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Output VFO:", id="label_output_vfo", className="field-label"),
                    dcc.Dropdown(
                        id="output_vfo",
                        options=[
                            {"label": "ALL", "value": -1},
                            {"label": "0", "value": 0},
                            {"label": "1", "value": 1},
                            {"label": "2", "value": 2},
                            {"label": "3", "value": 3},
                            {"label": "4", "value": 4},
                            {"label": "5", "value": 5},
                            {"label": "6", "value": 6},
                            {"label": "7", "value": 7},
                            {"label": "8", "value": 8},
                            {"label": "9", "value": 9},
                            {"label": "10", "value": 10},
                            {"label": "11", "value": 11},
                            {"label": "12", "value": 12},
                            {"label": "13", "value": 13},
                            {"label": "14", "value": 14},
                            {"label": "15", "value": 15},
                        ],
                        value=webInterface_inst.module_signal_processor.output_vfo,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("DSP Side Decimation:", id="label_dsp_side_decimation", className="field-label"),
                    dcc.Input(
                        id="dsp_decimation",
                        value=webInterface_inst.module_signal_processor.dsp_decimation,
                        type="number",
                        debounce=True,
                        className="field-body-textbox",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Optimize Short Bursts:", id="label_optimize_short_bursts", className="field-label"),
                    dcc.Checklist(
                        options=option,
                        id="en_optimize_short_bursts",
                        className="field-body",
                        value=en_optimize_short_bursts,
                    ),
                ],
                className="field",
            ),
        ],
        className="card",
    )

    # -----------------------------
    #  Individual VFO Configurations
    # -----------------------------
    vfo_card = [" "] * webInterface_inst.module_signal_processor.max_vfos

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        vfo_card[i] = html.Div(
            [
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Frequency [MHz]:", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_freq",
                            value=webInterface_inst.module_signal_processor.vfo_freq[i] / 10**6,
                            type="number",
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Bandwidth [Hz]:", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_bw",
                            value=webInterface_inst.module_signal_processor.vfo_bw[i],
                            type="number",
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Squelch [dB] :", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_squelch",
                            value=webInterface_inst.module_signal_processor.vfo_squelch[i],
                            type="number",
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Demod:", className="field-label"),
                        dcc.Dropdown(
                            id=f"vfo_{i}_demod",
                            options=[
                                {
                                    "label": f"Default ({webInterface_inst.module_signal_processor.vfo_default_demod})",
                                    "value": "Default",
                                },
                                {"label": "None", "value": "None"},
                                {"label": "FM", "value": "FM"},
                            ],
                            value=webInterface_inst.module_signal_processor.vfo_demod[i],
                            style={"display": "inline-block"},
                            className="field-body",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " IQ Channel:", className="field-label"),
                        dcc.Dropdown(
                            id=f"vfo_{i}_iq",
                            options=[
                                {
                                    "label": f"Default ({webInterface_inst.module_signal_processor.vfo_default_iq})",
                                    "value": "Default",
                                },
                                {"label": "False", "value": "False"},
                                {"label": "True", "value": "True"},
                            ],
                            value=webInterface_inst.module_signal_processor.vfo_iq[i],
                            style={"display": "inline-block"},
                            className="field-body",
                        ),
                    ],
                    className="field",
                ),
            ],
            id="vfo" + str(i),
            className="card",
            style={"display": "block"}
            if i < webInterface_inst.module_signal_processor.active_vfos
            else {"display": "none"},
        )

    system_control_card = html.Div(
        [
            html.Div(
                [
                    html.Div("Open System Control", id="label_en_system_control", className="field-label"),
                    dcc.Checklist(
                        options=option,
                        id="en_system_control",
                        className="field-body",
                        value=webInterface_inst.en_system_control,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div(
                        [html.Button("Restart Software", id="btn-restart_sw", className="btn-restart_sw", n_clicks=0)],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Restart System", id="btn-restart_system", className="btn-restart_system", n_clicks=0
                            )
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Shutdown System", id="btn-shtudown_system", className="btn-shtudown_system", n_clicks=0
                            )
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Clear Cache and Restart", id="btn-clear_cache", className="btn-clear_cache", n_clicks=0
                            )
                        ],
                        className="field",
                    ),
                    html.Div("Version 1.6"),
                ],
                id="system_control_container",
            ),
        ],
        className="card",
    )

    config_page_component_list = [
        start_stop_card,
        daq_status_card,
        daq_config_card,
        vfo_config_card,
        dsp_config_card,
        display_options_card,
        station_config_card,
        recording_config_card,
        system_control_card,
    ]

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        config_page_component_list.append(vfo_card[i])

    if not webInterface_inst.disable_tooltips:
        config_page_component_list.append(tooltips.dsp_config_tooltips)
        config_page_component_list.append(tooltips.daq_ini_config_tooltips)
        config_page_component_list.append(tooltips.station_parameters_tooltips)

    return html.Div(children=config_page_component_list)
