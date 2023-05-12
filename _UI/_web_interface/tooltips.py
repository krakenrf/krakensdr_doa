import dash_bootstrap_components as dbc
import dash_html_components as html

dsp_config_tooltips = html.Div(
    [
        # Antenna arrangement selection
        dbc.Tooltip(
            [
                html.P("ULA - Uniform Linear Array"),
                html.P(
                    "Antenna elements placed on a line with equal distances between each other. Cannot determine if the source is behind or in front of array without additional information."
                ),
                html.P("UCA - Uniform Circular Array"),
                html.P(
                    "Antenna elements are placed on a circle equaly distributed at some radius around 360°. UCA is the most common array."
                ),
                html.P("Custom - Custom Array"),
                html.P(
                    "Input custom array coordinates in meters as comma seperated values. Useful for irregular arrays."
                ),
            ],
            target="label_ant_arrangement",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Spacing of the array specified in meters. For ULA the interelement spacing. For UCA the radius.")],
            target="label_ant_spacing_meter",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("Calculation of the array spacing in wavelength. Depends on frequency and array size."),
                html.P(
                    "This must be kept under 0.5 to avoid ambiguities (more than one valid bearing). Closer to 0.5 results in better angular resolution."
                ),
            ],
            target="label_ant_spacing_wavelength",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("DoA Algorithms. MUSIC works the best in almost all situations.")],
            target="label_doa_method",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("The number of active VFO channels available to use in the active spectrum.")],
            target="label_active_vfos",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Choose which VFO channel is output to the DOA graphs and data stream. In the spectrum graph this chooses what VFO channel click to tune will move."
                ),
                html.P(
                    "ALL - Outputs data from all active VFOs to the Kraken App / Kraken Pro App output data stream for simultaenous channel monitoring."
                ),
                html.P(
                    "Note that outputting more than 3 active VFOs on a Pi 4 may result in slow computation, resulting in intermittant signal squelch misses. To get around this, you can apply decimation to make computation more efficient."
                ),
            ],
            target="label_output_vfo",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Decimate the spectrum. Reduces spectrum bandwidth for zooming in on signals. If you will always decimate, it is more efficient to apply decimation in the DAQ settings. "
                )
            ],
            target="label_dsp_side_decimation",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Enhance squelcher detection of very narrow bandwidth and short bursty signals with pulse lengths 50ms or less."
                )
            ],
            target="label_optimize_short_bursts",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("Linear - A simple line plot of the DoA data. "),
                html.P("Polar - A circular plot in polar form. "),
                html.P(
                    "Compass - The same as the polar plot, but axis in the compass convention with 90 degrees clockwise from zero. Can be offset by some degrees in order to align the graph with the array heading. "
                ),
            ],
            target="label_doa_graph_type",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Add a peak hold plot to the spectrum. Only works in 'Single Ch' spectrum calculation mode. ")],
            target="label_peak_hold",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Single Ch - Normal use. You must use this for intermittant signal squelching to work correctly."
                ),
                html.P(
                    "All Ch - Only ever use this to test your antenna array connections. This mode will allow you to view all channels in the spectrum graph. Will NOT work with intermittant signals."
                ),
            ],
            target="label_spectrum_calculation",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("Standard - VFOs are set manually."),
                html.P(
                    "VFO-0 Auto Max - VFO-0 will auto tune to the strongest signal in the spectrum. Only supports a single VFO."
                ),
            ],
            target="label_vfo_mode",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("VFO Default Demodulation that could be either None or FM"),
                html.P("FM - frequency demodulation"),
            ],
            target="label_vfo_default_demod",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("VFO Default IQ wtiting mode"),
                html.P("False - disable writing IQ samples, True - enable writing IQ samples to file"),
            ],
            target="label_vfo_default_iq",
            placement="bottom",
            className="tooltip",
        ),
        # Antenna Spacing
        #    dbc.Tooltip([
        #        html.P("When ULA is selected: Spacing between antenna elements"),
        #        html.P("When UCA is selected: Radius of the circle on which the elements are placed")],
        #        target="label_ant_spacing",
        #        placement="bottom",
        #        className="tooltip"
        #        ),
        # Enable F-B averaging
        dbc.Tooltip(
            [
                html.P(
                    "Decorrelation methods that might improve performance of DoA estimation in multipath and (or) low SNR environments."
                )
            ],
            target="label_decorrelation",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "If the 0 degree direction of the array is not in-line with the heading of the vehicle, use this to offset the array."
                ),
                html.P(
                    "For example, if you are using a linear array with the broadside not facing the front of the car."
                ),
            ],
            target="label_array_offset",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "DoA methods that separate noise and signal subspaces, such as MUSIC, require a priori knowledge of number of signal sources."
                ),
                html.P("Setting this to larger than expected number of rf sources might give misleading results."),
            ],
            target="label_expected_num_of_sources",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Linear arrays cannot differentiate between a signal in front or behind the array. If you have prior knowledge about the signal source location, choose if the signal is in front or behind the array."
                )
            ],
            target="label_ula_direction",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Enter the filename for the recording.")],
            target="filename_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("The data output format for the file recording. Currently only Kraken App is available.")],
            target="data_format_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "How often data to the file will be written. If you are making very long recordings, increase to avoid the filesize becoming too large."
                )
            ],
            target="write_interval_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Enable writing data to local file.")],
            target="label_en_data_record",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Please ensure that there is sufficient space on your device for the data file.")],
            target="label_file_size",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "How long it takes to compute. Should be faster than the data block length, so that no frames are dropped. "
                )
            ],
            target="label_daq_update_rate",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Time taken from signal entry to data output.")],
            target="label_daq_dsp_latency",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Frame counter. Each frame contains one block of sampled IQ data. If it's incrementing by more than one each time, then we're dropping frames."
                )
            ],
            target="label_daq_frame_index",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Frame type indicates if the frame contains data, or is used for calibration, or a dummy frame for flushing buffers."
                )
            ],
            target="label_daq_frame_type",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("If OK, we are receiving frames successfully.")],
            target="label_daq_frame_sync",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "If Overdrive, the signal strength may be too strong. Try reducing the gain. Operating in overdrive is fine in most situations."
                )
            ],
            target="label_daq_power_level",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Are we connected to the DAQ.")],
            target="label_daq_conn_status",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Do we have sample level coherent sync.")],
            target="label_daq_delay_sync",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Do we have phase level coherent sync.")],
            target="label_daq_iq_sync",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("The noise source will automatically enable during calibration.")],
            target="label_daq_noise_source",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("The currently tuned center frequency. Change in the RF Receiver Configuration card.")],
            target="label_daq_rf_center_freq",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Total RF bandwidth from the DAQ.")],
            target="label_daq_sampling_freq",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Total bandwidth after DSP side decimation.")],
            target="label_dsp_decimated_bw",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Minimum and maximum possible VFO frequencies in available bandwidth.")],
            target="label_vfo_range",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Length of time IQ data is collected for in each frame. Longer results in more processing gain, but slower update rates. Also affects computation time."
                )
            ],
            target="label_daq_cpi",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Currently set RF gains on each channel. Set in RF Receiver Configuration settings.")],
            target="label_daq_if_gain",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Signal power of VFO-0 in dB.")],
            target="label_max_amp",
            placement="bottom",
            className="tooltip",
        ),
    ]
)

