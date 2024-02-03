import json
import os
import platform
import sys

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

trace_colors = px.colors.qualitative.Plotly
trace_colors[3] = "rgb(255,255,51)"

current_path = os.path.dirname(os.path.realpath(__file__))
root_path = os.path.dirname(os.path.dirname(current_path))
shared_path = os.path.join(root_path, "_share")

INVALID_SETTINGS_FILE_TIMESTAMP = -np.inf
# Load settings file
settings_file_path = os.path.join(shared_path, "settings.json")
try:
    with open(settings_file_path, "r", encoding="utf-8") as myfile:
        dsp_settings = json.load(myfile)
except Exception:
    dsp_settings = dict()
    dsp_settings["timestamp"] = INVALID_SETTINGS_FILE_TIMESTAMP
else:
    dsp_settings["timestamp"] = os.stat(settings_file_path).st_mtime

try:
    import git

    SOFTWARE_GIT_SHORT_HASH = git.Repo().head.object.hexsha[:7]
except Exception:
    SOFTWARE_GIT_SHORT_HASH = "e5df8c9"

SOFTWARE_VERSION = "1.7.0"
SYSTEM_UNAME = platform.uname()

status_file_path = os.path.join(shared_path, "status.json")

daq_subsystem_path = os.path.join(os.path.join(os.path.dirname(root_path), "heimdall_daq_fw"), "Firmware")

daq_config_filename = os.path.join(daq_subsystem_path, "daq_chain_config.ini")

# Import Kraken SDR modules
receiver_path = os.path.join(root_path, "_sdr/_receiver")
signal_processor_path = os.path.join(root_path, "_sdr/_signal_processing")
ui_path = os.path.join(root_path, "_ui")


sys.path.insert(0, receiver_path)
sys.path.insert(0, signal_processor_path)
sys.path.insert(0, ui_path)

daq_preconfigs_path = os.path.join(os.path.join(os.path.dirname(root_path), "heimdall_daq_fw"), "config_files")
daq_config_filename = os.path.join(daq_subsystem_path, "daq_chain_config.ini")
daq_stop_filename = "daq_stop.sh"
daq_start_filename = "daq_start_sm.sh"
# daq_start_filename    = "daq_synthetic_start.sh"
sys.path.insert(0, daq_subsystem_path)

valid_fir_windows = [
    "boxcar",
    "triang",
    "blackman",
    "hamming",
    "hann",
    "bartlett",
    "flattop",
    "parzen",
    "bohman",
    "blackmanharris",
    "nuttall",
    "barthann",
]
valid_sample_rates = [0.25, 0.900001, 1.024, 1.4, 1.8, 1.92, 2.048, 2.4, 2.56, 3.2]
valid_daq_buffer_sizes = (2 ** np.arange(10, 21, 1)).tolist()
calibration_tack_modes = [["No tracking", 0], ["Periodic tracking", 2]]
doa_trace_colors = {
    "DoA Bartlett": "#00B5F7",
    "DoA Capon": "rgb(226,26,28)",
    "DoA MEM": "#1CA71C",
    "DoA TNA": "rgb(255, 0, 255)",
    "DoA MUSIC": "rgb(257,233,111)",
}
figure_font_size = 20

y = np.random.normal(0, 1, 2**1)
x = np.arange(2**1)

fig_layout = go.Layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    template="plotly_dark",
    showlegend=True,
    margin=go.layout.Margin(t=0),  # top margin
)
doa_fig = go.Figure(layout=fig_layout)

option = [{"label": "", "value": 1}]

DECORRELATION_OPTIONS = [
    {"label": "Off", "value": "Off"},
    {"label": "F-B Averaging", "value": "FBA"},
    {"label": "Toeplizification", "value": "TOEP"},
    {"label": "Spatial Smoothing", "value": "FBSS"},
    {"label": "F-B Toeplitz", "value": "FBTOEP"},
]

DOA_METHODS = [
    {"label": "Bartlett", "value": "Bartlett"},
    {"label": "Capon", "value": "Capon"},
    {"label": "MEM", "value": "MEM"},
    {"label": "TNA", "value": "TNA"},
    {"label": "MUSIC", "value": "MUSIC"},
    {"label": "ROOT-MUSIC", "value": "ROOT-MUSIC"},
]

HZ_TO_MHZ = 1.0e-6

DEFAULT_MAPPING_SERVER_ENDPOINT = "wss://map.krakenrf.com:2096"

AUTO_GAIN_VALUE = -100.0

AGC_WARNING = "WARNING: Automatic gain control might lead to erroneous results because (a) it can overshoot and overdrive ADC and (b) gains are controlled independently on each channel."
AGC_WARNING_DISABLED_STYLE = {"display": "none"}
AGC_WARNING_ENABLED_STYLE = {"color": "#f39c12", "display": "block"}
