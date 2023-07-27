import os
import subprocess

import dash_core_components as dcc
import dash_devices as dash
import numpy as np

# isort: off
from maindash import app, spectrum_fig, waterfall_fig, web_interface

# isort: on

from dash_devices.dependencies import Input, Output, State
from kraken_web_config import write_config_file_dict
from kraken_web_spectrum import init_spectrum_fig
from krakenSDR_receiver import ReceiverRTLSDR
from krakenSDR_signal_processor import SignalProcessor, xi
from utils import (
    fetch_dsp_data,
    fetch_gps_data,
    read_config_file_dict,
    set_clicked,
    settings_change_watcher,
)
from variables import (
    DECORRELATION_OPTIONS,
    DOA_METHODS,
    current_path,
    daq_config_filename,
    daq_start_filename,
    daq_stop_filename,
    daq_subsystem_path,
    dsp_settings,
    fig_layout,
    root_path,
    settings_file_path,
    trace_colors,
)


# ============================================
#          CALLBACK FUNCTIONS
# ============================================
@app.callback_connect
def func(client, connect):
    if connect and len(app.clients) == 1:
        fetch_dsp_data(app, web_interface, spectrum_fig, waterfall_fig)
        fetch_gps_data(app, web_interface)
        settings_change_watcher(web_interface, settings_file_path)
    elif not connect and len(app.clients) == 0:
        web_interface.dsp_timer.cancel()
        web_interface.gps_timer.cancel()
        web_interface.settings_change_timer.cancel()


@app.callback_shared(
    None,
    [
        Input(component_id="filename_input", component_property="value"),
        Input(component_id="en_data_record", component_property="value"),
        Input(component_id="write_interval_input", component_property="value"),
    ],
)
def update_data_recording_params(filename, en_data_record, write_interval):
    # web_interface.module_signal_processor.data_recording_file_name = filename
    web_interface.module_signal_processor.update_recording_filename(filename)
    # TODO: Call sig processor file update function here

    if en_data_record is not None and len(en_data_record):
        web_interface.module_signal_processor.en_data_record = True
    else:
        web_interface.module_signal_processor.en_data_record = False

    web_interface.module_signal_processor.write_interval = float(write_interval)


@app.callback_shared(Output("download_recorded_file", "data"), [Input("btn_download_file", "n_clicks")])
def send_recorded_file(n_clicks):
    return dcc.send_file(
        os.path.join(
            os.path.join(
                web_interface.module_signal_processor.root_path,
                web_interface.module_signal_processor.data_recording_file_name,
            )
        )
    )


# Set DOA Output Format
@app.callback_shared(None, [Input(component_id="doa_format_type", component_property="value")])
def set_doa_format(doa_format):
    web_interface.module_signal_processor.DOA_data_format = doa_format


# Update Station ID
@app.callback_shared(None, [Input(component_id="station_id_input", component_property="value")])
def set_station_id(station_id):
    web_interface.module_signal_processor.station_id = station_id


@app.callback_shared(None, [Input(component_id="krakenpro_key", component_property="value")])
def set_kraken_pro_key(key):
    web_interface.module_signal_processor.krakenpro_key = key


@app.callback_shared(None, [Input(component_id="rdf_mapper_server_address", component_property="value")])
def set_rdf_mapper_server(url):
    web_interface.module_signal_processor.RDF_mapper_server = url


# Enable GPS Relevant fields


@app.callback(
    [Output("fixed_heading_div", "style"), Output("gps_status_info", "style")], [Input("loc_src_dropdown", "value")]
)
def toggle_gps_fields(toggle_value):
    if toggle_value == "gpsd":
        return [{"display": "block"}, {"display": "block"}]
    else:
        return [{"display": "none"}, {"display": "none"}]


# Enable of Disable Kraken Pro Key Box
@app.callback(
    [Output("krakenpro_field", "style"), Output("rdf_mapper_server_address_field", "style")],
    [Input("doa_format_type", "value")],
)
def toggle_kraken_pro_key(doa_format_type):
    kraken_pro_field_style = {"display": "block"} if doa_format_type == "Kraken Pro Remote" else {"display": "none"}
    rdf_mapper_server_address_field_style = (
        {"display": "block"}
        if doa_format_type == "RDF Mapper" or doa_format_type == "Full POST"
        else {"display": "none"}
    )
    return kraken_pro_field_style, rdf_mapper_server_address_field_style


# Enable or Disable Heading Input Fields
@app.callback(
    Output("heading_field", "style"),
    [
        Input("loc_src_dropdown", "value"),
        Input(component_id="fixed_heading_check", component_property="value"),
    ],
    [State("heading_input", component_property="value")],
)
def toggle_heading_info(static_loc, fixed_heading, heading):
    if static_loc == "Static":
        web_interface.module_signal_processor.fixed_heading = True
        web_interface.module_signal_processor.heading = heading
        return {"display": "block"}
    elif static_loc == "gpsd" and fixed_heading:
        web_interface.module_signal_processor.heading = heading
        return {"display": "block"}
    elif static_loc == "gpsd" and not fixed_heading:
        web_interface.module_signal_processor.fixed_heading = False
        return {"display": "none"}
    elif static_loc == "None":
        web_interface.module_signal_processor.fixed_heading = False
        return {"display": "none"}
    else:
        return {"display": "none"}


