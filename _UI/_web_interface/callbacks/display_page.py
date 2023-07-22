import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import app, spectrum_fig, waterfall_fig, webInterface_inst

# isort: on
from dash_devices.dependencies import Input, Output
from kraken_web_config import generate_config_page_layout
from kraken_web_doa import generate_doa_page_layout, plot_doa
from variables import doa_fig

spectrum_page_layout = html.Div(
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


@app.callback(
    [
        Output("page-content", "children"),
        Output("header_config", "className"),
        Output("header_spectrum", "className"),
        Output("header_doa", "className"),
    ],
    [Input("url", "pathname")],
)
def display_page(pathname):
    # CHECK CONTEXT, was this called by url or timer?
    # if self.needs_refresh:
    #    self.needs_refresh = False
    global spectrum_fig
    webInterface_inst.pathname = pathname

    if pathname == "/" or pathname == "/init":
        webInterface_inst.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(webInterface_inst), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/config":
        webInterface_inst.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(webInterface_inst), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/spectrum":
        webInterface_inst.module_signal_processor.en_spectrum = True
        webInterface_inst.reset_spectrum_graph_flag = True
        return [spectrum_page_layout, "header_inactive", "header_active", "header_inactive"]
    elif pathname == "/doa":
        webInterface_inst.module_signal_processor.en_spectrum = False
        webInterface_inst.reset_doa_graph_flag = True
        plot_doa(app, webInterface_inst, doa_fig)
        return [generate_doa_page_layout(webInterface_inst), "header_inactive", "header_inactive", "header_active"]
    return Output("dummy_output", "children", "")
