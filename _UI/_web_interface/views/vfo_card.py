import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import web_interface


# isort: on
def get_vfo_card_layout():
    # -----------------------------
    #  Individual VFO Configurations
    # -----------------------------
    layout = [" "] * web_interface.module_signal_processor.max_vfos

    for i in range(web_interface.module_signal_processor.max_vfos):
        is_auto_squelch = web_interface.module_signal_processor.vfo_squelch_mode[i] in ["Auto", "Auto Channel"] or (
            web_interface.module_signal_processor.vfo_default_squelch_mode in ["Auto", "Auto Channel"]
            and web_interface.module_signal_processor.vfo_squelch_mode[i] == "Default"
        )
        layout[i] = html.Div(
            [
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Frequency [MHz]:", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_freq",
                            value=web_interface.module_signal_processor.vfo_freq[i] / 10**6,
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
                        html.Div("VFO-" + str(i) + " Bandwidth [Hz]:", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_bw",
                            value=web_interface.module_signal_processor.vfo_bw[i],
                            type="number",
                            min=100,
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " FIR Order Factor:", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_fir_order_factor",
                            value=web_interface.module_signal_processor.vfo_fir_order_factor[i],
                            type="number",
                            min=2,
                            step=1,
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Squelch Mode:", className="field-label"),
                        dcc.Dropdown(
                            id=f"vfo_squelch_mode_{i}",
                            options=[
                                {
                                    "label": f"Default ({webInterface_inst.module_signal_processor.vfo_default_squelch_mode})",
                                    "value": "Default",
                                },
                                {"label": "None", "value": "None"},
                                {"label": "Auto", "value": "Auto"},
                                {"label": "Auto Channel", "value": "Auto Channel"},
                            ],
                            value=webInterface_inst.module_signal_processor.vfo_squelch_mode[i],
                            style={"display": "inline-block"},
                            className="field-body",
                        ),
                    ],
                    className="field",
                ),
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Squelch [dB] :", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_squelch",
                            value=web_interface.module_signal_processor.vfo_squelch[i],
                            type="number",
                            debounce=True,
                            className="field-body-textbox",
                        ),
                    ],
                    style={"display": "inline-block"} if not is_auto_squelch else {"display": "none"},
                    className="field",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div("VFO-" + str(i) + " Demod:", className="field-label"),
                                dcc.Dropdown(
                                    id=f"vfo_{i}_demod",
                                    options=[
                                        {
                                            "label": f"Default ({web_interface.module_signal_processor.vfo_default_demod})",
                                            "value": "Default",
                                        },
                                        {"label": "None", "value": "None"},
                                        {"label": "FM", "value": "FM"},
                                    ],
                                    value=web_interface.module_signal_processor.vfo_demod[i],
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
                                            "label": f"Default ({web_interface.module_signal_processor.vfo_default_iq})",
                                            "value": "Default",
                                        },
                                        {"label": "False", "value": "False"},
                                        {"label": "True", "value": "True"},
                                    ],
                                    value=web_interface.module_signal_processor.vfo_iq[i],
                                    style={"display": "inline-block"},
                                    className="field-body",
                                ),
                            ],
                            className="field",
                        ),
                    ],
                    id="beta_features_container " + str(i),
                    style={"display": "none"},
                ),
            ],
            id="vfo" + str(i),
            className="card",
            style={"display": "block"}
            if i < web_interface.module_signal_processor.active_vfos
            else {"display": "none"},
        )

    return layout