# Enable or Disable Location Input Fields
@app.callback(Output("location_fields", "style"), [Input("loc_src_dropdown", "value")])
def toggle_location_info(toggle_value):
    web_interface.location_source = toggle_value
    if toggle_value == "Static":
        return {"display": "block"}
    else:
        return {"display": "none"}


# Enable or Disable Location Input Fields
@app.callback(
    Output("min_speed_heading_fields", "style"),
    [Input("loc_src_dropdown", "value"), Input("fixed_heading_check", "value")],
)
def toggle_min_speed_heading_filter(toggle_value, fixed_heading):
    web_interface.location_source = toggle_value
    if toggle_value == "gpsd" and not fixed_heading:
        return {"display": "block"}
    else:
        return {"display": "none"}


# Set location data


@app.callback_shared(
    None,
    [
        Input(component_id="latitude_input", component_property="value"),
        Input(component_id="longitude_input", component_property="value"),
        Input("loc_src_dropdown", "value"),
    ],
)
def set_static_location(lat, lon, toggle_value):
    if toggle_value == "Static":
        web_interface.module_signal_processor.latitude = lat
        web_interface.module_signal_processor.longitude = lon


# Enable Fixed Heading
@app.callback(None, [Input(component_id="fixed_heading_check", component_property="value")])
def set_fixed_heading(fixed):
    if fixed:
        web_interface.module_signal_processor.fixed_heading = True
    else:
        web_interface.module_signal_processor.fixed_heading = False


# Set heading data
@app.callback_shared(None, [Input(component_id="heading_input", component_property="value")])
def set_static_heading(heading):
    web_interface.module_signal_processor.heading = heading


# Set minimum speed for trustworthy GPS heading
@app.callback_shared(None, [Input(component_id="min_speed_input", component_property="value")])
def set_min_speed_for_valid_gps_heading(min_speed):
    web_interface.module_signal_processor.gps_min_speed_for_valid_heading = min_speed


# Set minimum speed duration for trustworthy GPS heading
@app.callback_shared(None, [Input(component_id="min_speed_duration_input", component_property="value")])
def set_min_speed_duration_for_valid_gps_heading(min_speed_duration):
    web_interface.module_signal_processor.gps_min_duration_for_valid_heading = min_speed_duration


# Enable GPS (note that we need this to fire on load, so we cannot use callback_shared!)
@app.callback(
    [Output("gps_status", "children"), Output("gps_status", "style")],
    [Input("loc_src_dropdown", "value")],
)
def enable_gps(toggle_value):
    if toggle_value == "gpsd":
        status = web_interface.module_signal_processor.enable_gps()
        if status:
            web_interface.module_signal_processor.usegps = True
            return ["Connected", {"color": "#7ccc63"}]
        else:
            return ["Error", {"color": "#e74c3c"}]
    else:
        web_interface.module_signal_processor.usegps = False
        return ["-", {"color": "white"}]


@app.callback_shared(None, web_interface.vfo_cfg_inputs)
def update_vfo_params(*args):
    # Get dict of input variables
    input_names = [item.component_id for item in web_interface.vfo_cfg_inputs]
    kwargs_dict = dict(zip(input_names, args))

    web_interface.module_signal_processor.spectrum_fig_type = kwargs_dict["spectrum_fig_type"]
    web_interface.module_signal_processor.vfo_mode = kwargs_dict["vfo_mode"]
    web_interface.module_signal_processor.vfo_default_squelch_mode = kwargs_dict["vfo_default_squelch_mode"]
    web_interface.module_signal_processor.vfo_default_demod = kwargs_dict["vfo_default_demod"]
    web_interface.module_signal_processor.vfo_default_iq = kwargs_dict["vfo_default_iq"]
    web_interface.module_signal_processor.max_demod_timeout = int(kwargs_dict["max_demod_timeout"])

    active_vfos = kwargs_dict["active_vfos"]
    # If VFO mode is in the VFO-0 Auto Max mode, we active VFOs to 1 only
    if kwargs_dict["vfo_mode"] == "Auto":
        active_vfos = 1
        app.push_mods({"active_vfos": {"value": 1}})

    web_interface.module_signal_processor.dsp_decimation = max(int(kwargs_dict["dsp_decimation"]), 1)
    web_interface.module_signal_processor.active_vfos = active_vfos
    web_interface.module_signal_processor.output_vfo = kwargs_dict["output_vfo"]

    en_optimize_short_bursts = kwargs_dict["en_optimize_short_bursts"]
    if en_optimize_short_bursts is not None and len(en_optimize_short_bursts):
        web_interface.module_signal_processor.optimize_short_bursts = True
    else:
        web_interface.module_signal_processor.optimize_short_bursts = False

    for i in range(web_interface.module_signal_processor.max_vfos):
        if i < kwargs_dict["active_vfos"]:
            app.push_mods({"vfo" + str(i): {"style": {"display": "block"}}})
        else:
            app.push_mods({"vfo" + str(i): {"style": {"display": "none"}}})

    if web_interface.daq_fs > 0:
        bw = web_interface.daq_fs / web_interface.module_signal_processor.dsp_decimation
        vfo_min = web_interface.daq_center_freq - bw / 2
        vfo_max = web_interface.daq_center_freq + bw / 2

        for i in range(web_interface.module_signal_processor.max_vfos):
            web_interface.module_signal_processor.vfo_bw[i] = int(
                min(kwargs_dict["vfo_" + str(i) + "_bw"], bw * 10**6)
            )
            web_interface.module_signal_processor.vfo_fir_order_factor[i] = int(
                kwargs_dict["vfo_" + str(i) + "_fir_order_factor"]
            )
            web_interface.module_signal_processor.vfo_freq[i] = int(
                max(min(kwargs_dict["vfo_" + str(i) + "_freq"], vfo_max), vfo_min) * 10**6
            )
            web_interface.module_signal_processor.vfo_squelch_mode[i] = kwargs_dict[f"vfo_squelch_mode_{i}"]
            web_interface.module_signal_processor.vfo_squelch[i] = int(kwargs_dict["vfo_" + str(i) + "_squelch"])
            web_interface.module_signal_processor.vfo_demod[i] = kwargs_dict[f"vfo_{i}_demod"]
            web_interface.module_signal_processor.vfo_iq[i] = kwargs_dict[f"vfo_{i}_iq"]


