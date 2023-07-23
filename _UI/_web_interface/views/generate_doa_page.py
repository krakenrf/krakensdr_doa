import dash_core_components as dcc
import dash_html_components as html
from variables import doa_fig

layout = html.Div(
    [
        html.Div(
            [
                html.Div("MAX DOA Angle:", id="label_doa_max", className="field-label"),
                html.Div("deg", id="body_doa_max", className="field-body"),
            ],
            className="field",
        ),
        # html.Div([
        dcc.Graph(
            style={"height": "inherit"},
            id="doa-graph",
            figure=doa_fig,  # fig_dummy #doa_fig #fig_dummy
        ),
    ],
    style={"width": "100%", "height": "80vh"},
)
