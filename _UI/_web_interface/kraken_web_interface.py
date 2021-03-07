# -*- coding: utf-8 -*-

# Import built-in modules
import logging
import os
import sys
import copy
import queue 
import time
# Import third-party modules
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
from dash.dash import no_update
from dash.dependencies import Input, Output, State
import numpy as np
import plotly.graph_objects as go
import plotly.express as px


# Import Kraken SDR modules
current_path          = os.path.dirname(os.path.realpath(__file__))
root_path             = os.path.dirname(os.path.dirname(current_path))
receiver_path         = os.path.join(root_path, "_receiver")
signal_processor_path = os.path.join(root_path, "_signal_processing")
ui_path               = os.path.join(root_path, "_UI")

sys.path.insert(0, receiver_path)
sys.path.insert(0, signal_processor_path)
sys.path.insert(0, ui_path)

import save_settings as settings
from kerberosSDR_receiver import ReceiverRTLSDR
from kerberosSDR_signal_processor import SignalProcessor
from kerberosSDR_signal_processor import DOA_plot_util
from iq_header import IQHeader

class webInterface():

    def __init__(self):
        self.user_interface = None
        
        logging.basicConfig(level=settings.logging_level*10)
        self.logger = logging.getLogger(__name__)        

        self.logger.info("Inititalizing web interface")

        #############################################
        #  Initialize and Configure Kraken modules  #
        #############################################

        # Web interface internal 
        self.page_update_rate = 1     
        self._avg_win_size = 10
        self._update_rate_arr = None

        self.sp_data_que = queue.Queue(1) # Que to communicate with the signal processing module
        self.rx_data_que = queue.Queue(1) # Que to communicate with the receiver modules

        # Instantiate and configure Kraken SDR modules
        self.module_receiver = ReceiverRTLSDR(data_que=self.rx_data_que, data_interface=settings.data_interface)
        self.module_signal_processor = SignalProcessor(data_que=self.sp_data_que, module_receiver=self.module_receiver)
        self.module_signal_processor.start()
        #############################################
        #     UI Status and Config variables        #
        #############################################

        # DAQ Configuration parameters
        self.center_freq   = 120
        self.samp_index    = 2 
        self.daq_rx_gain   = 0
        self.ip_addr       = "1.1"

        # DAQ Subsystem status parameters
        self.daq_conn_status       = 0
        self.daq_update_rate       = 0
        self.daq_frame_sync        = 1 # Active low
        self.daq_frame_index       = 0
        self.daq_power_level       = 0
        self.daq_sample_delay_sync = 0
        self.daq_iq_sync           = 0
        self.daq_noise_source_state= 0
        self.daq_center_freq       = 100
        self.daq_adc_fs            = "-"
        self.daq_fs                = "-"
        self.daq_cpi               = "-"
        self.daq_if_gains          ="[,,,,]"

        # DoA Processing Parameters        
        self.spectrum              = None
        self.doa_thetas            = None
        self.doa_results           = []
        self.doa_labels            = []
        self.logger.info("Web interface object initialized")
        
    def start_processing(self, ip_addr="127.0.0.1"):
        """
            Starts data processing

            Parameters:
            -----------
            :param: ip_addr: Ip address of the DAQ Subsystem

            :type ip_addr : string e.g.:"127.0.0.1"
        """
        self.logger.info("Start processing request")
        self.first_frame = 1
        self.module_receiver.rec_ip_addr = ip_addr        
        self.module_signal_processor.run_processing=True 
    
    def stop_processing(self):
        self.module_signal_processor.run_processing=False      

    def export_spectrum(self):
        """
        Exports the calculated spectrum image into a html file
        
        Parameters:
        ----------
        :param: : 
        :type :
        
        """
        pass

#############################################
#       Prepare component dependencies      #
#############################################

trace_colors = px.colors.qualitative.Plotly
trace_colors[3] = 'rgb(255,255,51)'

doa_trace_colors =	{
  "doa_bartlett": "#00B5F7",
  "doa_capon"   : "rgb(226,26,28)",
  "doa_mem"     : "#1CA71C",
  "doa_music"   : "rgb(257,233,111)"
}

y=np.random.normal(0,1,2**10)
x=np.arange(2**10)

fig_layout = go.Layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',        
    )
fig_dummy = go.Figure(layout=fig_layout)
fig_dummy.add_trace(go.Scatter(x=x, y=y, name = "Avg spectrum"))
fig_dummy.update_xaxes(title_text="Frequency [MHz]")
fig_dummy.update_yaxes(title_text="Amplitude [dB]")   