@app.callback_shared(
    None,
    [Input(component_id="btn-start_proc", component_property="n_clicks")],
)
def start_proc_btn(input_value):
    web_interface.logger.info("Start pocessing btn pushed")
    web_interface.start_processing()


@app.callback_shared(
    None,
    [Input(component_id="btn-stop_proc", component_property="n_clicks")],
)
def stop_proc_btn(input_value):
    web_interface.logger.info("Stop pocessing btn pushed")
    web_interface.stop_processing()


@app.callback_shared(
    None,
    [Input(component_id="btn-save_cfg", component_property="n_clicks")],
)
def save_config_btn(input_value):
    web_interface.logger.info("Saving DAQ and DSP Configuration")
    web_interface.save_configuration()


@app.callback_shared(
    None,
    [Input(component_id="btn-restart_sw", component_property="n_clicks")],
)
def restart_sw_btn(input_value):
    web_interface.logger.info("Restarting Software")
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
    os.chdir(root_path)
    subprocess.Popen(["bash", "kraken_doa_start.sh"])  # ,


@app.callback_shared(
    None,
    [Input(component_id="btn-restart_system", component_property="n_clicks")],
)
def restart_system_btn(input_value):
    web_interface.logger.info("Restarting System")
    subprocess.call(["reboot"])


@app.callback_shared(
    None,
    [Input(component_id="btn-shtudown_system", component_property="n_clicks")],
)
def shutdown_system_btn(input_value):
    web_interface.logger.info("Shutting System Down")
    subprocess.call(["shutdown", "now"])


@app.callback_shared(
    None,
    [Input(component_id="btn-clear_cache", component_property="n_clicks")],
)
def clear_cache_btn(input_value):
    web_interface.logger.info("Clearing Python and Numba Caches")
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
    os.chdir(root_path)
    subprocess.Popen(["bash", "kraken_doa_start.sh", "-c"])  # ,


@app.callback_shared(None, [Input("spectrum-graph", "clickData")])
def click_to_set_freq_spectrum(clickData):
    set_clicked(web_interface, clickData)


@app.callback_shared(None, [Input("waterfall-graph", "clickData")])
def click_to_set_waterfall_spectrum(clickData):
    set_clicked(web_interface, clickData)


# Enable custom input fields
@app.callback(
    [Output("customx", "style"), Output("customy", "style"), Output("antspacing", "style")],
    [Input("radio_ant_arrangement", "value")],
)
def toggle_custom_array_fields(toggle_value):
    if toggle_value == "UCA" or toggle_value == "ULA":
        return [{"display": "none"}, {"display": "none"}, {"display": "block"}]
    else:
        return [{"display": "block"}, {"display": "block"}, {"display": "none"}]


# Fallback to MUSIC if "Custom" arrangement is selected for ROOT-MUSIC
@app.callback(
    [Output("doa_method", "value")],
    [Input("radio_ant_arrangement", "value")],
)
def fallback_custom_array_to_music(toggle_value):
    if toggle_value == "Custom" and web_interface.module_signal_processor.DOA_algorithm == "ROOT-MUSIC":
        return ["MUSIC"]
    else:
        return [web_interface.module_signal_processor.DOA_algorithm]


# Disable ROOT-MUSIC if "Custom" arrangement is selected
@app.callback(
    [Output("doa_method", "options")],
    [Input("radio_ant_arrangement", "value")],
)
def disable_root_music_for_custom_array(toggle_value):
    if toggle_value == "Custom":
        return [
            [
                dict(doa_method, disabled=True)
                if doa_method["value"] == "ROOT-MUSIC"
                else dict(doa_method, disabled=False)
                for doa_method in DOA_METHODS
            ]
        ]
    else:
        return [[dict(doa_method, disabled=False) for doa_method in DOA_METHODS]]


