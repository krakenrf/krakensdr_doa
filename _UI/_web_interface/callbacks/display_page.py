# isort: off
from maindash import app, web_interface

# isort: on

from dash_devices.dependencies import Input, Output
from kraken_web_config import generate_config_page_layout
from kraken_web_doa import plot_doa
from variables import doa_fig
from views import generate_doa_page, spectrum_page


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
    web_interface.pathname = pathname

    if pathname == "/" or pathname == "/init":
        web_interface.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(web_interface), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/config":
        web_interface.module_signal_processor.en_spectrum = False
        return [generate_config_page_layout(web_interface), "header_active", "header_inactive", "header_inactive"]
    elif pathname == "/spectrum":
        web_interface.module_signal_processor.en_spectrum = True
        web_interface.reset_spectrum_graph_flag = True
        return [spectrum_page.layout, "header_inactive", "header_active", "header_inactive"]
    elif pathname == "/doa":
        web_interface.module_signal_processor.en_spectrum = False
        web_interface.reset_doa_graph_flag = True
        plot_doa(app, web_interface, doa_fig)
        return [generate_doa_page.layout, "header_inactive", "header_inactive", "header_active"]
    return Output("dummy_output", "children", "")