option = [{"label":"", "value": 1}]

#############################################
#          Prepare Dash application         #
############################################

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.layout = html.Div([
    dcc.Location(id='url', children='/config',refresh=False),

    html.Div([html.H1('Kraken SDR - Direction of Arrival Estimation')], style={"text-align": "center"}, className="main_title"),
    html.Div([html.A("Configuration", className="header_active"   , id="header_config"  ,href="/config"),
            html.A("Spectrum"       , className="header_inactive" , id="header_spectrum",href="/spectrum"),   
            html.A("DoA Estimation" , className="header_inactive" , id="header_doa"     ,href="/doa"),
            ], className="header"),
    html.Div([html.Div([html.Button('Start Processing', id='btn-start_proc', className="btn_start", n_clicks=0)], className="ctr_toolbar_item"),
            html.Div([html.Button('Stop Processing', id='btn-stop_proc', className="btn_stop", n_clicks=0)], className="ctr_toolbar_item")
            ], className="ctr_toolbar"),

    dcc.Interval(
        id='interval-component',
        interval=500, # in milliseconds
        n_intervals=0
    ),
    html.Div(id="placeholder_start"        , style={"display":"none"}),
    html.Div(id="placeholder_stop"         , style={"display":"none"}),
    html.Div(id="placeholder_update_rx"    , style={"display":"none"}),
    html.Div(id="placeholder_update_freq"  , style={"display":"none"}),
    html.Div(id="placeholder_update_dsp"   , style={"display":"none"}),    

    html.Div(id="placeholder_config_page_upd"  , style={"display":"none"}),
    html.Div(id="placeholder_spectrum_page_upd", style={"display":"none"}),
    html.Div(id="placeholder_doa_page_upd"     , style={"display":"none"}),
    
    
    html.Div(id='page-content')
])
def generate_config_page_layout(webInterface_inst):
    en_spectrum_values=[1] if webInterface_inst.module_signal_processor.en_spectrum       else []
    en_doa_values=[1]      if webInterface_inst.module_signal_processor.en_DOA_estimation else []
    en_bartlett_values=[1] if webInterface_inst.module_signal_processor.en_DOA_Bartlett   else []
    en_capon_values=[1]    if webInterface_inst.module_signal_processor.en_DOA_Capon      else []    
    en_mem_values=[1]      if webInterface_inst.module_signal_processor.en_DOA_MEM        else []
    en_music_values=[1]    if webInterface_inst.module_signal_processor.en_DOA_MUSIC      else []
    en_fb_avg_values=[1]   if webInterface_inst.module_signal_processor.en_DOA_FB_avg     else []
    
    # Calulcate spacings
    wavelength= 300 / webInterface_inst.daq_center_freq
    
    ant_spacing_wavelength = webInterface_inst.module_signal_processor.DOA_inter_elem_space
    ant_spacing_meter = wavelength * ant_spacing_wavelength
    ant_spacing_feet  = ant_spacing_meter*3.2808399
    ant_spacing_inch  = ant_spacing_meter*39.3700787
    
    config_page_layout = html.Div(children=[
        html.Div([
                html.H2("DAQ Subsystem Configuration", id="init_title_c"),
                html.Div([
                        html.Div("Center Frequency [MHz]", className="field-label"),                                         
                        dcc.Input(id='daq_center_freq', value=webInterface_inst.center_freq, type='number', debounce=True, className="field-body")
                        ], className="field"),
                html.Div([
                        html.Div("Receiver gain", className="field-label"), 
                        dcc.Dropdown(id='daq_rx_gain',
                                options=[
                                    {'label': '0 dB',    'value': 0},
                                    {'label': '0.9 dB',  'value': 0.9}, 
                                    {'label': '1.4 dB',  'value': 1.4},
                                    {'label': '2.7 dB',  'value': 2.7},
                                    {'label': '3.7 dB',  'value': 3.7},
                                    {'label': '7.7 dB',  'value': 7.7},
                                    {'label': '8.7 dB',  'value': 8.7},
                                    {'label': '12.5 dB', 'value': 12.5},
                                    {'label': '14.4 dB', 'value': 14.4},
                                    {'label': '15.7 dB', 'value': 15.7},
                                    {'label': '16.6 dB', 'value': 16.6},
                                    {'label': '19.7 dB', 'value': 19.7},
                                    {'label': '20.7 dB', 'value': 20.7},
                                    {'label': '22.9 dB', 'value': 22.9},
                                    {'label': '25.4 dB', 'value': 25.4},
                                    {'label': '28.0 dB', 'value': 28.0},
                                    {'label': '29.7 dB', 'value': 29.7},
                                    {'label': '32.8 dB', 'value': 32.8},
                                    {'label': '33.8 dB', 'value': 33.8},
                                    {'label': '36.4 dB', 'value': 36.4},
                                    {'label': '37.2 dB', 'value': 37.2},
                                    {'label': '38.6 dB', 'value': 38.6},
                                    {'label': '40.2 dB', 'value': 40.2},
                                    {'label': '42.1 dB', 'value': 42.1},
                                    {'label': '43.4 dB', 'value': 43.4},
                                    {'label': '43.9 dB', 'value': 43.9},
                                    {'label': '44.5 dB', 'value': 44.5},
                                    {'label': '48.0 dB', 'value': 48.0},
                                    {'label': '49.6 dB', 'value': 49.6},
                                    ],
                            value=webInterface_inst.daq_rx_gain, style={"display":"inline-block"},className="field-body")
                        ], className="field"),
                html.Div([
                    html.Button('Update Receiver Parameters', id='btn-update_rx_param', className="btn"),
                ], className="field")
        ], className="card"),        
        html.Div([
                html.H2("DAQ Subsystem Status", id="init_title_s"),
                html.Div([html.Div("Update rate:"              , id="label_daq_update_rate"   , className="field-label"), html.Div("- ms"        , id="body_daq_update_rate"   , className="field-body")], className="field"),
                html.Div([html.Div("Frame index:"              , id="label_daq_frame_index"   , className="field-label"), html.Div("-"           , id="body_daq_frame_index"   , className="field-body")], className="field"),
                html.Div([html.Div("Frame sync:"               , id="label_daq_frame_sync"    , className="field-label"), html.Div("LOSS"        , id="body_daq_frame_sync"    , className="field-body", style={"color": "red"})], className="field"),
                html.Div([html.Div("Power level:"              , id="label_daq_power_level"   , className="field-label"), html.Div("-"           , id="body_daq_power_level"   , className="field-body")], className="field"),
                html.Div([html.Div("Connection status:"        , id="label_daq_conn_status"   , className="field-label"), html.Div("Disconnected", id="body_daq_conn_status"   , className="field-body", style={"color": "red"})], className="field"),
                html.Div([html.Div("Sample delay snyc:"        , id="label_daq_delay_sync"    , className="field-label"), html.Div("LOSS"        , id="body_daq_delay_sync"    , className="field-body", style={"color": "red"})], className="field"),
                html.Div([html.Div("IQ snyc:"                  , id="label_daq_iq_sync"       , className="field-label"), html.Div("LOSS"        , id="body_daq_iq_sync"       , className="field-body", style={"color": "red"})], className="field"),
                html.Div([html.Div("Noise source state:"       , id="label_daq_noise_source"  , className="field-label"), html.Div("Disabled"    , id="body_daq_noise_source"  , className="field-body", style={"color": "green"})], className="field"),
                html.Div([html.Div("RF center frequecy [MHz]:" , id="label_daq_rf_center_freq", className="field-label"), html.Div("- MHz"       , id="body_daq_rf_center_freq", className="field-body")], className="field"),
                html.Div([html.Div("Sampling frequency [MHz]:" , id="label_daq_sampling_freq" , className="field-label"), html.Div("- MHz"       , id="body_daq_sampling_freq" , className="field-body")], className="field"),
                html.Div([html.Div("Data block length [ms]:"   , id="label_daq_cpi"           , className="field-label"), html.Div("- ms"        , id="body_daq_cpi"           , className="field-body")], className="field"),
                html.Div([html.Div("IF gains [dB]:"            , id="label_daq_if_gain"       , className="field-label"), html.Div("[,] dB"      , id="body_daq_if_gain"       , className="field-body")], className="field"),
        ], className="card"),
        html.Div([
            html.H2("DSP Configuration", id="init_title_d"),
            html.Div([html.Div("Enable spectrum estimation", id="label_en_spectrum" , className="field-label"),
                    dcc.Checklist(options=option          , id="en_spectrum_check" , className="field-body", value=en_spectrum_values),
            ], className="field"),
            
            html.Div([html.Div("Antenna configuration:"              , id="label_ant_arrangement"   , className="field-label"),
            dcc.RadioItems(
                options=[
                    {'label': "ULA", 'value': "ULA"},
                    {'label': "UCA", 'value': "UCA"},                
                ], value=webInterface_inst.module_signal_processor.DOA_ant_alignment, className="field-body", labelStyle={'display': 'inline-block'}, id="radio_ant_arrangement")
            ], className="field"),        
            html.Div("Spacing:"              , id="label_ant_spacing"   , className="field-label"),
            html.Div([html.Div("[wavelength]:"        , id="label_ant_spacing_wavelength"  , className="field-label"), 
                      dcc.Input(id="ant_spacing_wavelength", value=ant_spacing_wavelength, type='number', debounce=False, className="field-body")]),
            html.Div([html.Div("[meter]:"             , id="label_ant_spacing_meter"  , className="field-label"), 
                      dcc.Input(id="ant_spacing_meter", value=ant_spacing_meter, type='number', debounce=False, className="field-body")]),
            html.Div([html.Div("[feet]:"              , id="label_ant_spacing_feet"   , className="field-label"), 
                      dcc.Input(id="ant_spacing_feet", value=ant_spacing_feet, type='number'  , debounce=False, className="field-body")]),
            html.Div([html.Div("[inch]:"              , id="label_ant_spacing_inch"   , className="field-label"), 
                      dcc.Input(id="ant_spacing_inch", value=ant_spacing_inch, type='number'  , debounce=False, className="field-body")]),
            
            # --> DoA estimation configuration checkboxes <--  
            # Note: Individual checkboxes are created due to layout considerations, correct if extist a better solution       
            html.Div([html.Div("Enable DoA estimation", id="label_en_doa"     , className="field-label"),
                    dcc.Checklist(options=option     , id="en_doa_check"     , className="field-body", value=en_doa_values),
            ], className="field"),
            html.Div([html.Div("Bartlett"             , id="label_en_bartlett", className="field-label"),
                    dcc.Checklist(options=option     , id="en_bartlett_check", className="field-body", value=en_bartlett_values),
            ], className="field"),
            html.Div([html.Div("Capon"                , id="label_en_capon"   , className="field-label"),
                    dcc.Checklist(options=option     , id="en_capon_check"   , className="field-body", value=en_capon_values),
            ], className="field"),
            html.Div([html.Div("MEM"                  , id="label_en_mem"     , className="field-label"),
                    dcc.Checklist(options=option     , id="en_mem_check"     , className="field-body", value=en_mem_values),
            ], className="field"),
            html.Div([html.Div("MUSIC"                , id="label_en_music"   , className="field-label"),
                    dcc.Checklist(options=option     , id="en_music_check"   , className="field-body", value=en_music_values),
            ], className="field"),
            html.Div([html.Div("Enable F-B averaging", id="label_en_fb_avg"   , className="field-label"),
                    dcc.Checklist(options=option     , id="en_fb_avg_check"   , className="field-body", value=en_fb_avg_values),
            ], className="field")

        ], className="card"),
    ])
    return config_page_layout

        
