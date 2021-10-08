import dash_html_components as html
import dash_bootstrap_components as dbc

dsp_config_tooltips = html.Div([
    # Antenna arrangement selection
    dbc.Tooltip([
        html.P("ULA - Uniform Linear Array"),
        html.P("Antenna elements placed on a line with having equal distances between each other"),
        html.P("UCA - Uniform Circular Array"),
        html.P("Antenna elements are placed on circle equaly distributed on 360°")],        
        target="label_ant_arrangement",
        placement="bottom",
        className="tooltip"
        ),
    # Antenna Spacing
    dbc.Tooltip([
        html.P("When ULA is selected: Spacing between antenna elements"),
        html.P("When UCA is selected: Radius of the circle on which the elements are placed")],
        target="label_ant_spacing",
        placement="bottom",
        className="tooltip"
        ),
    # Enable F-B averaging
    dbc.Tooltip([
        html.P("Forward-backward averegaing improves the performance of DoA estimation in multipath environment"),
        html.P("(Available only for ULA antenna systems)")],
        target="label_en_fb_avg",
        placement="bottom",
        className="tooltip"
        ),
        ])

daq_ini_config_tooltips = html.Div([
    # DAQ buffer size
    dbc.Tooltip([
        html.P("Buffer size of the realtek driver")],
        target="label_daq_buffer_size",
        placement="bottom",
        className="tooltip"
        ),
    # Sampling frequency
    dbc.Tooltip([
        html.P("Raw - ADC sampling frequency of the realtek chip")],
        target="label_sample_rate",
        placement="bottom",
        className="tooltip"
        ),
    # Enable noise source control
    dbc.Tooltip([
        html.P("Enables the utilization of the built-in noise source for calibration")],
        target="label_en_noise_source_ctr",
        placement="bottom",
        className="tooltip"
        ),
    # Enable squelch mode
    dbc.Tooltip([
        html.P("Enable squelch to capture burst like signals")],
        target="label_en_squelch",
        placement="bottom",
        className="tooltip"
        ),
    # Squelch threshold
    dbc.Tooltip([
        html.P("Amplitude threshold used for the squelch feature."),
        html.P("Should take values on range: 0...1"),
        html.P("When set to zero the squelch is bypassed")],
        target="label_squelch_init_threshold",
        placement="bottom",
        className="tooltip"
        ),
    # CPI size
    dbc.Tooltip([
        html.P("Length of the Coherent Processing Interval after decimation")],
        target="label_cpi_size",
        placement="bottom",
        className="tooltip"
        ),
    # Decimation raito
    dbc.Tooltip([
        html.P("Raw sampling frequency is decreased with the decimation ratio")],
        target="label_decimation_ratio",
        placement="bottom",
        className="tooltip"
        ),
    # FIR relative bandwidth
    dbc.Tooltip([
        html.P("Anti-aliasing filter bandwith after decimation"),
        html.P("Should take values on range: (0, 1]"),
        html.P("E.g.: ADC sampling frequency: 1 MHz (IQ!) , Decimation ratio: 2,  FIR relative bandwith:0.25"),
        html.P("Resulting passband bandwidth: 125 kHz ")],
        target="label_fir_relative_bw",
        placement="bottom",
        className="tooltip"
        ),
    # FIR tap size
    dbc.Tooltip([
        html.P("Anti-aliasing FIR filter tap size"),
        html.P("Should be greater than the decimation ratio")],
        target="label_fir_tap_size",
        placement="bottom",
        className="tooltip"
        ),            
    # FIR tap size
    dbc.Tooltip([
        html.P("Window function type for designing the anti-aliasing FIR filter"),
        html.P("https://en.wikipedia.org/wiki/Window_function")],
        target="label_fir_window",
        placement="bottom",
        className="tooltip"
        ),
    # Enable filter reset
    dbc.Tooltip([
        html.P("If enabled, the memory of the anti-aliasing FIR filter is reseted at the begining of every new CPI")],
        target="label_en_filter_reset",
        placement="bottom",
        className="tooltip"
        ),  
    # Correlation size
    dbc.Tooltip([
        html.P("Number of samples used for the calibration procedure (sample delay and IQ compensation)")],
        target="label_correlation_size",
        placement="bottom",
        className="tooltip"
        ),
    # Standard channel index
    dbc.Tooltip([
        html.P("The selected channel is used as a reference for the IQ compensation")],
        target="label_std_ch_index",
        placement="bottom",
        className="tooltip"
        ),
    # Enable IQ calibration
    dbc.Tooltip([
        html.P("Enables to compensate the amplitude and phase differences of the receiver channels")],
        target="label_en_iq_calibration",
        placement="bottom",
        className="tooltip"
        ),
    # Gain lock interval
    dbc.Tooltip([
        html.P("Minimum number of stable frames before terminating the gain tuning procedure")],
        target="label_gain_lock_interval",
        placement="bottom",
        className="tooltip"
        ),
    # Require track lock intervention
    dbc.Tooltip([
        html.P("When enabled the DAQ firmware waits for manual intervention during the calibraiton procedure"),
        html.P("Should be used only for hardave version 1.0")],
        target="label_require_track_lock",
        placement="bottom",
        className="tooltip"
        ),
    # Amplitude calibraiton mode
    dbc.Tooltip([
        html.P("Amplitude difference compensation method applied as part of the IQ compensation"),
        html.P("default: Amplitude differences are estimated by calculating the cross-correlations of the channels"),
        html.P("disabled: Amplitude differences are not compensated"),
        html.P("channel_power: Ampltiude compensation is set in a way to achieve equal channel powers")],
        target="label_amplitude_calibration_mode",
        placement="bottom",
        className="tooltip"
        ),
    dbc.Tooltip([
        html.P("When periodic calibration track mode is selected the firmware regularly turn on the noise source for a short burst to\
            check whether the IQ calibration is still valid or not. In case the calibrated state is lost, the firmware automatically\
                initiates a reclaibration procedure")],
        target="label_calibration_track_mode",
        placement="bottom",
        className="tooltip"
        ),
        
    # Calibration frame interval
    dbc.Tooltip([
        html.P("Number of data frames between two consecutive calibration burst. Used when periodic calibration mode is selected")],
        target="label_calibration_frame_interval",
        placement="bottom",
        className="tooltip"
        ),
    # Calibration frame burst size
    dbc.Tooltip([
        html.P("Number of calibration frames generated in the periodic calibration mode")],
        target="label_calibration_frame_burst_size",
        placement="bottom",
        className="tooltip"
        ),
    # Amplitude tolerance
    dbc.Tooltip([
        html.P("Maximum allowed amplitude difference between the receiver channels")],
        target="label_amplitude_tolerance",
        placement="bottom",
        className="tooltip"
        ),
    # Phase tolerance
    dbc.Tooltip([
        html.P("Maximum allowed phase difference between the receiver channels")],
        target="label_phase_tolerance",
        placement="bottom",
        className="tooltip"
        ),
    # Maximum sync fails
    dbc.Tooltip([
        html.P("Maximum allowed consecutive IQ difference check failes before initiating a recalibraiton")],
        target="label_max_sync_fails",
        placement="bottom",
        className="tooltip"
        ),
    ])

        