daq_ini_config_tooltips = html.Div(
    [
        dbc.Tooltip(
            [html.P("Edit DAQ settings. For most users these settings should never be touched.")],
            target="label_en_basic_daq_cfg",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Length of IQ data collection time for each frame. Modifies the CPI size in advanced settings.")],
            target="label_daq_config_data_block_len",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Choose a sampling bandwidth. Can only be an integer division of the RTL-SDR sampling rate.")],
            target="label_daq_decimated_bw",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "How often should the system check on coherence calibration. Checks take a few seconds, and a reasonable time is every 5-10 minutes."
                )
            ],
            target="label_recal_interval",
            placement="bottom",
            className="tooltip",
        ),
        # DAQ buffer size
        dbc.Tooltip(
            [html.P("Buffer size of the realtek driver")],
            target="label_daq_buffer_size",
            placement="bottom",
            className="tooltip",
        ),
        # Sampling frequency
        dbc.Tooltip(
            [html.P("Raw - ADC sampling frequency of the realtek chip")],
            target="label_sample_rate",
            placement="bottom",
            className="tooltip",
        ),
        # Enable noise source control
        dbc.Tooltip(
            [html.P("Enables the utilization of the built-in noise source for calibration")],
            target="label_en_noise_source_ctr",
            placement="bottom",
            className="tooltip",
        ),
        # CPI size
        dbc.Tooltip(
            [html.P("Length of the Coherent Processing Interval (CPI) after decimation")],
            target="label_cpi_size",
            placement="bottom",
            className="tooltip",
        ),
        # Decimation raito
        dbc.Tooltip(
            [html.P("Decimation factor")],
            target="label_decimation_ratio",
            placement="bottom",
            className="tooltip",
        ),
        # FIR relative bandwidth
        dbc.Tooltip(
            [
                html.P("Anti-aliasing filter bandwith after decimation"),
                html.P("Should take values on range: (0, 1]"),
                html.P("E.g.: ADC sampling frequency: 1 MHz (IQ!) , Decimation ratio: 2,  FIR relative bandwith:0.25"),
                html.P("Resulting passband bandwidth: 125 kHz "),
            ],
            target="label_fir_relative_bw",
            placement="bottom",
            className="tooltip",
        ),
        # FIR tap size
        dbc.Tooltip(
            [
                html.P("Anti-aliasing FIR filter tap size - Do not set too large, or CPU utilization will be 100%"),
                html.P("Should be greater than the decimation ratio"),
            ],
            target="label_fir_tap_size",
            placement="bottom",
            className="tooltip",
        ),
        # FIR tap size
        dbc.Tooltip(
            [
                html.P("Window function type for designing the anti-aliasing FIR filter"),
                html.P("https://en.wikipedia.org/wiki/Window_function"),
            ],
            target="label_fir_window",
            placement="bottom",
            className="tooltip",
        ),
        # Enable filter reset
        dbc.Tooltip(
            [
                html.P(
                    "If enabled, the memory of the anti-aliasing FIR filter is reseted at the begining of every new CPI"
                )
            ],
            target="label_en_filter_reset",
            placement="bottom",
            className="tooltip",
        ),
        # Correlation size
        dbc.Tooltip(
            [html.P("Number of samples used for the calibration procedure (sample delay and IQ compensation)")],
            target="label_correlation_size",
            placement="bottom",
            className="tooltip",
        ),
        # Standard channel index
        dbc.Tooltip(
            [html.P("The selected channel is used as a reference for the IQ compensation")],
            target="label_std_ch_index",
            placement="bottom",
            className="tooltip",
        ),
        # Enable IQ calibration
        dbc.Tooltip(
            [html.P("Enables to compensate the amplitude and phase differences of the receiver channels")],
            target="label_en_iq_calibration",
            placement="bottom",
            className="tooltip",
        ),
        # Gain lock interval
        dbc.Tooltip(
            [html.P("Minimum number of stable frames before terminating the gain tuning procedure")],
            target="label_gain_lock_interval",
            placement="bottom",
            className="tooltip",
        ),
        # Require track lock intervention
        dbc.Tooltip(
            [
                html.P("When enabled the DAQ firmware waits for manual intervention during the calibraiton procedure"),
                html.P("Should be used only for hardave version 1.0"),
            ],
            target="label_require_track_lock",
            placement="bottom",
            className="tooltip",
        ),
        # Amplitude calibraiton mode
        dbc.Tooltip(
            [
                html.P("Amplitude difference compensation method applied as part of the IQ compensation"),
                html.P(
                    "default: Amplitude differences are estimated by calculating the cross-correlations of the channels"
                ),
                html.P("disabled: Amplitude differences are not compensated"),
                html.P("channel_power: Ampltiude compensation is set in a way to achieve equal channel powers"),
            ],
            target="label_amplitude_calibration_mode",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "When periodic calibration track mode is selected the firmware regularly turn on the noise source for a short burst to\
            check whether the IQ calibration is still valid or not. In case the calibrated state is lost, the firmware automatically\
                initiates a reclaibration procedure"
                )
            ],
            target="label_calibration_track_mode",
            placement="bottom",
            className="tooltip",
        ),
        # Calibration frame interval
        dbc.Tooltip(
            [
                html.P(
                    "Number of data frames between two consecutive calibration burst. Used when periodic calibration mode is selected"
                )
            ],
            target="label_calibration_frame_interval",
            placement="bottom",
            className="tooltip",
        ),
        # Calibration frame burst size
        dbc.Tooltip(
            [html.P("Number of calibration frames generated in the periodic calibration mode")],
            target="label_calibration_frame_burst_size",
            placement="bottom",
            className="tooltip",
        ),
        # Amplitude tolerance
        dbc.Tooltip(
            [html.P("Maximum allowed amplitude difference between the receiver channels")],
            target="label_amplitude_tolerance",
            placement="bottom",
            className="tooltip",
        ),
        # Phase tolerance
        dbc.Tooltip(
            [html.P("Maximum allowed phase difference between the receiver channels")],
            target="label_phase_tolerance",
            placement="bottom",
            className="tooltip",
        ),
        # Maximum sync fails
        dbc.Tooltip(
            [html.P("Maximum allowed consecutive IQ difference check failures before initiating a recalibration")],
            target="label_max_sync_fails",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Apply an optional calibration on any phase differences in cables. Measurements need to be taken with a VNA."
                ),
                html.P(
                    "touchstone: Add 5 Touchstone .s1p format files to the heimdall _calibration folder with filnames cable_ch0.s1p, cable_ch1.s1p and so on. Make sure the file covers the frequency range of interest."
                ),
                html.P("explicit-time-delay: Apply a constant time delay."),
            ],
            target="label_iq_adjust_source",
            placement="top",
            className="tooltip",
        ),
        dbc.Tooltip(
            [html.P("Apply an IQ amplitude adjustment to each channel if required.")],
            target="label_iq_adjust_amplitude",
            placement="top",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P(
                    "Relative time delays to use with the explicit-time-delay mode. NOTE: The time delays are in ns and RELATIVE to the measurement made at CH0. (delta = CH_0 - CH_X)"
                )
            ],
            target="label_iq_adjust_time_delay_ns",
            placement="top",
            className="tooltip",
        ),
    ]
)