spectrum_page_layout = html.Div([
    html.Div([
    dcc.Graph(
        style={"height": "inherit"},
        id="spectrum-graph",
        figure=fig_dummy
    )], className="monitor_card"),
])

doa_page_layout = html.Div([
    html.Div([
    dcc.Graph(
        style={"height": "inherit"},
        id="doa-graph",
        figure=fig_dummy
    )], className="monitor_card"),
])

@app.callback(   
    Output(component_id="interval-component"           , component_property='interval'),    
    Output(component_id="placeholder_config_page_upd"  , component_property='children'),
    Output(component_id="placeholder_spectrum_page_upd", component_property='children'),
    Output(component_id="placeholder_doa_page_upd"     , component_property='children'),
    Output(component_id="placeholder_update_freq"      , component_property='children'),  
    Input(component_id ="interval-component"           , component_property='n_intervals'),
    State(component_id ="url"                          , component_property='pathname')
)
def fetch_dsp_data(input_value, pathname):    
    daq_status_update_flag = 0    
    spectrum_update_flag   = 0
    doa_update_flag        = 0
    freq_update            = no_update
    #############################################
    #      Fetch new data from back-end ques    #
    #############################################        
    try:
        # Fetch new data from the receiver module
        que_data_packet = webInterface_inst.rx_data_que.get(False)
        for data_entry in que_data_packet:
            if data_entry[0] == "conn-ok":
                webInterface_inst.daq_conn_status = 1        
        
    except queue.Empty:
        # Handle empty queue here
        logging.debug("Receiver module que is empty")
    else:
        pass
        # Handle task here and call q.task_done()

    try:
        # Fetch new data from the signal processing module
        que_data_packet  = webInterface_inst.sp_data_que.get(False)
        for data_entry in que_data_packet:
            if data_entry[0] == "iq_header":
                logging.debug("Iq header data fetched from signal processing que")
                iq_header = data_entry[1]
                # Unpack header
                webInterface_inst.daq_frame_index = iq_header.cpi_index
            
                webInterface_inst.daq_frame_sync        = iq_header.check_sync_word()            
                webInterface_inst.daq_power_level       = iq_header.adc_overdrive_flags
                webInterface_inst.daq_sample_delay_sync = iq_header.delay_sync_flag
                webInterface_inst.daq_iq_sync           = iq_header.iq_sync_flag
                webInterface_inst.daq_noise_source_state= iq_header.noise_source_state
                
                if webInterface_inst.daq_center_freq != iq_header.rf_center_freq/10**6: 
                    freq_update = 1

                webInterface_inst.daq_center_freq       = iq_header.rf_center_freq/10**6
                webInterface_inst.daq_adc_fs            = iq_header.adc_sampling_freq/10**6
                webInterface_inst.daq_fs                = iq_header.sampling_freq/10**6
                webInterface_inst.daq_cpi               = int(iq_header.cpi_length*10**3/iq_header.sampling_freq)
                gain_list_str=""
                for m in range(iq_header.active_ant_chs):
                    gain_list_str+=str(iq_header.if_gains[m]/10)
                    gain_list_str+=", "
                webInterface_inst.daq_if_gains          =gain_list_str[:-2]
                daq_status_update_flag = 1
            elif data_entry[0] == "update_rate":
                webInterface_inst.daq_update_rate = data_entry[1]
                # Set absoluth minimum
                if webInterface_inst.daq_update_rate < 0.1: webInterface_inst.daq_update_rate = 0.1
                if webInterface_inst._update_rate_arr is None:
                    webInterface_inst._update_rate_arr = np.ones(webInterface_inst._avg_win_size)*webInterface_inst.daq_update_rate
                webInterface_inst._update_rate_arr[0:webInterface_inst._avg_win_size-2] = \
                webInterface_inst._update_rate_arr[1:webInterface_inst._avg_win_size-1]                
                webInterface_inst._update_rate_arr[webInterface_inst._avg_win_size-1] = webInterface_inst.daq_update_rate
                webInterface_inst.page_update_rate = np.average(webInterface_inst._update_rate_arr)*0.8                
            elif data_entry[0] == "max_amplitude":
                pass
            elif data_entry[0] == "spectrum":
                logging.debug("Spectrum data fetched from signal processing que")
                spectrum_update_flag = 1
                webInterface_inst.spectrum = data_entry[1]
            elif data_entry[0] == "doa_thetas":
                webInterface_inst.doa_thetas= data_entry[1]
                doa_update_flag               = 1
                webInterface_inst.doa_results = []
                webInterface_inst.doa_labels  = []
                logging.debug("DoA estimation data fetched from signal processing que")                
            elif data_entry[0] == "doa_bartlett":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "doa_capon":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "doa_mem":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "doa_music":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])

            else:                
                logging.warning("Unknown data entry: {:s}".format(data_entry[0]))
        
    except queue.Empty:
        # Handle empty queue here
        logging.debug("Signal processing que is empty")
    else:
        pass
        # Handle task here and call q.task_done()
    if (pathname == "/config" or pathname=="/") and daq_status_update_flag:        
        return webInterface_inst.page_update_rate*1000, 1, no_update, no_update, freq_update
    elif pathname == "/spectrum" and spectrum_update_flag:
        return webInterface_inst.page_update_rate*1000, no_update, 1, no_update, no_update
    elif pathname == "/doa" and doa_update_flag:
        return webInterface_inst.page_update_rate*1000, no_update, no_update, 1, no_update
    else:
        return  webInterface_inst.page_update_rate*1000, no_update, no_update, no_update, no_update

