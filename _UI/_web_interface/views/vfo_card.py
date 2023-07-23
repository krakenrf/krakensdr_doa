import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import webInterface_inst


# isort: on
def get_vfo_card_layout():
    # -----------------------------
    #  Individual VFO Configurations
    # -----------------------------
    layout = [" "] * webInterface_inst.module_signal_processor.max_vfos

    for i in range(webInterface_inst.module_signal_processor.max_vfos):
        layout[i] = html.Div(
            [
                html.Div(
                    [
                        html.Div("VFO-" + str(i) + " Frequency [MHz]:", className="field-label"),
                        dcc.Input(
                            id="vfo_" + str(i) + "_freq",
                            value=webInterface_inst.module_signal_processor.vfo_freq[i] / 10**6,
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
                            value=webInterface_inst.module_signal_processor.vfo_bw[i],
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
                            value=webInterface_inst.module_signal_processor.vfo_fir_order_factor[i],
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
                    id="beta_features_container " + str(i),
                    style={"display": "none"},
                ),
            ],
            id="vfo" + str(i),
            className="card",
            style={"display": "block"}
            if i < webInterface_inst.module_signal_processor.active_vfos
            else {"display": "none"},
        )

        return layout
