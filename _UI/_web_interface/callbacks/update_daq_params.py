import numpy as np
from dash_devices.dependencies import Input, State
from maindash import app, web_interface


@app.callback_shared(
    None,
    [Input(component_id="btn-update_rx_param", component_property="n_clicks")],
    [
        State(component_id="daq_center_freq", component_property="value"),
        State(component_id="daq_rx_gain", component_property="value"),
    ],
)
def update_daq_params(input_value, f0, gain):
    if web_interface.module_signal_processor.run_processing:
        web_interface.daq_center_freq = f0
        web_interface.config_daq_rf(f0, gain)

        for i in range(web_interface.module_signal_processor.max_vfos):
            half_band_width = (web_interface.module_signal_processor.vfo_bw[i] / 10**6) / 2
            min_freq = web_interface.daq_center_freq - web_interface.daq_fs / 2 + half_band_width
            max_freq = web_interface.daq_center_freq + web_interface.daq_fs / 2 - half_band_width
            if not (min_freq < (web_interface.module_signal_processor.vfo_freq[i] / 10**6) < max_freq):
                web_interface.module_signal_processor.vfo_freq[i] = f0
                app.push_mods({f"vfo_{i}_freq": {"value": f0}})

        wavelength = 300 / web_interface.daq_center_freq
        # web_interface.module_signal_processor.DOA_inter_elem_space = web_interface.ant_spacing_meters / wavelength

        if web_interface.module_signal_processor.DOA_ant_alignment == "UCA":
            # Convert RADIUS to INTERELEMENT SPACING
            inter_elem_spacing = (
                np.sqrt(2)
                * web_interface.ant_spacing_meters
                * np.sqrt(1 - np.cos(np.deg2rad(360 / web_interface.module_signal_processor.channel_number)))
            )
            web_interface.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / wavelength
        else:
            web_interface.module_signal_processor.DOA_inter_elem_space = web_interface.ant_spacing_meters / wavelength

        ant_spacing_wavelength = round(web_interface.module_signal_processor.DOA_inter_elem_space, 3)
        app.push_mods(
            {
                "body_ant_spacing_wavelength": {"children": str(ant_spacing_wavelength)},
            }
        )