@app.callback(
    Output(component_id="body_daq_update_rate"        , component_property='children'),
    Output(component_id="body_daq_frame_index"        , component_property='children'),
    Output(component_id="body_daq_frame_sync"         , component_property='children'),
    Output(component_id="body_daq_frame_sync"         , component_property='style'),
    Output(component_id="body_daq_power_level"        , component_property='children'),
    Output(component_id="body_daq_conn_status"        , component_property='children'),
    Output(component_id="body_daq_conn_status"        , component_property='style'),    
    Output(component_id="body_daq_delay_sync"         , component_property='children'),
    Output(component_id="body_daq_delay_sync"         , component_property='style'),
    Output(component_id="body_daq_iq_sync"            , component_property='children'),
    Output(component_id="body_daq_iq_sync"            , component_property='style'),
    Output(component_id="body_daq_noise_source"       , component_property='children'),
    Output(component_id="body_daq_noise_source"       , component_property='style'),
    Output(component_id="body_daq_rf_center_freq"     , component_property='children'),
    Output(component_id="body_daq_sampling_freq"      , component_property='children'),
    Output(component_id="body_daq_cpi"                , component_property='children'),   
    Output(component_id="body_daq_if_gain"            , component_property='children'),     
    Input(component_id ="placeholder_config_page_upd" , component_property='children'),
    prevent_initial_call=True
)
def update_daq_status(input_value):         
    
    
    #############################################
    #      Prepare UI component properties      #
    #############################################
    
    if webInterface_inst.daq_conn_status:
        daq_conn_status_str = "Connected"
        conn_status_style={"color": "green"}
    else:
        daq_conn_status_str = "Disconnected"
        conn_status_style={"color": "red"}

    if webInterface_inst.daq_update_rate < 1:
        daq_update_rate_str    = "{:.2f} ms".format(webInterface_inst.daq_update_rate*1000)
    else:
        daq_update_rate_str    = "{:.2f} s".format(webInterface_inst.daq_update_rate)

    daq_frame_index_str    = str(webInterface_inst.daq_frame_index)
    if webInterface_inst.daq_frame_sync:
        daq_frame_sync_str = "LOSS"    
        frame_sync_style={"color": "red"}
    else:
        daq_frame_sync_str = "Ok"
        frame_sync_style={"color": "green"}

    if webInterface_inst.daq_sample_delay_sync:
        daq_delay_sync_str     = "Ok"
        delay_sync_style={"color": "green"}
    else:
        daq_delay_sync_str     = "LOSS"
        delay_sync_style={"color": "red"}

    if webInterface_inst.daq_iq_sync:
        daq_iq_sync_str        = "Ok"
        iq_sync_style={"color": "green"}
    else:
        daq_iq_sync_str        = "LOSS"
        iq_sync_style={"color": "red"}

    if webInterface_inst.daq_noise_source_state:
        daq_noise_source_str   = "Enabled"
        noise_source_style={"color": "red"}
    else:
        daq_noise_source_str   = "Disabled"
        noise_source_style={"color": "green"}
        
    
    daq_power_level_str    = str(webInterface_inst.daq_power_level)    
    daq_rf_center_freq_str = str(webInterface_inst.daq_center_freq)
    daq_sampling_freq_str  = str(webInterface_inst.daq_fs)
    daq_cpi_str            = str(webInterface_inst.daq_cpi)
    
    return daq_update_rate_str, daq_frame_index_str, daq_frame_sync_str, \
            frame_sync_style, daq_power_level_str, daq_conn_status_str, \
            conn_status_style, daq_delay_sync_str, delay_sync_style, \
            daq_iq_sync_str, iq_sync_style, daq_noise_source_str, \
            noise_source_style, daq_rf_center_freq_str, daq_sampling_freq_str, \
            daq_cpi_str, webInterface_inst.daq_if_gains
            


