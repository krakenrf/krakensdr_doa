import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import webInterface_inst

# isort: on
from variables import option

layout = html.Div(
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
                html.Div(
                    [
                        html.Div("Enable Beta Features", id="label_en_beta_features", className="field-label"),
                        dcc.Checklist(
                            options=option,
                            id="en_beta_features",
                            className="field-body",
                            value=webInterface_inst.en_beta_features,
                        ),
                    ],
                    className="field",
                ),
                html.Div("Version 1.6.1"),
            ],
            id="system_control_container",
        ),
    ],
    className="card",
)
