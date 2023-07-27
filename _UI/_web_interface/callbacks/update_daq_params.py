import numpy as np
from dash_devices.dependencies import Input, State
from maindash import app, webInterface_inst


@app.callback_shared(
    None,
    [Input(component_id="btn-update_rx_param", component_property="n_clicks")],
    [
        State(component_id="daq_center_freq", component_property="value"),
        State(component_id="daq_rx_gain", component_property="value"),
    ],
)
def update_daq_params(input_value, f0, gain):
    if webInterface_inst.module_signal_processor.run_processing:
        webInterface_inst.daq_center_freq = f0
        webInterface_inst.config_daq_rf(f0, gain)

        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            half_band_width = (webInterface_inst.module_signal_processor.vfo_bw[i] / 10**6) / 2
            min_freq = webInterface_inst.daq_center_freq - webInterface_inst.daq_fs / 2 + half_band_width
            max_freq = webInterface_inst.daq_center_freq + webInterface_inst.daq_fs / 2 - half_band_width
            if not (min_freq < (webInterface_inst.module_signal_processor.vfo_freq[i] / 10**6) < max_freq):
                webInterface_inst.module_signal_processor.vfo_freq[i] = f0
                app.push_mods({f"vfo_{i}_freq": {"value": f0}})

        wavelength = 300 / webInterface_inst.daq_center_freq
        # webInterface_inst.module_signal_processor.DOA_inter_elem_space = webInterface_inst.ant_spacing_meters / wavelength

        if webInterface_inst.module_signal_processor.DOA_ant_alignment == "UCA":
            # Convert RADIUS to INTERELEMENT SPACING
            inter_elem_spacing = (
                np.sqrt(2)
                * webInterface_inst.ant_spacing_meters
                * np.sqrt(1 - np.cos(np.deg2rad(360 / webInterface_inst.module_signal_processor.channel_number)))
            )
            webInterface_inst.module_signal_processor.DOA_inter_elem_space = inter_elem_spacing / wavelength
        else:
            webInterface_inst.module_signal_processor.DOA_inter_elem_space = (
                webInterface_inst.ant_spacing_meters / wavelength
            )

        ant_spacing_wavelength = round(webInterface_inst.module_signal_processor.DOA_inter_elem_space, 3)
        app.push_mods(
            {
                "body_ant_spacing_wavelength": {"children": str(ant_spacing_wavelength)},
            }
        )