station_parameters_tooltips = html.Div(
    [
        dbc.Tooltip(
            [
                html.P("Station ID"),
                html.P("A useful name for your station."),
                html.P("Allows Alpha-Numberic Characters and Hyphens (-)."),
                html.P("All other chacters are replaced by hyphens."),
            ],
            target="station_id_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("DOA Data Format"),
                html.P(
                    "Kraken/Pro & Kerberos App: Choose if you are outputting to the KrakenSDR Android App, KrakenSDR Pro, or Legacy KerberosSDR App"
                ),
                html.P("DF Aggregator: Use for DF Aggregator"),
                html.P("RDF Mapper: Upload directly to an RDF Mapper server"),
            ],
            target="doa_format_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("Location Source"),
                html.P("None: Don't use location data, use this if you're only using the android app."),
                html.P("Static: A fixed location for a stationary receiver."),
                html.P("GPS: Uses gpsd and a USB gps. If this is greyed out, the gpsd python library is not installed"),
            ],
            target="location_src_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("Fixed Heading"),
                html.P("If you're getting location from a GPS, but aren't moving, use this to set a static heading."),
                html.P("GPS Heading information is only reliable when you're moving."),
            ],
            target="fixed_heading_label",
            placement="bottom",
            className="tooltip",
        ),
        dbc.Tooltip(
            [
                html.P("Filter out unreliable heading"),
                html.P("Most consumer-grade GPS modules require it to move to estimate heading."),
                html.P("Typically those measurements are not reliable when speed is too low."),
                html.P("Please set minimum speed and its minumum duration to filter out bogus heading readings."),
                html.P(
                    """Note that u-blox GPS modules might implement these logic internally, but it needs to be configured and activated."""
                    """If you did so, then feel free to disable this filter by setting zero values."""
                ),
            ],
            target="min_speed_heading_fields",
            placement="bottom",
            className="tooltip",
        ),
    ]
)
