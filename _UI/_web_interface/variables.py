import os
import sys
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

trace_colors = px.colors.qualitative.Plotly
trace_colors[3] = 'rgb(255,255,51)'

current_path          = os.path.dirname(os.path.realpath(__file__))
root_path             = os.path.dirname(os.path.dirname(current_path))

daq_subsystem_path    = os.path.join(
                        os.path.join(os.path.dirname(root_path),
                        "heimdall_daq_fw"),
                        "Firmware")

daq_config_filename   = os.path.join(daq_subsystem_path, "daq_chain_config.ini")

# Import Kraken SDR modules
receiver_path         = os.path.join(root_path, "_receiver")
signal_processor_path = os.path.join(root_path, "_signal_processing")
ui_path               = os.path.join(root_path, "_UI")

sys.path.insert(0, receiver_path)
sys.path.insert(0, signal_processor_path)
sys.path.insert(0, ui_path)

daq_preconfigs_path   = os.path.join(
                        os.path.join(os.path.dirname(root_path),
                        "heimdall_daq_fw"),
                        "config_files")
daq_config_filename   = os.path.join(daq_subsystem_path, "daq_chain_config.ini")
daq_stop_filename     = "daq_stop.sh"
daq_start_filename    = "daq_start_sm.sh"
#daq_start_filename    = "daq_synthetic_start.sh"
sys.path.insert(0, daq_subsystem_path)

valid_fir_windows = ['boxcar', 'triang', 'blackman', 'hamming', 'hann', 'bartlett', 'flattop', 'parzen' , 'bohman', 'blackmanharris', 'nuttall', 'barthann']
valid_sample_rates = [0.25, 0.900001, 1.024, 1.4, 1.8, 1.92, 2.048, 2.4, 2.56, 3.2]
valid_daq_buffer_sizes = (2**np.arange(10,21,1)).tolist()
calibration_tack_modes = [['No tracking',0] , ['Periodic tracking',2]]
doa_trace_colors =	{
  "DoA Bartlett": "#00B5F7",
  "DoA Capon"   : "rgb(226,26,28)",
  "DoA MEM"     : "#1CA71C",
  "DoA TNA"     : "rgb(255, 0, 255)",
  "DoA MUSIC"   : "rgb(257,233,111)"
}
figure_font_size = 20

y=np.random.normal(0,1,2**1)
x=np.arange(2**1)

fig_layout = go.Layout(
                 paper_bgcolor='rgba(0,0,0,0)',
                 plot_bgcolor='rgba(0,0,0,0)',
                 template='plotly_dark',
                 showlegend=True,
                 margin=go.layout.Margin(
                     t=0 #top margin
                 )
             )

option = [{"label":"", "value": 1}]

DECORRELATION_OPTIONS = [
    {
        'label': 'Off',
        'value': 'Off'
    },
    {
        'label': 'F-B Averaging',
        'value': 'FBA'
    },
    {
        'label': 'Toeplizification',
        'value': 'TOEP'
    },
    {
        'label': 'Spatial Smoothing',
        'value': 'FBSS'
    },
    {
        'label': 'F-B Toeplitz',
        'value': 'FBTOEP'
    },
]