@app.callback(
    Output(component_id='spectrum-graph', component_property='figure'),
    Input(component_id='placeholder_spectrum_page_upd', component_property='children'),
    prevent_initial_call=True
)
def plot_spectrum(spectrum_update_flag):
    fig = go.Figure(layout=fig_layout)
    if webInterface_inst.spectrum is not None:
        # Plot traces
        freqs = webInterface_inst.spectrum[0,:]    
        for m in range(np.size(webInterface_inst.spectrum, 0)-1):   
            fig.add_trace(go.Scatter(x=freqs, y=webInterface_inst.spectrum[m+1, :], 
                                     name="Channel {:d}".format(m),
                                     line = dict(color = trace_colors[m],
                                                 width = 3)
                                    ))
        
        fig.update_xaxes(title_text="Frequency [MHz]", 
                        color='rgba(255,255,255,1)', 
                        title_font_size=20, 
                        tickfont_size=15,
                        mirror=True,
                        ticks='outside',
                        showline=True)
        fig.update_yaxes(title_text="Amplitude [dB]",
                        color='rgba(255,255,255,1)', 
                        title_font_size=20, 
                        tickfont_size=15, 
                        #range=[-5, 5],
                        mirror=True,
                        ticks='outside',
                        showline=True)
        return fig

@app.callback(
    Output(component_id='doa-graph'              , component_property='figure'),
    Input(component_id='placeholder_doa_page_upd', component_property='children'),
    prevent_initial_call=True
)
def plot_doa(doa_update_flag):
    fig = go.Figure(layout=fig_layout)   
    
    if webInterface_inst.doa_thetas is not None:
        # Plot traces 
        for i, doa_result in enumerate(webInterface_inst.doa_results): 
            fig.add_trace(go.Scatter(x=webInterface_inst.doa_thetas, 
                                     y=DOA_plot_util(doa_result, log_scale_min= -50),
                                     name=webInterface_inst.doa_labels[i],
                                     line = dict(
                                                color = doa_trace_colors[webInterface_inst.doa_labels[i]],
                                                width = 3)
                           ))
        
        fig.update_xaxes(title_text="Incident angle [deg]", 
                        color='rgba(255,255,255,1)', 
                        title_font_size=20, 
                        tickfont_size=15,
                        mirror=True,
                        ticks='outside',
                        showline=True)
        fig.update_yaxes(title_text="Amplitude [dB]",
                        color='rgba(255,255,255,1)', 
                        title_font_size=20, 
                        tickfont_size=15, 
                        #range=[-5, 5],
                        mirror=True,
                        ticks='outside',
                        showline=True)
        return fig
    