@app.callback(
    [
        Output(component_id="body_ant_spacing_wavelength", component_property="children"),
        Output(component_id="label_ant_spacing_meter", component_property="children"),
        Output(component_id="ambiguity_warning", component_property="children"),
        Output(component_id="doa_decorrelation_method", component_property="options"),
        Output(component_id="doa_decorrelation_method", component_property="disabled"),
        Output(component_id="uca_decorrelation_warning", component_property="children"),
        Output(component_id="uca_root_music_warning", component_property="children"),
        Output(component_id="expected_num_of_sources", component_property="options"),
        Output(component_id="expected_num_of_sources", component_property="disabled"),
    ],
    [
        Input(component_id="placeholder_update_freq", component_property="children"),
        Input(component_id="en_doa_check", component_property="value"),
        Input(component_id="doa_decorrelation_method", component_property="value"),
        Input(component_id="ant_spacing_meter", component_property="value"),
        Input(component_id="radio_ant_arrangement", component_property="value"),
        Input(component_id="doa_fig_type", component_property="value"),
        Input(component_id="doa_method", component_property="value"),
        Input(component_id="ula_direction", component_property="value"),
        Input(component_id="expected_num_of_sources", component_property="value"),
        Input(component_id="array_offset", component_property="value"),
        Input(component_id="compass_offset", component_property="value"),
        Input(component_id="custom_array_x_meters", component_property="value"),
        Input(component_id="custom_array_y_meters", component_property="value"),
        Input(component_id="en_peak_hold", component_property="value"),
    ],
)
def update_dsp_params(
    update_freq,
    en_doa,
    doa_decorrelation_method,
    spacing_meter,
    ant_arrangement,
    doa_fig_type,
    doa_method,
    ula_direction,
    expected_num_of_sources,
    array_offset,
    compass_offset,
    custom_array_x_meters,
    custom_array_y_meters,
    en_peak_hold,
):  # , input_value):
    web_interface.ant_spacing_meters = spacing_meter
    wavelength = 300 / web_interface.daq_center_freq

    # web_interface.module_signal_processor.DOA_inter_elem_space = web_interface.ant_spacing_meters / wavelength

    if ant_arrangement == "UCA":
        web_interface.module_signal_processor.DOA_UCA_radius_m = web_interface.ant_spacing_meters
        # Convert RADIUS to INTERELEMENT SPACING
        inter_elem_spacing = (
            np.sqrt(2)
            * web_interface.ant_spacing_meters
            * np.sqrt(1 - np.cos(np.deg2rad(360 / web_interface.module_signal_processor.channel_number)))
        )
        web_interface.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / wavelength
    else:
        web_interface.module_signal_processor.DOA_UCA_radius_m = np.Infinity
        web_interface.module_signal_processor.DOA_inter_elem_space = web_interface.ant_spacing_meters / wavelength

    ant_spacing_wavelength = round(web_interface.module_signal_processor.DOA_inter_elem_space, 3)

    spacing_label = ""

    # Split CSV input in custom array

    web_interface.custom_array_x_meters = np.float_(custom_array_x_meters.split(","))
    web_interface.custom_array_y_meters = np.float_(custom_array_y_meters.split(","))

    web_interface.module_signal_processor.custom_array_x = web_interface.custom_array_x_meters / wavelength
    web_interface.module_signal_processor.custom_array_y = web_interface.custom_array_y_meters / wavelength

    # Max phase diff and ambiguity warning and Spatial smoothing control
    if ant_arrangement == "ULA":
        max_phase_diff = web_interface.ant_spacing_meters / wavelength
        spacing_label = "Interelement Spacing [m]:"
    elif ant_arrangement == "UCA":
        UCA_ant_spacing = (
            np.sqrt(2)
            * web_interface.ant_spacing_meters
            * np.sqrt(1 - np.cos(np.deg2rad(360 / web_interface.module_signal_processor.channel_number)))
        )
        max_phase_diff = UCA_ant_spacing / wavelength
        spacing_label = "Array Radius [m]:"
    elif ant_arrangement == "Custom":
        max_phase_diff = 0.25  # ant_spacing_meter / wavelength
        spacing_label = "Interelement Spacing [m]"

    if max_phase_diff > 0.5:
        ambiguity_warning = "WARNING: Array size is too large for this frequency. DoA estimation is ambiguous. Max phase difference:{:.1f}°.".format(
            np.rad2deg(2 * np.pi * max_phase_diff)
        )
    elif max_phase_diff < 0.1:
        ambiguity_warning = "WARNING: Array size may be too small.  Max phase difference: {:.1f}°.".format(
            np.rad2deg(2 * np.pi * max_phase_diff)
        )
    else:
        ambiguity_warning = ""

    if en_doa is not None and len(en_doa):
        web_interface.logger.debug("DoA estimation enabled")
        web_interface.module_signal_processor.en_DOA_estimation = True
    else:
        web_interface.module_signal_processor.en_DOA_estimation = False

    web_interface.module_signal_processor.DOA_algorithm = doa_method

    is_odd_number_of_channels = web_interface.module_signal_processor.channel_number % 2 != 0
    # UCA->VULA transformation works best if we have odd number of channels
    is_decorrelation_applicable = ant_arrangement != "Custom" and is_odd_number_of_channels
    web_interface.module_signal_processor.DOA_decorrelation_method = (
        doa_decorrelation_method if is_decorrelation_applicable else DECORRELATION_OPTIONS[0]["value"]
    )

    doa_decorrelation_method_options = (
        DECORRELATION_OPTIONS
        if is_decorrelation_applicable
        else [{**DECORRELATION_OPTION, "label": "N/A"} for DECORRELATION_OPTION in DECORRELATION_OPTIONS]
    )
    doa_decorrelation_method_state = False if is_decorrelation_applicable else True

    if (
        ant_arrangement == "UCA"
        and web_interface.module_signal_processor.DOA_decorrelation_method != DECORRELATION_OPTIONS[0]["value"]
    ):
        uca_decorrelation_warning = "WARNING: Using decorrelation methods with UCA array is still experimental as it might produce inconsistent results."
        _, L = xi(web_interface.ant_spacing_meters, web_interface.daq_center_freq * 1.0e6)
        M = web_interface.module_signal_processor.channel_number // 2
        if L < M:
            if ambiguity_warning != "":
                ambiguity_warning += "\n"
            ambiguity_warning += "WARNING: If decorrelation is used with UCA, please try to keep radius of the array as large as possible."
    else:
        uca_decorrelation_warning = ""

    if ant_arrangement == "UCA" and doa_method == "ROOT-MUSIC":
        uca_root_music_warning = "WARNING: Using ROOT-MUSIC method with UCA array is still experimental as it might produce inconsistent results."
    elif ant_arrangement == "Custom" and doa_method == "ROOT-MUSIC":
        uca_root_music_warning = "WARNING: ROOT-MUSIC cannot be used with 'Custom' antenna arrangement."
    else:
        uca_root_music_warning = ""

    web_interface.module_signal_processor.DOA_ant_alignment = ant_arrangement
    web_interface._doa_fig_type = doa_fig_type
    web_interface.module_signal_processor.doa_measure = doa_fig_type
    web_interface.compass_offset = compass_offset
    web_interface.module_signal_processor.compass_offset = compass_offset
    web_interface.module_signal_processor.ula_direction = ula_direction
    web_interface.module_signal_processor.array_offset = array_offset

    if en_peak_hold is not None and len(en_peak_hold):
        web_interface.module_signal_processor.en_peak_hold = True
    else:
        web_interface.module_signal_processor.en_peak_hold = False

    web_interface.module_signal_processor.DOA_expected_num_of_sources = expected_num_of_sources
    num_of_sources = (
        [
            {
                "label": f"{c}",
                "value": c,
            }
            for c in range(1, web_interface.module_signal_processor.channel_number)
        ]
        if "MUSIC" in doa_method
        else [
            {
                "label": "N/A",
                "value": c,
            }
            for c in range(1, web_interface.module_signal_processor.channel_number)
        ]
    )

    num_of_sources_state = False if "MUSIC" in doa_method else True

    return [
        str(ant_spacing_wavelength),
        spacing_label,
        ambiguity_warning,
        doa_decorrelation_method_options,
        doa_decorrelation_method_state,
        uca_decorrelation_warning,
        uca_root_music_warning,
        num_of_sources,
        num_of_sources_state,
    ]


