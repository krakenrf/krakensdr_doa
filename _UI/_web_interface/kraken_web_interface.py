# -*- coding: utf-8 -*-

# Import built-in modules
import logging
import os
import sys
import copy
import queue 
import time
import subprocess

# Import third-party modules
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
from dash.dash import no_update
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from configparser import ConfigParser

# Import Kraken SDR modules
current_path          = os.path.dirname(os.path.realpath(__file__))
root_path             = os.path.dirname(os.path.dirname(current_path))
receiver_path         = os.path.join(root_path, "_receiver")
signal_processor_path = os.path.join(root_path, "_signal_processing")
ui_path               = os.path.join(root_path, "_UI")

sys.path.insert(0, receiver_path)
sys.path.insert(0, signal_processor_path)
sys.path.insert(0, ui_path)

daq_subsystem_path    = os.path.join(
                            os.path.join(os.path.dirname(root_path), 
                            "heimdall_daq_fw"), 
                        "Firmware")
daq_config_filename   = os.path.join(daq_subsystem_path, "daq_chain_config.ini")
daq_stop_filename     = "daq_stop.sh"
daq_start_filename   = "daq_start_sm.sh"
#daq_start_filename    = "daq_synthetic_start.sh"


import save_settings as settings
from krakenSDR_receiver import ReceiverRTLSDR
from krakenSDR_signal_processor import SignalProcessor
from krakenSDR_signal_processor import DOA_plot_util
from iq_header import IQHeader

class webInterface():

    def __init__(self):
        self.user_interface = None
        
        logging.basicConfig(level=settings.logging_level*10)
        self.logger = logging.getLogger(__name__)        
        self.logger.setLevel(settings.logging_level*10)
        self.logger.info("Inititalizing web interface ")

        #############################################
        #  Initialize and Configure Kraken modules  #
        #############################################

        # Web interface internal 
        self.page_update_rate = 1     
        self._avg_win_size = 10
        self._update_rate_arr = None
        self._doa_method   = 3
        self._doa_fig_type = 0
        
        self.sp_data_que = queue.Queue(1) # Que to communicate with the signal processing module
        self.rx_data_que = queue.Queue(1) # Que to communicate with the receiver modules

        # Instantiate and configure Kraken SDR modules
        self.module_receiver = ReceiverRTLSDR(data_que=self.rx_data_que, data_interface=settings.data_interface)
        self.module_signal_processor = SignalProcessor(data_que=self.sp_data_que, module_receiver=self.module_receiver)
        self.module_signal_processor.start()
        #############################################
        #       UI Status and Config variables      #
        #############################################

        # DAQ Configuration parameters
        self.center_freq   = 120
        self.samp_index    = 2 
        self.daq_rx_gain   = 0
        self.ip_addr       = "1.1"

        # DAQ Subsystem status parameters
        self.daq_conn_status       = 0
        self.daq_cgf_iface_status  = 0 # 0- ready, 1-busy        
        self.daq_update_rate       = 0
        self.daq_frame_sync        = 1 # Active low
        self.daq_frame_index       = 0
        self.daq_frame_type        = "-"
        self.daq_power_level       = 0
        self.daq_sample_delay_sync = 0
        self.daq_iq_sync           = 0
        self.daq_noise_source_state= 0
        self.daq_center_freq       = 100
        self.daq_adc_fs            = "-"
        self.daq_fs                = "-"
        self.daq_cpi               = "-"
        self.daq_if_gains          ="[,,,,]"

        self.squelch_th            = None

        # DSP Processing Parameters and Results  
        self.spectrum              = None
        self.doa_thetas            = None
        self.doa_results           = []
        self.doa_labels            = []
        self.doas                  = [] # Final measured DoAs [deg]
        self.doa_confidences       = []
        self.compass_ofset         = 0
        self.DOA_res_fd            = open("_android_web/DOA_value.html","w+") #open("/ram/DOA_value.html","w+") # DOA estimation result file descriptor

        self.max_amplitude         = 0 # Used to help setting the threshold level of the squelch
        self.avg_powers            = []
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
    
    def close_data_interfaces(self):
        self.module_receiver.eth_close()

    def close(self):
        self.DOA_res_fd.close()
    
    def read_config_file(self):
        """

        """
        parser = ConfigParser()
        found = parser.read([daq_config_filename])
        param_list = []
        if not found:            
            return None
        param_list.append(parser.getint('hw', 'num_ch'))

        param_list.append(parser.getint('daq','daq_buffer_size'))
        param_list.append(parser.getint('daq','sample_rate'))
        param_list.append(parser.getint('daq','en_noise_source_ctr'))

        param_list.append(parser.getint('squelch','en_squelch'))
        param_list.append(parser.getfloat('squelch','amplitude_threshold'))

        param_list.append(parser.getint('pre_processing', 'cpi_size'))
        param_list.append(parser.getint('pre_processing', 'decimation_ratio'))
        param_list.append(parser.getfloat('pre_processing', 'fir_relative_bandwidth'))
        param_list.append(parser.getint('pre_processing', 'fir_tap_size'))
        param_list.append(parser.get('pre_processing','fir_window'))
        param_list.append(parser.getint('pre_processing','en_filter_reset'))

        param_list.append(parser.getint('calibration','corr_size'))
        param_list.append(parser.getint('calibration','std_ch_ind'))
        param_list.append(parser.getint('calibration','en_iq_cal'))
        param_list.append(parser.getint('calibration','gain_lock_interval'))
        param_list.append(parser.getint('calibration','require_track_lock_intervention'))
        param_list.append(parser.getint('calibration','cal_track_mode'))
        param_list.append(parser.getint('calibration','cal_frame_interval'))
        param_list.append(parser.getint('calibration','cal_frame_burst_size'))
        param_list.append(parser.getint('calibration','amplitude_tolerance'))
        param_list.append(parser.getint('calibration','phase_tolerance'))
        param_list.append(parser.getint('calibration','maximum_sync_fails'))

        param_list.append(parser.get('data_interface','out_data_iface_type'))
        
        if self.squelch_th is None:
            self.squelch_th = round(20*np.log10(param_list[5]),1)        

        return param_list
    
    def write_config_file(self, param_list):
        """
        
        """
        logging.info("Write config file: {0}".format(param_list))
        parser = ConfigParser()
        found = parser.read([daq_config_filename])
        if not found:            
            return -1
        
        parser['hw']['num_ch']=str(param_list[0])

        parser['daq']['daq_buffer_size']=str(param_list[1])
        parser['daq']['sample_rate']=str(param_list[2])
        parser['daq']['en_noise_source_ctr']=str(param_list[3])

        parser['squelch']['en_squelch']=str(param_list[4])
        parser['squelch']['amplitude_threshold']=str(param_list[5])

        parser['pre_processing']['cpi_size']=str(param_list[6])
        parser['pre_processing']['decimation_ratio']=str(param_list[7])
        parser['pre_processing']['fir_relative_bandwidth']=str(param_list[8])
        parser['pre_processing']['fir_tap_size']=str(param_list[9])
        parser['pre_processing']['fir_window']=str(param_list[10])
        parser['pre_processing']['en_filter_reset']=str(param_list[11])

        parser['calibration']['corr_size']=str(param_list[12])
        parser['calibration']['std_ch_ind']=str(param_list[13])
        parser['calibration']['en_iq_cal']=str(param_list[14])
        parser['calibration']['gain_lock_interval']=str(param_list[15])
        parser['calibration']['require_track_lock_intervention']=str(param_list[16])
        parser['calibration']['cal_track_mode']=str(param_list[17])
        parser['calibration']['cal_frame_interval']=str(param_list[18])
        parser['calibration']['cal_frame_burst_size']=str(param_list[19])
        parser['calibration']['amplitude_tolerance']=str(param_list[20])
        parser['calibration']['phase_tolerance']=str(param_list[21])
        parser['calibration']['maximum_sync_fails']=str(param_list[22])

        with open(daq_config_filename, 'w') as configfile:
            parser.write(configfile)
        return 0