@app.callback(    
    Output(component_id='placeholder_start', component_property='children'),
    Input(component_id='btn-start_proc', component_property='n_clicks'),
    prevent_initial_call=True
)
def start_proc_btn(input_value):    
    logging.info("Start pocessing btn pushed")    
    webInterface_inst.start_processing()
    return ""

@app.callback(    
    Output(component_id='placeholder_stop', component_property='children'),
    Input(component_id='btn-stop_proc', component_property='n_clicks'),
    prevent_initial_call=True
)
def stop_proc_btn(input_value):    
    logging.info("Stop pocessing btn pushed")    
    webInterface_inst.stop_processing()    
    return ""

@app.callback(
    Output(component_id="placeholder_update_rx" , component_property="children"),    
    Input(component_id="btn-update_rx_param"    , component_property="n_clicks"),
    State(component_id ="daq_center_freq"       , component_property='value'),    
    State(component_id ="daq_rx_gain"           , component_property='value'), 
    prevent_initial_call=True
)
def update_daq_params(input_value, f0, gain):
    if input_value is None:
        raise PreventUpdate


    # Change antenna spacing config for DoA estimation
    webInterface_inst.module_signal_processor.DOA_inter_elem_space *=f0/webInterface_inst.daq_center_freq    

    webInterface_inst.center_freq = f0
    webInterface_inst.daq_rx_gain = gain
    webInterface_inst.module_receiver.set_center_freq(int(f0*10**6))
    webInterface_inst.module_receiver.set_if_gain(int(10*gain))
    logging.info("Updating receiver parameters: {0}".format(input_value))
    logging.info("Center frequency: {:f}".format(webInterface_inst.center_freq))
        
    return  ""