@app.callback(
    None,
    [
        Input("cfg_rx_channels", "value"),
        Input("cfg_daq_buffer_size", "value"),
        Input("cfg_sample_rate", "value"),
        Input("en_noise_source_ctr", "value"),
        Input("cfg_cpi_size", "value"),
        Input("cfg_decimation_ratio", "value"),
        Input("cfg_fir_bw", "value"),
        Input("cfg_fir_tap_size", "value"),
        Input("cfg_fir_window", "value"),
        Input("en_filter_reset", "value"),
        Input("cfg_corr_size", "value"),
        Input("cfg_std_ch_ind", "value"),
        Input("en_iq_cal", "value"),
        Input("cfg_gain_lock", "value"),
        Input("en_req_track_lock_intervention", "value"),
        Input("cfg_cal_track_mode", "value"),
        Input("cfg_amplitude_cal_mode", "value"),
        Input("cfg_cal_frame_interval", "value"),
        Input("cfg_cal_frame_burst_size", "value"),
        Input("cfg_amplitude_tolerance", "value"),
        Input("cfg_phase_tolerance", "value"),
        Input("cfg_max_sync_fails", "value"),
        Input("cfg_data_block_len", "value"),
        Input("cfg_recal_interval", "value"),
        Input("cfg_en_bias_tee", "value"),
        Input("cfg_iq_adjust_source", "value"),
        Input("cfg_iq_adjust_amplitude", "value"),
        Input("cfg_iq_adjust_time_delay_ns", "value"),
    ],
)
def update_daq_ini_params(
    cfg_rx_channels,
    cfg_daq_buffer_size,
    cfg_sample_rate,
    en_noise_source_ctr,
    cfg_cpi_size,
    cfg_decimation_ratio,
    cfg_fir_bw,
    cfg_fir_tap_size,
    cfg_fir_window,
    en_filter_reset,
    cfg_corr_size,
    cfg_std_ch_ind,
    en_iq_cal,
    cfg_gain_lock,
    en_req_track_lock_intervention,
    cfg_cal_track_mode,
    cfg_amplitude_cal_mode,
    cfg_cal_frame_interval,
    cfg_cal_frame_burst_size,
    cfg_amplitude_tolerance,
    cfg_phase_tolerance,
    cfg_max_sync_fails,
    cfg_data_block_len,
    cfg_recal_interval,
    cfg_en_bias_tee,
    cfg_iq_adjust_source,
    cfg_iq_adjust_amplitude,
    cfg_iq_adjust_time_delay_ns,
    config_fname=daq_config_filename,
):
    ctx = dash.callback_context
    component_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if ctx.triggered:
        if len(ctx.triggered) == 1:  # User manually changed one parameter
            web_interface.tmp_daq_ini_cfg = "Custom"

        # If the input was from basic DAQ config, update the actual DAQ params
        if component_id == "cfg_data_block_len" or component_id == "cfg_recal_interval":
            if not cfg_data_block_len or not cfg_recal_interval:
                # [no_update, no_update, no_update, no_update]
                return Output("dummy_output", "children", "")

            cfg_daq_buffer_size = 262144  # This is a reasonable DAQ buffer size to use

            decimated_bw = ((cfg_sample_rate * 10**6) / cfg_decimation_ratio) / 10**3
            cfg_cpi_size = round((cfg_data_block_len / 10**3) * decimated_bw * 10**3)
            cfg_cal_frame_interval = round((cfg_recal_interval * 60) / (cfg_data_block_len / 10**3))

            while cfg_decimation_ratio * cfg_cpi_size < cfg_daq_buffer_size:
                cfg_daq_buffer_size = (int)(cfg_daq_buffer_size / 2)

            app.push_mods(
                {
                    "cfg_cpi_size": {"value": cfg_cpi_size},
                    "cfg_cal_frame_interval": {"value": cfg_cal_frame_interval},
                    "cfg_fir_tap_size": {"value": cfg_fir_tap_size},
                    "cfg_daq_buffer_size": {"value": cfg_daq_buffer_size},
                }
            )

        # If we updated advanced daq, update basic DAQ params
        elif (
            component_id == "cfg_sample_rate"
            or component_id == "cfg_decimation_ratio"
            or component_id == "cfg_cpi_size"
            or component_id == "cfg_cal_frame_interval"
        ):
            if not cfg_sample_rate or not cfg_decimation_ratio or not cfg_cpi_size:
                # [no_update, no_update, no_update, no_update]
                return Output("dummy_output", "children", "")

            decimated_bw = ((cfg_sample_rate * 10**6) / cfg_decimation_ratio) / 10**3

            cfg_data_block_len = cfg_cpi_size / (decimated_bw)
            cfg_recal_interval = (cfg_cal_frame_interval * (cfg_data_block_len / 10**3)) / 60

            app.push_mods(
                {
                    "cfg_data_block_len": {"value": cfg_data_block_len},
                    "cfg_recal_interval": {"value": cfg_recal_interval},
                }
            )

    # Write calculated daq params to the ini param_dict
    param_dict = web_interface.daq_ini_cfg_dict
    param_dict["config_name"] = "Custom"
    param_dict["num_ch"] = cfg_rx_channels
    param_dict["en_bias_tee"] = cfg_en_bias_tee
    param_dict["daq_buffer_size"] = cfg_daq_buffer_size
    param_dict["sample_rate"] = int(cfg_sample_rate * 10**6)
    param_dict["en_noise_source_ctr"] = 1 if len(en_noise_source_ctr) else 0
    param_dict["cpi_size"] = cfg_cpi_size
    param_dict["decimation_ratio"] = cfg_decimation_ratio
    param_dict["fir_relative_bandwidth"] = cfg_fir_bw
    param_dict["fir_tap_size"] = cfg_fir_tap_size
    param_dict["fir_window"] = cfg_fir_window
    param_dict["en_filter_reset"] = 1 if len(en_filter_reset) else 0
    param_dict["corr_size"] = cfg_corr_size
    param_dict["std_ch_ind"] = cfg_std_ch_ind
    param_dict["en_iq_cal"] = 1 if len(en_iq_cal) else 0
    param_dict["gain_lock_interval"] = cfg_gain_lock
    param_dict["require_track_lock_intervention"] = 1 if len(en_req_track_lock_intervention) else 0
    param_dict["cal_track_mode"] = cfg_cal_track_mode
    param_dict["amplitude_cal_mode"] = cfg_amplitude_cal_mode
    param_dict["cal_frame_interval"] = cfg_cal_frame_interval
    param_dict["cal_frame_burst_size"] = cfg_cal_frame_burst_size
    param_dict["amplitude_tolerance"] = cfg_amplitude_tolerance
    param_dict["phase_tolerance"] = cfg_phase_tolerance
    param_dict["maximum_sync_fails"] = cfg_max_sync_fails
    param_dict["iq_adjust_source"] = cfg_iq_adjust_source
    param_dict["iq_adjust_amplitude"] = cfg_iq_adjust_amplitude
    param_dict["iq_adjust_time_delay_ns"] = cfg_iq_adjust_time_delay_ns

    web_interface.daq_ini_cfg_dict = param_dict


