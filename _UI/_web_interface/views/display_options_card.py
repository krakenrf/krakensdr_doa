import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import webInterface_inst

# isort: on

from variables import option


def get_display_options_card_layout():
    en_peak_hold = [1] if webInterface_inst.module_signal_processor.en_peak_hold else []

    # -----------------------------
    #    Display Options Card
    # -----------------------------
    return html.Div(
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