@app.callback(
    Output(component_id="placeholder_update_dsp", component_property="children"),
    Output(component_id="ant_spacing_wavelength", component_property="value"),
    Output(component_id="ant_spacing_meter"     , component_property="value"),
    Output(component_id="ant_spacing_feet"      , component_property="value"),
    Output(component_id="ant_spacing_inch"      , component_property="value"),    
    Input(component_id="placeholder_update_freq", component_property="children"),
    Input(component_id="en_spectrum_check"      , component_property="value"),
    Input(component_id="en_doa_check"           , component_property="value"),
    Input(component_id="en_bartlett_check"      , component_property="value"),
    Input(component_id="en_capon_check"         , component_property="value"),
    Input(component_id="en_mem_check"           , component_property="value"),
    Input(component_id="en_music_check"         , component_property="value"),
    Input(component_id="en_fb_avg_check"        , component_property="value"),
    Input(component_id="ant_spacing_wavelength" , component_property="value"),
    Input(component_id="ant_spacing_meter"      , component_property="value"),
    Input(component_id="ant_spacing_feet"       , component_property="value"),
    Input(component_id="ant_spacing_inch"       , component_property="value"),
    Input(component_id="radio_ant_arrangement"  , component_property="value"),
    prevent_initial_call=True
)
def update_dsp_params(freq_update, en_spectrum, en_doa, en_bartlett, en_capon, en_mem, en_music,
                      en_fb_avg, spacing_wavlength, spacing_meter, spacing_feet, spacing_inch,
                      ant_arrangement):
    ctx = dash.callback_context
    
    if ctx.triggered:
        component_id = ctx.triggered[0]['prop_id'].split('.')[0]
        wavelength= 300 / webInterface_inst.daq_center_freq
        
        if component_id   == "placeholder_update_freq": 
            ant_spacing_meter = spacing_meter  
        else:
            ant_spacing_meter = wavelength * webInterface_inst.module_signal_processor.DOA_inter_elem_space
        
        if component_id   == "ant_spacing_meter":
            ant_spacing_meter = spacing_meter
        elif component_id == "ant_spacing_wavelength":
            ant_spacing_meter = wavelength*spacing_wavlength
        elif component_id == "ant_spacing_feet":
            ant_spacing_meter = spacing_feet/3.2808399
        elif component_id == "ant_spacing_inch":
            ant_spacing_meter = spacing_inch/39.3700787
        
        webInterface_inst.module_signal_processor.DOA_inter_elem_space = ant_spacing_meter / wavelength
        ant_spacing_feet = ant_spacing_meter * 3.2808399
        ant_spacing_inch = ant_spacing_meter * 39.3700787
        ant_spacing_wavlength = ant_spacing_meter / wavelength

    if en_spectrum is not None and len(en_spectrum):
        logging.debug("Spectrum estimation enabled")
        webInterface_inst.module_signal_processor.en_spectrum = True
    else:
        webInterface_inst.module_signal_processor.en_spectrum = False       
    if en_doa is not None and len(en_doa):
        logging.debug("DoA estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_estimation = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_estimation = False       
    
    if en_bartlett is not None and len(en_bartlett):
        logging.debug("Bartlett estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_Bartlett = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_Bartlett = False
    if en_capon is not None and len(en_capon):        
        logging.debug("Capon estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_Capon    = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_Capon    = False
    
    if en_mem is not None and len(en_mem):
        logging.debug("MEM estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_MEM      = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_MEM      = False
    
    if en_music is not None and len(en_music):
        logging.debug("MUSIC estimation enabled")
        webInterface_inst.module_signal_processor.en_DOA_MUSIC    = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_MUSIC    = False
    if en_fb_avg is not None and len(en_fb_avg):
        logging.debug("FB averaging enabled")
        webInterface_inst.module_signal_processor.en_DOA_FB_avg   = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_FB_avg   = False
    
    #webInterface_inst.module_signal_processor.DOA_ant_alignment=ant_arrangement

    return "", ant_spacing_wavlength, ant_spacing_meter, ant_spacing_feet, ant_spacing_inch


@app.callback(Output("page-content"   , "children"),
              Output("header_config"  ,"className"),  
              Output("header_spectrum","className"),
              Output("header_doa"     ,"className"),
              [Input("url"            , "pathname")])
def display_page(pathname):
    if pathname == "/":
        return generate_config_page_layout(webInterface_inst), "header_active", "header_inactive", "header_inactive"
    elif pathname == "/config":
        return generate_config_page_layout(webInterface_inst), "header_active", "header_inactive", "header_inactive" 
    elif pathname == "/spectrum":
        return spectrum_page_layout, "header_inactive", "header_active", "header_inactive"
    elif pathname == "/doa":
        return doa_page_layout, "header_inactive", "header_inactive", "header_active"
    
if __name__ == "__main__":        
    webInterface_inst = webInterface()
    app.run_server(debug=False, host="0.0.0.0")


"""
html.Div([
    html.H2("System Logs"),
    dcc.Textarea(
        placeholder = "Enter a value...",
        value = "System logs .. - Curently NOT used",
        style = {"width": "100%", "background-color": "#000000", "color":"#02c93d"}
    )
], className="card")
"""