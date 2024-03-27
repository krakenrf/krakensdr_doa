from configparser import ConfigParser

import dash_html_components as html
import ini_checker
from variables import daq_config_filename
from views import daq_status_card, start_stop_card, tooltips
from views.daq_config_card import get_daq_config_card_layout
from views.display_options_card import get_display_options_card_layout
from views.dsp_config_card import get_dsp_config_card_layout
from views.recording_config_card import get_recording_config_card_layout
from views.station_config_card import get_station_config_card_layout
from views.system_control_card import get_system_control_card_layout
from views.vfo_card import get_vfo_card_layout
from views.vfo_config_card import get_vfo_config_card_layout


def write_config_file_dict(web_interface, param_dict, dsp_settings):
    web_interface.logger.info("Write config file: {0}".format(param_dict))
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
    parser["daq"]["center_freq"] = str(int(web_interface.module_receiver.daq_center_freq))
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
            web_interface.logger.error(e)
        return -1, error_list
    else:
        with open(daq_config_filename, "w") as configfile:
            parser.write(configfile)
        return 0, []


# noinspection PyListCreation
def generate_config_page_layout(web_interface):
    #vfo_card = get_vfo_card_layout()
    config_page_component_list = [
        #start_stop_card.layout,
        daq_status_card.layout,
        get_daq_config_card_layout(),
        #get_vfo_config_card_layout(),
        get_dsp_config_card_layout(),
        #get_display_options_card_layout(),
        get_station_config_card_layout(),
        #get_recording_config_card_layout(),
        get_system_control_card_layout(),
    ]

    #for i in range(web_interface.module_signal_processor.max_vfos):
    #    config_page_component_list.append(vfo_card[i])

    if not web_interface.disable_tooltips:
        config_page_component_list.append(tooltips.dsp_config_tooltips)
        config_page_component_list.append(tooltips.daq_ini_config_tooltips)
        config_page_component_list.append(tooltips.station_parameters_tooltips)

    return html.Div(children=config_page_component_list)
