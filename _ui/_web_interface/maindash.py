import dash_devices as dash
from kraken_web_interface import WebInterface
from kraken_web_spectrum import init_spectrum_fig
from variables import fig_layout, trace_colors
from waterfall import init_waterfall

# app = dash.Dash(__name__, suppress_callback_exceptions=True,
# compress=True, update_title="") # cannot use update_title with
# dash_devices
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Locate"
app.config.suppress_callback_exceptions = True

# app_log = logger.getLogger('werkzeug')
# app_log.setLevel(settings.logging_level*10)
# app_log.setLevel(30) # TODO: Only during dev time

#############################################
#          Prepare Dash application         #
############################################
web_interface = WebInterface()

#############################################
#       Prepare component dependencies      #
#############################################
spectrum_fig = init_spectrum_fig(web_interface, fig_layout, trace_colors)
waterfall_fig = init_waterfall(web_interface)
