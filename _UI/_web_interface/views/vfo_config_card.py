import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import web_interface

# isort: on

from variables import option


def get_vfo_config_card_layout():
    # -----------------------------
    #  VFO Configuration Card
    # -----------------------------

    en_optimize_short_bursts = [1] if web_interface.module_signal_processor.optimize_short_bursts else []

    return html.Div(
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
                        value=web_interface.module_signal_processor.spectrum_fig_type,
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
                        value=web_interface.module_signal_processor.vfo_mode,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("VFO Default Squelch Mode:", id="label_vfo_default_squelch_mode", className="field-label"),
                    dcc.Dropdown(
                        id="vfo_default_squelch_mode",
                        options=[
                            {"label": "Manual", "value": "Manual"},
                            {"label": "Auto", "value": "Auto"},
                            {"label": "Auto Channel", "value": "Auto Channel"},
                        ],
                        value=web_interface.module_signal_processor.vfo_default_squelch_mode,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("VFO Default Demod:", id="label_vfo_default_demod", className="field-label"),
                            dcc.Dropdown(
                                id="vfo_default_demod",
                                options=[
                                    {"label": "None", "value": "None"},
                                    {"label": "FM", "value": "FM"},
                                ],
                                value=web_interface.module_signal_processor.vfo_default_demod,
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
                                value=web_interface.module_signal_processor.vfo_default_iq,
                                style={"display": "inline-block"},
                                className="field-body",
                            ),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Maximum Demod Time [s]:", id="label_max_demod_timeout", className="field-label"),
                            dcc.Input(
                                id="max_demod_timeout",
                                value=web_interface.module_signal_processor.max_demod_timeout,
                                type="number",
                                debounce=True,
                                className="field-body-textbox",
                                min=0,
                            ),
                        ],
                        className="field",
                    ),
                ],
                id="beta_features_container",
                style={"display": "none"},
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
                        value=web_interface.module_signal_processor.active_vfos,
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
                        value=web_interface.module_signal_processor.output_vfo,
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
                        value=web_interface.module_signal_processor.dsp_decimation,
                        type="number",
                        min=1,
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
