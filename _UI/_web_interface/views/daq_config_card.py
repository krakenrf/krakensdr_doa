import os
from configparser import ConfigParser

import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import web_interface

# isort: on

from variables import (
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


def get_daq_config_card_layout():
    # Read DAQ config file
    daq_cfg_dict = web_interface.daq_ini_cfg_dict

    if daq_cfg_dict is not None:
        en_noise_src_values = [1] if daq_cfg_dict["en_noise_source_ctr"] else []
        en_filter_rst_values = [1] if daq_cfg_dict["en_filter_reset"] else []
        en_iq_cal_values = [1] if daq_cfg_dict["en_iq_cal"] else []
        en_req_track_lock_values = [1] if daq_cfg_dict["require_track_lock_intervention"] else []

        # Read available preconfig files
        preconfigs = get_preconfigs(daq_preconfigs_path)

    en_advanced_daq_cfg = [1] if web_interface.en_advanced_daq_cfg else []
    en_basic_daq_cfg = [1] if web_interface.en_basic_daq_cfg else []

    decimated_bw = ((daq_cfg_dict["sample_rate"]) / daq_cfg_dict["decimation_ratio"]) / 10**3
    cfg_data_block_len = daq_cfg_dict["cpi_size"] / (decimated_bw)
    cfg_recal_interval = (daq_cfg_dict["cal_frame_interval"] * (cfg_data_block_len / 10**3)) / 60

    if daq_cfg_dict["cal_track_mode"] == 0:  # If set to no tracking
        cfg_recal_interval = 1

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
                    value=web_interface.module_receiver.daq_center_freq / 10**6,
                    type="number",
                    min=24,
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
                    value=web_interface.module_receiver.daq_rx_gain,
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
                            "Active Configuration: " + web_interface.active_daq_ini_cfg,
                            id="active_daq_ini_cfg",
                            className="field-label",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div(
                            web_interface.daq_cfg_ini_error,
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

    return html.Div(daq_config_card_list, className="card")
