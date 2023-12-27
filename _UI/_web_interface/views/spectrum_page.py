import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import spectrum_fig, waterfall_fig

# isort: on
layout = html.Div(
    [
        html.Div(
            [
                dcc.Graph(
                    id="spectrum-graph",
                    style={"width": "100%", "height": "45%"},
                    figure=spectrum_fig,  # fig_dummy #spectrum_fig #fig_dummy
                ),
                dcc.Graph(
                    id="waterfall-graph",
                    style={"width": "100%", "height": "65%"},
                    figure=waterfall_fig,  # waterfall fig remains unchanged always due to slow speed to update entire graph #fig_dummy #spectrum_fig #fig_dummy
                ),
            ],
            style={"width": "100%", "height": "80vh"},
        ),
    ]
)