#############################################
#       Prepare component dependencies      #
#############################################

trace_colors = px.colors.qualitative.Plotly
trace_colors[3] = 'rgb(255,255,51)'

doa_trace_colors =	{
  "DoA Bartlett": "#00B5F7",
  "DoA Capon"   : "rgb(226,26,28)",
  "DoA MEM"     : "#1CA71C",
  "DoA MUSIC"   : "rgb(257,233,111)"
}
figure_font_size = 20

y=np.random.normal(0,1,2**10)
x=np.arange(2**10)

fig_layout = go.Layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)', 
        template='plotly_dark',
        showlegend=True    
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
app_log = logging.getLogger('werkzeug')
#app_log.setLevel(settings.logging_level*10)
app_log.setLevel(30) # TODO: Only during dev time

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
    html.Div(id="placeholder_start"          , style={"display":"none"}),
    html.Div(id="placeholder_stop"           , style={"display":"none"}),
    html.Div(id="placeholder_update_rx"      , style={"display":"none"}),
    html.Div(id="placeholder_recofnig_daq"   , style={"display":"none"}),    
    html.Div(id="placeholder_update_freq"    , style={"display":"none"}),
    html.Div(id="placeholder_update_dsp"     , style={"display":"none"}),
    html.Div(id="placeholder_update_squelch" , style={"display":"none"}),

    

    html.Div(id="placeholder_config_page_upd"  , style={"display":"none"}),
    html.Div(id="placeholder_spectrum_page_upd", style={"display":"none"}),
    html.Div(id="placeholder_doa_page_upd"     , style={"display":"none"}),
    
    
    html.Div(id='page-content')
])
def generate_config_page_layout(webInterface_inst):
    # Read DAQ config file
    daq_cfg_params = webInterface_inst.read_config_file()   

    if daq_cfg_params is not None:
        en_noise_src_values       =[1] if daq_cfg_params[3]  else []
        en_squelch_values         =[1] if daq_cfg_params[4]  else []
        en_filter_rst_values      =[1] if daq_cfg_params[11] else []
        en_iq_cal_values          =[1] if daq_cfg_params[14] else []
        en_req_track_lock_values  =[1] if daq_cfg_params[16] else []

        daq_data_iface_type       = daq_cfg_params[23]

    en_spectrum_values    =[1] if webInterface_inst.module_signal_processor.en_spectrum       else []
    en_doa_values         =[1] if webInterface_inst.module_signal_processor.en_DOA_estimation else []
    en_bartlett_values    =[1] if webInterface_inst.module_signal_processor.en_DOA_Bartlett   else []
    en_capon_values       =[1] if webInterface_inst.module_signal_processor.en_DOA_Capon      else []    
    en_mem_values         =[1] if webInterface_inst.module_signal_processor.en_DOA_MEM        else []
    en_music_values       =[1] if webInterface_inst.module_signal_processor.en_DOA_MUSIC      else []
    en_fb_avg_values      =[1] if webInterface_inst.module_signal_processor.en_DOA_FB_avg     else []    
    en_dsp_squelch_values =[1] if webInterface_inst.module_signal_processor.en_squelch        else []
    # Calulcate spacings
    wavelength= 300 / webInterface_inst.daq_center_freq
    
    ant_spacing_wavelength = webInterface_inst.module_signal_processor.DOA_inter_elem_space
    ant_spacing_meter = wavelength * ant_spacing_wavelength
    ant_spacing_feet  = ant_spacing_meter*3.2808399
    ant_spacing_inch  = ant_spacing_meter*39.3700787
    
    #-----------------------------
    #   DAQ Configuration Card
    #-----------------------------
    # -- > Main Card Layout < --
    daq_config_card_list = \
    [
        html.H2("RF Receiver Configuration", id="init_title_c"),
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
        ], className="field"),        
    ]
    
    # --> Optional DAQ Subsystem reconfiguration fields <--    
    if daq_cfg_params is not None:
        daq_subsystem_reconfiguration_options = [ \
            html.H2("DAQ Subsystem Reconfiguration", id="init_title_reconfig"),
            html.H3("HW", id="cfg_group_hw"),
            html.Div([
                    html.Div("Rx channels:", className="field-label"),                                         
                    dcc.Input(id='cfg_rx_channels', value=daq_cfg_params[0], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.H3("DAQ", id="cfg_group_daq"),
            html.Div([
                    html.Div("DAQ buffer size:", className="field-label"),                                         
                    dcc.Input(id='cfg_daq_buffer_size', value=daq_cfg_params[1], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Sample rate [MHz]:", className="field-label"),                                         
                    dcc.Input(id='cfg_sample_rate', value=daq_cfg_params[2]/10**6, type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Enable noise source control:", className="field-label"),                                         
                    dcc.Checklist(options=option     , id="en_noise_source_ctr"   , className="field-body", value=en_noise_src_values),
            ], className="field"),
            html.H3("Squelch"),
            html.Div([
                    html.Div("Enable Squelch mode:", className="field-label"),                                                                 
                    dcc.Checklist(options=option     , id="en_squelch_mode"   , className="field-body", value=en_squelch_values),
            ], className="field"),
            html.Div([
                    html.Div("Initial threshold:", className="field-label"),                                         
                    dcc.Input(id='cfg_squelch_init_th', value=daq_cfg_params[5], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.H3("Pre Processing"),
            html.Div([
                    html.Div("CPI size [sample]:", className="field-label"),                                         
                    dcc.Input(id='cfg_cpi_size', value=daq_cfg_params[6], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Decimation ratio:", className="field-label"),                                         
                    dcc.Input(id='cfg_decimation_ratio', value=daq_cfg_params[7], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("FIR relative bandwidth:", className="field-label"),                                         
                    dcc.Input(id='cfg_fir_bw', value=daq_cfg_params[8], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("FIR tap size:", className="field-label"),                                         
                    dcc.Input(id='cfg_fir_tap_size', value=daq_cfg_params[9], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
            html.Div("FIR window:", className="field-label"),                                         
                    dcc.Input(id='cfg_fir_window', value=daq_cfg_params[10], type='text', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Enable filter reset:", className="field-label"),                                         
                    dcc.Checklist(options=option     , id="en_filter_reset"   , className="field-body", value=en_filter_rst_values),
            ], className="field"),
            html.H3("Calibration"),
            html.Div([
                    html.Div("Correlation size [sample]:", className="field-label"),                                         
                    dcc.Input(id='cfg_corr_size', value=daq_cfg_params[12], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Standard channel index:", className="field-label"),                                         
                    dcc.Input(id='cfg_std_ch_ind', value=daq_cfg_params[13], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Enable IQ calibration:", className="field-label"),                                         
                    dcc.Checklist(options=option     , id="en_iq_cal"   , className="field-body", value=en_iq_cal_values),
            ], className="field"),
            html.Div([
                    html.Div("Gain lock interval [frame]:", className="field-label"),                                         
                    dcc.Input(id='cfg_gain_lock', value=daq_cfg_params[15], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Require track lock intervention:", className="field-label"),                                         
                    dcc.Checklist(options=option     , id="en_req_track_lock_intervention"   , className="field-body", value=en_req_track_lock_values),
            ], className="field"),
            html.Div([
                    html.Div("Calibration track mode:", className="field-label"),                                         
                    dcc.Input(id='cfg_cal_track_mode', value=daq_cfg_params[17], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Calibration frame interval:", className="field-label"),                                         
                    dcc.Input(id='cfg_cal_frame_interval', value=daq_cfg_params[18], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Calibration frame bursts size:", className="field-label"),                                         
                    dcc.Input(id='cfg_cal_frame_burst_size', value=daq_cfg_params[19], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Amplitude tolerance [dB]:", className="field-label"),                                         
                    dcc.Input(id='cfg_amplitude_tolerance', value=daq_cfg_params[20], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Phase tolerance [deg]:", className="field-label"),                                         
                    dcc.Input(id='cfg_phase_tolerance', value=daq_cfg_params[21], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                    html.Div("Maximum sync fails:", className="field-label"),                                         
                    dcc.Input(id='cfg_max_sync_fails', value=daq_cfg_params[22], type='number', debounce=True, className="field-body")
            ], className="field"),
            html.Div([
                html.Button('Reconfigure & Restart DAQ chain', id='btn_reconfig_daq_chain', className="btn"),
            ], className="field") 
        ]
        for i in range(len(daq_subsystem_reconfiguration_options)):
            daq_config_card_list.append(daq_subsystem_reconfiguration_options[i])
    else:
        daq_config_card_list.append(html.H2("DAQ Subsystem Reconfiguration", id="init_title_reconfig"))
        daq_config_card_list.append(html.Div("Config file not found! Reconfiguration is not possible !", id="daq_reconfig_note", className="field", style={"color":"red"}))
    
    daq_config_card = html.Div(daq_config_card_list, className="card")
    #-----------------------------
    #       DAQ Status Card
    #-----------------------------
    daq_status_card = \
    html.Div([
        html.H2("DAQ Subsystem Status", id="init_title_s"),
        html.Div([html.Div("Update rate:"              , id="label_daq_update_rate"   , className="field-label"), html.Div("- ms"        , id="body_daq_update_rate"   , className="field-body")], className="field"),
        html.Div([html.Div("Frame index:"              , id="label_daq_frame_index"   , className="field-label"), html.Div("-"           , id="body_daq_frame_index"   , className="field-body")], className="field"),
        html.Div([html.Div("Frame type:"               , id="label_daq_frame_type"    , className="field-label"), html.Div("-"           , id="body_daq_frame_type"    , className="field-body")], className="field"),
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
        html.Div([html.Div("Max amplitude-CH0 [dB]:"   , id="label_max_amp"           , className="field-label"), html.Div("-"           , id="body_max_amp"           , className="field-body")], className="field"),
        html.Div([html.Div("Avg. powers [dB]:"         , id="label_avg_powers"        , className="field-label"), html.Div("[,] dB"      , id="body_avg_powers"        , className="field-body")], className="field"),
    ], className="card")

    #-----------------------------
    #    DSP Confugartion Card
    #-----------------------------

    dsp_config_card = \
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
        html.Div([html.Div("DoA method", id="label_doa_method"     , className="field-label"),
        dcc.Dropdown(id='doa_method',
            options=[
                {'label': 'Bartlett', 'value': 0},
                {'label': 'Capon'   , 'value': 1},
                {'label': 'MEM'   , 'value': 2},
                {'label': 'MUSIC'   , 'value': 3}
                ],
        value=webInterface_inst._doa_method, style={"display":"inline-block"},className="field-body")
        ], className="field"),
        html.Div([html.Div("Enable F-B averaging", id="label_en_fb_avg"   , className="field-label"),
                dcc.Checklist(options=option     , id="en_fb_avg_check"   , className="field-body", value=en_fb_avg_values),
        ], className="field")
    ], className="card")

    #-----------------------------
    #    Display Options Card
    #-----------------------------
    
    display_options_card = \
    html.Div([
        html.H2("Display Options", id="init_title_disp"),
        html.Div("DoA estimation graph type:", className="field-label"), 
        dcc.Dropdown(id='doa_fig_type',
                options=[
                    {'label': 'Linear plot', 'value': 0},
                    {'label': 'Polar plot' ,  'value': 1},
                    {'label': 'Compass'    ,  'value': 2},
                    ],
            value=webInterface_inst._doa_fig_type, style={"display":"inline-block"},className="field-body"),
        html.Div("Compass ofset [deg]:", className="field-label"), 
        dcc.Input(id="compass_ofset", value=webInterface_inst.compass_ofset, type='number', debounce=False, className="field-body"),

    ], className="card")
    
    #-----------------------------
    #  Squelch Configuration Card
    #-----------------------------
    
    if webInterface_inst.squelch_th is not None:        
        squelch_th_display_value = webInterface_inst.squelch_th
        reconfig_note = ""
    else:
        squelch_th_display_value = 0
        reconfig_note = "Unknown initial threshold value"

    squelch_card = \
    html.Div([
        html.H2("Squelch configuration", id="init_title_sq"),
        html.Div([html.Div("Enable squelch (DOA-DSP Subsystem)", id="label_en_dsp_squelch" , className="field-label"),
                dcc.Checklist(options=option , id="en_dsp_squelch_check" , className="field-body", value=en_dsp_squelch_values),
            ], className="field"),
        html.Div([
                html.Div("Squelch threshold [dB] (<0):", className="field-label"),                                         
                dcc.Input(id='squelch_th', value=squelch_th_display_value, type='number', debounce=False, className="field-body")
            ], className="field"),
        html.Div(reconfig_note, id="squelch_reconfig_note", className="field", style={"color":"red"}),
    ], className="card")

    config_page_layout = html.Div(children=[daq_config_card, daq_status_card, dsp_config_card, display_options_card,squelch_card])
    return config_page_layout

        
spectrum_page_layout = html.Div([   
    html.Div([
    dcc.Graph(
        style={"height": "inherit"},
        id="spectrum-graph",
        figure=fig_dummy
    )], className="monitor_card"),
])
def generate_doa_page_layout(webInterface_inst):
    doa_page_layout = html.Div([        
        html.Div([    
        dcc.Graph(
            style={"height": "inherit"},
            id="doa-graph",
            figure=fig_dummy
        )], className="monitor_card"),
    ])
    return doa_page_layout

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
            elif data_entry[0] == "disconn-ok":     
                webInterface_inst.daq_conn_status = 0
            elif data_entry[0] == "config-ok":                      
                webInterface_inst.daq_cgf_iface_status = 0

        
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
                
                if iq_header.frame_type == iq_header.FRAME_TYPE_DATA:
                    webInterface_inst.daq_frame_type  = "Data"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_DUMMY:
                    webInterface_inst.daq_frame_type  = "Dummy"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_CAL:
                    webInterface_inst.daq_frame_type  = "Calibration"
                elif iq_header.frame_type == iq_header.FRAME_TYPE_TRIGW:
                    webInterface_inst.daq_frame_type  = "Trigger wait"
                else:
                    webInterface_inst.daq_frame_type  = "Unknown"

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
                webInterface_inst.max_amplitude = data_entry[1]                
            elif data_entry[0] == "avg_powers":                
                avg_powers_str = ""
                for avg_power in data_entry[1]:
                    avg_powers_str+="{:.1f}".format(avg_power)
                    avg_powers_str+=", "
                webInterface_inst.avg_powers = avg_powers_str[:-2]                
            elif data_entry[0] == "spectrum":
                logging.debug("Spectrum data fetched from signal processing que")
                spectrum_update_flag = 1
                webInterface_inst.spectrum = data_entry[1]
            elif data_entry[0] == "doa_thetas":
                webInterface_inst.doa_thetas= data_entry[1]
                doa_update_flag                   = 1
                webInterface_inst.doa_results     = []
                webInterface_inst.doa_labels      = []
                webInterface_inst.doas            = []
                webInterface_inst.doa_confidences = []
                logging.debug("DoA estimation data fetched from signal processing que")                
            elif data_entry[0] == "DoA Bartlett":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "DoA Bartlett Max":
                webInterface_inst.doas.append(data_entry[1])
            elif data_entry[0] == "DoA Barlett confidence":
                webInterface_inst.doa_confidences.append(data_entry[1])
            elif data_entry[0] == "DoA Capon":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "DoA Capon Max":
                webInterface_inst.doas.append(data_entry[1])
            elif data_entry[0] == "DoA Capon confidence":
                webInterface_inst.doa_confidences.append(data_entry[1])
            elif data_entry[0] == "DoA MEM":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "DoA MEM Max":
                webInterface_inst.doas.append(data_entry[1])
            elif data_entry[0] == "DoA MEM confidence":
                webInterface_inst.doa_confidences.append(data_entry[1])
            elif data_entry[0] == "DoA MUSIC":
                webInterface_inst.doa_results.append(data_entry[1])
                webInterface_inst.doa_labels.append(data_entry[0])
            elif data_entry[0] == "DoA MUSIC Max":
                webInterface_inst.doas.append(data_entry[1])
            elif data_entry[0] == "DoA MUSIC confidence":
                webInterface_inst.doa_confidences.append(data_entry[1])
            else:                
                logging.warning("Unknown data entry: {:s}".format(data_entry[0]))
        
    except queue.Empty:
        # Handle empty queue here
        logging.debug("Signal processing que is empty")
    else:
        pass
        # Handle task here and call q.task_done()
    # External interface
    if doa_update_flag:
        DOA_str = str(int(webInterface_inst.doas[0]))
        confidence_str  = "{:.2f}".format(np.max(webInterface_inst.doa_confidences))
        max_power_level_str = "{:.1f}".format((np.maximum(-100, webInterface_inst.max_amplitude)))
        html_str = "<DATA>\n<DOA>"+DOA_str+"</DOA>\n<CONF>"+confidence_str+"</CONF>\n<PWR>"+max_power_level_str+"</PWR>\n</DATA>"
        webInterface_inst.DOA_res_fd.seek(0)
        webInterface_inst.DOA_res_fd.write(html_str)
        webInterface_inst.DOA_res_fd.truncate()
        logging.debug("DoA results writen: {:s}".format(html_str))    

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
    Output(component_id="body_daq_frame_type"         , component_property='children'),
    Output(component_id="body_daq_frame_type"         , component_property='style'),    
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
    Output(component_id="body_max_amp"                , component_property='children'),
    Output(component_id="body_avg_powers"             , component_property='children'),    
    Input(component_id ="placeholder_config_page_upd" , component_property='children'),    
    prevent_initial_call=True
)
def update_daq_status(input_value):         
     
    
    #############################################
    #      Prepare UI component properties      #
    #############################################
    
    if webInterface_inst.daq_conn_status:
        if not webInterface_inst.daq_cgf_iface_status:
            daq_conn_status_str = "Connected"
            conn_status_style={"color": "green"}
        else: # Config interface is busy
            daq_conn_status_str = "Reconfiguration.."
            conn_status_style={"color": "orange"}
    else:
        daq_conn_status_str = "Disconnected"
        conn_status_style={"color": "red"}

    if webInterface_inst.daq_update_rate < 1:
        daq_update_rate_str    = "{:.2f} ms".format(webInterface_inst.daq_update_rate*1000)
    else:
        daq_update_rate_str    = "{:.2f} s".format(webInterface_inst.daq_update_rate)

    daq_frame_index_str    = str(webInterface_inst.daq_frame_index)
    
    daq_frame_type_str =  webInterface_inst.daq_frame_type
    if webInterface_inst.daq_frame_type == "Data":
        frame_type_style   = frame_type_style={"color": "green"} 
    elif webInterface_inst.daq_frame_type == "Dummy":
        frame_type_style   = frame_type_style={"color": "white"} 
    elif webInterface_inst.daq_frame_type == "Calibration":
        frame_type_style   = frame_type_style={"color": "orange"} 
    elif webInterface_inst.daq_frame_type == "Trigger wait":
        frame_type_style   = frame_type_style={"color": "yellow"}
    else:
        frame_type_style   = frame_type_style={"color": "red"}    

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
    daq_max_amp_str        = "{:.1f}".format(webInterface_inst.max_amplitude)
    daq_avg_powers_str     = webInterface_inst.avg_powers
    
    return daq_update_rate_str, daq_frame_index_str, daq_frame_sync_str, \
            frame_sync_style, daq_frame_type_str, frame_type_style, \
            daq_power_level_str, daq_conn_status_str, \
            conn_status_style, daq_delay_sync_str, delay_sync_style, \
            daq_iq_sync_str, iq_sync_style, daq_noise_source_str, \
            noise_source_style, daq_rf_center_freq_str, daq_sampling_freq_str, \
            daq_cpi_str, webInterface_inst.daq_if_gains, daq_max_amp_str, \
            daq_avg_powers_str
            


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
                        tickfont_size=figure_font_size,
                        mirror=True,
                        ticks='outside',
                        showline=True)
        fig.update_yaxes(title_text="Amplitude [dB]",
                        color='rgba(255,255,255,1)', 
                        title_font_size=20, 
                        tickfont_size=figure_font_size, 
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
        # --- Linear plot ---
        if webInterface_inst._doa_fig_type == 0 : 
            # Plot traces 
            for i, doa_result in enumerate(webInterface_inst.doa_results):                 
                label = webInterface_inst.doa_labels[i]+": "+str(webInterface_inst.doas[i])+"°"
                fig.add_trace(go.Scatter(x=webInterface_inst.doa_thetas, 
                                        y=doa_result,
                                        name=label,
                                        line = dict(
                                                    color = doa_trace_colors[webInterface_inst.doa_labels[i]],
                                                    width = 3)
                            ))
            
            fig.update_xaxes(title_text="Incident angle [deg]", 
                            color='rgba(255,255,255,1)', 
                            title_font_size=20, 
                            tickfont_size=figure_font_size,
                            mirror=True,
                            ticks='outside',
                            showline=True)
            fig.update_yaxes(title_text="Amplitude [dB]",
                            color='rgba(255,255,255,1)', 
                            title_font_size=20, 
                            tickfont_size=figure_font_size, 
                            #range=[-5, 5],
                            mirror=True,
                            ticks='outside',
                            showline=True)
        # --- Polar plot ---
        elif webInterface_inst._doa_fig_type == 1:
            if webInterface_inst.module_signal_processor.DOA_ant_alignment == "ULA":           
                fig.update_layout(polar = dict(sector = [0, 180], 
                                               radialaxis_tickfont_size = figure_font_size,
                                               angularaxis = dict(rotation=90,                                                                  
                                                                  tickfont_size = figure_font_size
                                                                  )
                                                )
                                 )                
            else: #UCA                
                fig.update_layout(polar = dict(radialaxis_tickfont_size = figure_font_size,
                                               angularaxis = dict(rotation=90,                                                                   
                                                                  tickfont_size = figure_font_size)                                               
                                               )
                                 )           

            for i, doa_result in enumerate(webInterface_inst.doa_results):
                label = webInterface_inst.doa_labels[i]+": "+str(webInterface_inst.doas[i])+"°"
                fig.add_trace(go.Scatterpolar(theta=webInterface_inst.doa_thetas, 
                                            r=doa_result,
                                            name=label,
                                            line = dict(color = doa_trace_colors[webInterface_inst.doa_labels[i]]),
                                            fill= 'toself'
                                            ))
                fig.add_trace(go.Scatterpolar(
                                                r = [0,min(doa_result)],
                                                theta = [webInterface_inst.doas[i],
                                                         webInterface_inst.doas[i]],
                                                mode = 'lines',
                                                showlegend=False,                                                      
                                                line = dict(
                                                    color = doa_trace_colors[webInterface_inst.doa_labels[i]],
                                                    dash='dash'
                                                )))
            # --- Compass  ---
        elif webInterface_inst._doa_fig_type == 2 :
            #thetas_compass = webInterface_inst.doa_thetas[::-1]            
            #thetas_compass += webInterface_inst.compass_ofset
            if webInterface_inst.module_signal_processor.DOA_ant_alignment == "ULA":             
                fig.update_layout(polar = dict(sector = [0, 180], 
                                            radialaxis_tickfont_size = figure_font_size,
                                            angularaxis = dict(rotation=90+webInterface_inst.compass_ofset,
                                                                direction="clockwise",
                                                                tickfont_size = figure_font_size
                                                                )
                                                )
                                )                
            else: #UCA                
                fig.update_layout(polar = dict(radialaxis_tickfont_size = figure_font_size,
                                            angularaxis = dict(rotation=90+webInterface_inst.compass_ofset, 
                                                                direction="clockwise",
                                                                tickfont_size = figure_font_size)                                               
                                            )
                                )           

            for i, doa_result in enumerate(webInterface_inst.doa_results):                 
                if webInterface_inst.module_signal_processor.DOA_ant_alignment == "ULA":
                    doa_compass = 0-webInterface_inst.doas[i]+webInterface_inst.compass_ofset
                    
                else:
                    doa_compass = (360-webInterface_inst.doas[i]+webInterface_inst.compass_ofset)%360
                label = webInterface_inst.doa_labels[i]+": "+str(doa_compass)+"°"           
                """
                fig.add_trace(go.Scatterpolar(theta=thetas_compass, 
                                            r=doa_result,
                                            name=label,
                                            line = dict(color = doa_trace_colors[webInterface_inst.doa_labels[i]]),
                                            fill= 'toself'
                                            ))
                """
                fig.add_trace(go.Scatterpolar(
                                                r = [0,min(doa_result)],
                                                theta = [doa_compass,
                                                         doa_compass],
                                                mode = 'lines',
                                                name = label,
                                                showlegend=True,                                                      
                                                line = dict(
                                                    color = doa_trace_colors[webInterface_inst.doa_labels[i]],
                                                    dash='dash'
                                                )))

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
    Input(component_id ="btn-update_rx_param"   , component_property="n_clicks"),
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
    webInterface_inst.daq_cgf_iface_status = 1
    webInterface_inst.module_receiver.set_center_freq(int(f0*10**6))
    webInterface_inst.module_receiver.set_if_gain(int(10*gain))
    
    logging.info("Updating receiver parameters: {0}".format(input_value))
    logging.info("Center frequency: {:f}".format(webInterface_inst.center_freq))
        
    return  ""
    
@app.callback(
    Output(component_id="placeholder_update_squelch", component_property="children"),    
    Input(component_id ="en_dsp_squelch_check"  , component_property="value"),
    Input(component_id ="squelch_th"            , component_property="value"),
    prevent_initial_call=True
)
def update_squelch_params(en_dsp_squelch, squelch_threshold):
    """
    squelch_threshold = 0
    """

    if en_dsp_squelch is not None and len(en_dsp_squelch):
        webInterface_inst.module_signal_processor.en_squelch = True
    else:
        webInterface_inst.module_signal_processor.en_squelch = False

    webInterface_inst.daq_cgf_iface_status = 0
    webInterface_inst.module_signal_processor.squelch_threshold = 10**(squelch_threshold/20)
    webInterface_inst.module_receiver.set_squelch_threshold(squelch_threshold)
    webInterface_inst.squelch_th = squelch_threshold
    return 0
    

@app.callback(
    Output(component_id="placeholder_recofnig_daq" , component_property="children"),    
    Input(component_id="btn_reconfig_daq_chain"    , component_property="n_clicks"),
    State(component_id='cfg_rx_channels'          , component_property="value"),
    State(component_id='cfg_daq_buffer_size'      , component_property="value"),
    State(component_id='cfg_sample_rate'          , component_property="value"),
    State(component_id="en_noise_source_ctr"      , component_property="value"),
    State(component_id="en_squelch_mode"          , component_property="value"),
    State(component_id='cfg_squelch_init_th'      , component_property="value"),
    State(component_id='cfg_cpi_size'             , component_property="value"),
    State(component_id='cfg_decimation_ratio'     , component_property="value"),
    State(component_id='cfg_fir_bw'               , component_property="value"),
    State(component_id='cfg_fir_tap_size'         , component_property="value"),
    State(component_id='cfg_fir_window'           , component_property="value"),
    State(component_id="en_filter_reset"          , component_property="value"),
    State(component_id='cfg_corr_size'            , component_property="value"),
    State(component_id='cfg_std_ch_ind'           , component_property="value"),
    State(component_id="en_iq_cal"                , component_property="value"),
    State(component_id='cfg_gain_lock'            , component_property="value"),
    State(component_id="en_req_track_lock_intervention", component_property="value"),
    State(component_id='cfg_cal_track_mode'       , component_property="value"),
    State(component_id='cfg_cal_frame_interval'   , component_property="value"),
    State(component_id='cfg_cal_frame_burst_size' , component_property="value"),
    State(component_id='cfg_amplitude_tolerance'  , component_property="value"),
    State(component_id='cfg_phase_tolerance'      , component_property="value"),
    State(component_id='cfg_max_sync_fails'       , component_property="value"),
    prevent_initial_call=True
)
def reconfig_daq_chain(input_value,
                    cfg_rx_channels,cfg_daq_buffer_size,cfg_sample_rate,en_noise_source_ctr,                    
                    en_squelch_mode,cfg_squelch_init_th,cfg_cpi_size,cfg_decimation_ratio,
                    cfg_fir_bw,cfg_fir_tap_size,cfg_fir_window,en_filter_reset,cfg_corr_size,
                    cfg_std_ch_ind,en_iq_cal,cfg_gain_lock,en_req_track_lock_intervention,
                    cfg_cal_track_mode,cfg_cal_frame_interval,cfg_cal_frame_burst_size,
                    cfg_amplitude_tolerance,cfg_phase_tolerance,cfg_max_sync_fails):
    
    if input_value is None:
        raise PreventUpdate

    # TODO: Check data interface mode here !
    """
        Update DAQ Subsystem config file
    """
    param_list = []
    param_list.append(cfg_rx_channels)
    param_list.append(cfg_daq_buffer_size)
    param_list.append(int(cfg_sample_rate*10**6))
    if en_noise_source_ctr is not None and len(en_noise_source_ctr):
        param_list.append(1)
    else:
        param_list.append(0)
    if en_squelch_mode is not None and len(en_squelch_mode):
        param_list.append(1)
    else:
        param_list.append(0)        
    param_list.append(cfg_squelch_init_th)
    param_list.append(cfg_cpi_size)
    param_list.append(cfg_decimation_ratio)
    param_list.append(cfg_fir_bw)
    param_list.append(cfg_fir_tap_size)
    param_list.append(cfg_fir_window)
    if en_filter_reset is not None and len(en_filter_reset):
        param_list.append(1)
    else:
        param_list.append(0)     
    param_list.append(cfg_corr_size)
    param_list.append(cfg_std_ch_ind)
    if en_iq_cal is not None and len(en_iq_cal):
        param_list.append(1)
    else:
        param_list.append(0) 
    param_list.append(cfg_gain_lock)
    if en_req_track_lock_intervention is not None and len(en_req_track_lock_intervention):
        param_list.append(1)
    else:
        param_list.append(0) 
    param_list.append(cfg_cal_track_mode)
    param_list.append(cfg_cal_frame_interval)
    param_list.append(cfg_cal_frame_burst_size)
    param_list.append(cfg_amplitude_tolerance)
    param_list.append(cfg_phase_tolerance)
    param_list.append(cfg_max_sync_fails)

    webInterface_inst.write_config_file(param_list)
    logging.info("DAQ Subsystem configuration file edited")
    
    """
        Restart DAQ Subsystem
    """
    # Stop signal processing
    webInterface_inst.stop_processing()   
    time.sleep(2)
    logging.debug("Signal processing stopped")

    # Close control and IQ data interfaces
    webInterface_inst.close_data_interfaces()
    logging.debug("Data interfaces are closed")

    os.chdir(daq_subsystem_path)

    # Kill DAQ subsystem
    daq_stop_script = subprocess.Popen(['bash', daq_stop_filename])#, stdout=subprocess.DEVNULL)
    daq_stop_script.wait()
    logging.debug("DAQ Subsystem halted")
    
    # Start DAQ subsystem
    daq_stop_script = subprocess.Popen(['bash', daq_start_filename])#, stdout=subprocess.DEVNULL)
    daq_stop_script.wait()
    logging.debug("DAQ Subsystem restarted")
    
    os.chdir(root_path)

    # Reinitialize receiver data interface
    if webInterface_inst.module_receiver.init_data_iface() == -1:
        logging.critical("Failed to restart the DAQ data interface")
        return -1
    
    # Restart signal processing
    webInterface_inst.start_processing()
    logging.debug("Signal processing started")
        
    return 0

@app.callback(
    Output(component_id="placeholder_update_dsp", component_property="children"),
    Output(component_id="ant_spacing_wavelength", component_property="value"),
    Output(component_id="ant_spacing_meter"     , component_property="value"),
    Output(component_id="ant_spacing_feet"      , component_property="value"),
    Output(component_id="ant_spacing_inch"      , component_property="value"),    
    Input(component_id="placeholder_update_freq", component_property="children"),
    Input(component_id="en_spectrum_check"      , component_property="value"),
    Input(component_id="en_doa_check"           , component_property="value"),
    Input(component_id="doa_method"             , component_property="value"),    
    Input(component_id="en_fb_avg_check"        , component_property="value"),
    Input(component_id="ant_spacing_wavelength" , component_property="value"),
    Input(component_id="ant_spacing_meter"      , component_property="value"),
    Input(component_id="ant_spacing_feet"       , component_property="value"),
    Input(component_id="ant_spacing_inch"       , component_property="value"),
    Input(component_id="radio_ant_arrangement"  , component_property="value"),
    Input(component_id='doa_fig_type'           , component_property='value'),
    Input(component_id='compass_ofset'          , component_property='value'),    

    prevent_initial_call=True
)
def update_dsp_params(freq_update, en_spectrum, en_doa, doa_method,
                      en_fb_avg, spacing_wavlength, spacing_meter, spacing_feet, spacing_inch,
                      ant_arrangement, doa_fig_type, compass_ofset):
    ctx = dash.callback_context
    
    if ctx.triggered:
        component_id = ctx.triggered[0]['prop_id'].split('.')[0]
        wavelength= 300 / webInterface_inst.daq_center_freq
        
        if component_id   == "placeholder_update_freq": 
            ant_spacing_meter = spacing_meter  
        else:
            ant_spacing_meter = round(wavelength * webInterface_inst.module_signal_processor.DOA_inter_elem_space,3)
        
        if component_id   == "ant_spacing_meter":
            ant_spacing_meter = spacing_meter
        elif component_id == "ant_spacing_wavelength":
            ant_spacing_meter = wavelength*spacing_wavlength
        elif component_id == "ant_spacing_feet":
            ant_spacing_meter = spacing_feet/3.2808399
        elif component_id == "ant_spacing_inch":
            ant_spacing_meter = spacing_inch/39.3700787
        
        webInterface_inst.module_signal_processor.DOA_inter_elem_space = ant_spacing_meter / wavelength
        ant_spacing_feet = round(ant_spacing_meter * 3.2808399,3)
        ant_spacing_inch = round(ant_spacing_meter * 39.3700787,3)
        ant_spacing_wavlength = round(ant_spacing_meter / wavelength,3)

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
    
    webInterface_inst._doa_method=doa_method
    if doa_method == 0:
        webInterface_inst.module_signal_processor.en_DOA_Bartlett = True
        webInterface_inst.module_signal_processor.en_DOA_Capon    = False
        webInterface_inst.module_signal_processor.en_DOA_MEM      = False
        webInterface_inst.module_signal_processor.en_DOA_MUSIC    = False
    elif doa_method == 1:
        webInterface_inst.module_signal_processor.en_DOA_Bartlett = False
        webInterface_inst.module_signal_processor.en_DOA_Capon    = True
        webInterface_inst.module_signal_processor.en_DOA_MEM      = False
        webInterface_inst.module_signal_processor.en_DOA_MUSIC    = False
    elif doa_method == 2:
        webInterface_inst.module_signal_processor.en_DOA_Bartlett = False
        webInterface_inst.module_signal_processor.en_DOA_Capon    = False
        webInterface_inst.module_signal_processor.en_DOA_MEM      = True
        webInterface_inst.module_signal_processor.en_DOA_MUSIC    = False
    elif doa_method == 3:
        webInterface_inst.module_signal_processor.en_DOA_Bartlett = False
        webInterface_inst.module_signal_processor.en_DOA_Capon    = False
        webInterface_inst.module_signal_processor.en_DOA_MEM      = False
        webInterface_inst.module_signal_processor.en_DOA_MUSIC    = True

    if en_fb_avg is not None and len(en_fb_avg):
        logging.debug("FB averaging enabled")
        webInterface_inst.module_signal_processor.en_DOA_FB_avg   = True
    else:
        webInterface_inst.module_signal_processor.en_DOA_FB_avg   = False
    
    webInterface_inst.module_signal_processor.DOA_ant_alignment=ant_arrangement
    webInterface_inst._doa_fig_type = doa_fig_type
    webInterface_inst.compass_ofset = compass_ofset

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
        return generate_doa_page_layout(webInterface_inst), "header_inactive", "header_inactive", "header_active"

if __name__ == "__main__":        
    webInterface_inst = webInterface()
    app.run_server(debug=False, host="0.0.0.0")

# Debug mode does not work when the data interface is set to shared-memory "shmem"! 

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