@app.callback(Output("adv-cfg-container", "style"), [Input("en_advanced_daq_cfg", "value")])
def toggle_adv_daq(toggle_value):
    web_interface.en_advanced_daq_cfg = toggle_value
    if toggle_value:
        return {"display": "block"}
    else:
        return {"display": "none"}


@app.callback(Output("basic-cfg-container", "style"), [Input("en_basic_daq_cfg", "value")])
def toggle_basic_daq(toggle_value):
    web_interface.en_basic_daq_cfg = toggle_value
    if toggle_value:
        return {"display": "block"}
    else:
        return {"display": "none"}


@app.callback(
    [Output("url", "pathname")],
    [
        Input("daq_cfg_files", "value"),
        Input("placeholder_recofnig_daq", "children"),
        Input("placeholder_update_rx", "children"),
    ],
)
def reload_cfg_page(config_fname, dummy_0, dummy_1):
    web_interface.daq_ini_cfg_dict = read_config_file_dict(config_fname)
    web_interface.tmp_daq_ini_cfg = web_interface.daq_ini_cfg_dict["config_name"]
    web_interface.needs_refresh = False

    return ["/config"]


@app.callback(Output("system_control_container", "style"), [Input("en_system_control", "value")])
def toggle_system_control(toggle_value):
    web_interface.en_system_control = toggle_value
    if toggle_value:
        return {"display": "block"}
    else:
        return {"display": "none"}


@app.callback(None, [Input("en_beta_features", "value")])
def toggle_beta_features(toggle_value):
    web_interface.en_beta_features = toggle_value

    toggle_output = []

    # Toggle VFO default configuration settings
    if toggle_value:
        toggle_output.append(Output("beta_features_container", "style", {"display": "block"}))
    else:
        toggle_output.append(Output("beta_features_container", "style", {"display": "none"}))

    # Toggle individual VFO card settings
    for i in range(web_interface.module_signal_processor.max_vfos):
        if toggle_value:
            toggle_output.append(Output("beta_features_container " + str(i), "style", {"display": "block"}))
        else:
            toggle_output.append(Output("beta_features_container " + str(i), "style", {"display": "none"}))

    return toggle_output


@app.callback(
    [Output("placeholder_update_rx", "children")],
    [Input("settings-refresh-timer", "n_intervals")],
    [State("url", "pathname")],
)
def settings_change_refresh(toggle_value, pathname):
    if web_interface.needs_refresh:
        if pathname == "/" or pathname == "/init" or pathname == "/config":
            return ["upd"]

    return Output("dummy_output", "children", "")


@app.callback(
    None,
    [Input(component_id="btn_reconfig_daq_chain", component_property="n_clicks")],
    [
        State(component_id="daq_center_freq", component_property="value"),
        State(component_id="daq_rx_gain", component_property="value"),
    ],
)
def reconfig_daq_chain(input_value, freq, gain):
    if input_value is None:
        # [no_update, no_update, no_update, no_update]
        return Output("dummy_output", "children", "")

    # TODO: Check data interface mode here !
    #    Update DAQ Subsystem config file
    config_res, config_err = write_config_file_dict(web_interface, web_interface.daq_ini_cfg_dict, dsp_settings)
    if config_res:
        web_interface.daq_cfg_ini_error = config_err[0]
        return Output("placeholder_recofnig_daq", "children", "-1")
    else:
        web_interface.logger.info("DAQ Subsystem configuration file edited")

    web_interface.daq_restart = 1
    #    Restart DAQ Subsystem

    # Stop signal processing
    web_interface.stop_processing()
    web_interface.logger.debug("Signal processing stopped")

    # time.sleep(2)

    # Close control and IQ data interfaces
    web_interface.close_data_interfaces()
    web_interface.logger.debug("Data interfaces are closed")

    os.chdir(daq_subsystem_path)
    # Kill DAQ subsystem
    # , stdout=subprocess.DEVNULL)
    daq_stop_script = subprocess.Popen(["bash", daq_stop_filename])
    daq_stop_script.wait()
    web_interface.logger.debug("DAQ Subsystem halted")

    # Start DAQ subsystem
    # , stdout=subprocess.DEVNULL)
    daq_start_script = subprocess.Popen(["bash", daq_start_filename])
    daq_start_script.wait()
    web_interface.logger.debug("DAQ Subsystem restarted")

    # time.sleep(3)

    os.chdir(root_path)

    # TODO: Try this reinit method again, if it works it would save us needing
    # to restore variable states

    # Reinitialize receiver data interface
    # if web_interface.module_receiver.init_data_iface() == -1:
    #    web_interface.logger.critical("Failed to restart the DAQ data interface")
    #    web_interface.daq_cfg_ini_error = "Failed to restart the DAQ data interface"
    # return Output('dummy_output', 'children', '') #[no_update, no_update,
    # no_update, no_update]

    # return [-1]

    # Reset channel number count
    # web_interface.module_receiver.M = web_interface.daq_ini_cfg_params[1]

    # web_interface.module_receiver.M = 0
    # web_interface.module_signal_processor.first_frame = 1

    # web_interface.module_receiver.eth_connect()
    # time.sleep(2)
    # web_interface.config_daq_rf(web_interface.daq_center_freq, web_interface.module_receiver.daq_rx_gain)

    # Recreate and reinit the receiver and signal processor modules from
    # scratch, keeping current setting values
    daq_center_freq = web_interface.module_receiver.daq_center_freq
    daq_rx_gain = web_interface.module_receiver.daq_rx_gain
    rec_ip_addr = web_interface.module_receiver.rec_ip_addr

    DOA_ant_alignment = web_interface.module_signal_processor.DOA_ant_alignment
    DOA_inter_elem_space = web_interface.module_signal_processor.DOA_inter_elem_space
    en_DOA_estimation = web_interface.module_signal_processor.en_DOA_estimation
    doa_decorrelation_method = web_interface.module_signal_processor.DOA_decorrelation_method
    ula_direction = web_interface.module_signal_processor.ula_direction

    doa_format = web_interface.module_signal_processor.DOA_data_format
    doa_station_id = web_interface.module_signal_processor.station_id
    doa_lat = web_interface.module_signal_processor.latitude
    doa_lon = web_interface.module_signal_processor.longitude
    doa_fixed_heading = web_interface.module_signal_processor.fixed_heading
    doa_heading = web_interface.module_signal_processor.heading
    # alt
    # speed
    doa_hasgps = web_interface.module_signal_processor.hasgps
    doa_usegps = web_interface.module_signal_processor.usegps
    doa_gps_connected = web_interface.module_signal_processor.gps_connected
    logging_level = web_interface.logging_level
    data_interface = web_interface.data_interface

    web_interface.module_receiver = ReceiverRTLSDR(
        data_que=web_interface.rx_data_que, data_interface=data_interface, logging_level=logging_level
    )
    web_interface.module_receiver.daq_center_freq = daq_center_freq
    # settings.uniform_gain #daq_rx_gain
    web_interface.module_receiver.daq_rx_gain = daq_rx_gain
    web_interface.module_receiver.rec_ip_addr = rec_ip_addr

    web_interface.module_signal_processor = SignalProcessor(
        data_que=web_interface.sp_data_que,
        module_receiver=web_interface.module_receiver,
        logging_level=logging_level,
    )
    web_interface.module_signal_processor.DOA_ant_alignment = DOA_ant_alignment
    web_interface.module_signal_processor.DOA_inter_elem_space = DOA_inter_elem_space
    web_interface.module_signal_processor.en_DOA_estimation = en_DOA_estimation
    web_interface.module_signal_processor.DOA_decorrelation_method = doa_decorrelation_method
    web_interface.module_signal_processor.ula_direction = ula_direction

    web_interface.module_signal_processor.DOA_data_format = doa_format
    web_interface.module_signal_processor.station_id = doa_station_id
    web_interface.module_signal_processor.latitude = doa_lat
    web_interface.module_signal_processor.longitude = doa_lon
    web_interface.module_signal_processor.fixed_heading = doa_fixed_heading
    web_interface.module_signal_processor.heading = doa_heading
    web_interface.module_signal_processor.hasgps = doa_hasgps
    web_interface.module_signal_processor.usegps = doa_usegps
    web_interface.module_signal_processor.gps_connected = doa_gps_connected

    # This must be here, otherwise the gains dont reinit properly?
    web_interface.module_receiver.M = web_interface.daq_ini_cfg_dict["num_ch"]
    print("M: " + str(web_interface.module_receiver.M))

    web_interface.module_signal_processor.start()

    # Reinit the spectrum fig, because number of traces may have changed if
    # tuner count is different
    global spectrum_fig
    spectrum_fig = init_spectrum_fig(web_interface, fig_layout, trace_colors)

    # Restart signal processing
    web_interface.start_processing()
    web_interface.logger.debug("Signal processing started")
    web_interface.daq_restart = 0

    web_interface.daq_cfg_ini_error = ""
    # web_interface.tmp_daq_ini_cfg
    web_interface.active_daq_ini_cfg = web_interface.daq_ini_cfg_dict["config_name"]

    return Output("daq_cfg_files", "value", daq_config_filename), Output(
        "active_daq_ini_cfg", "children", "Active Configuration: " + web_interface.active_daq_ini_cfg
    )
