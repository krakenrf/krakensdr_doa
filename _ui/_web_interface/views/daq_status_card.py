import dash_html_components as html

# -----------------------------
#       DAQ Status Card
# -----------------------------
layout = html.Div(
    [
        html.H2("DAQ Subsystem Status", id="init_title_s"),
        html.Div(
            [
                html.Div("Update Rate:", id="label_daq_update_rate", className="field-label"),
                html.Div("- ms", id="body_daq_update_rate", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Latency:", id="label_daq_dsp_latency", className="field-label"),
                html.Div("- ms", id="body_daq_dsp_latency", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Frame Index:", id="label_daq_frame_index", className="field-label"),
                html.Div("-", id="body_daq_frame_index", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Frame Type:", id="label_daq_frame_type", className="field-label"),
                html.Div("-", id="body_daq_frame_type", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Frame Sync:", id="label_daq_frame_sync", className="field-label"),
                html.Div("LOSS", id="body_daq_frame_sync", className="field-body", style={"color": "#e74c3c"}),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Power Level:", id="label_daq_power_level", className="field-label"),
                html.Div("-", id="body_daq_power_level", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Connection Status:", id="label_daq_conn_status", className="field-label"),
                html.Div("Disconnected", id="body_daq_conn_status", className="field-body", style={"color": "#e74c3c"}),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Sample Delay Sync:", id="label_daq_delay_sync", className="field-label"),
                html.Div("LOSS", id="body_daq_delay_sync", className="field-body", style={"color": "#e74c3c"}),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("IQ Sync:", id="label_daq_iq_sync", className="field-label"),
                html.Div("LOSS", id="body_daq_iq_sync", className="field-body", style={"color": "#e74c3c"}),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Noise Source State:", id="label_daq_noise_source", className="field-label"),
                html.Div("Disabled", id="body_daq_noise_source", className="field-body", style={"color": "#7ccc63"}),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Center Frequecy [MHz]:", id="label_daq_rf_center_freq", className="field-label"),
                html.Div("- MHz", id="body_daq_rf_center_freq", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Sampling Frequency [MHz]:", id="label_daq_sampling_freq", className="field-label"),
                html.Div("- MHz", id="body_daq_sampling_freq", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("DSP Decimated BW [MHz]:", id="label_dsp_decimated_bw", className="field-label"),
                html.Div("- MHz", id="body_dsp_decimated_bw", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("VFO Range [MHz]:", id="label_vfo_range", className="field-label"),
                html.Div("- MHz", id="body_vfo_range", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("Data Block Length [ms]:", id="label_daq_cpi", className="field-label"),
                html.Div("- ms", id="body_daq_cpi", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("RF Gains [dB]:", id="label_daq_if_gain", className="field-label"),
                html.Div("[,] dB", id="body_daq_if_gain", className="field-body"),
            ],
            className="field",
        ),
        html.Div(
            [
                html.Div("VFO-0 Power [dB]:", id="label_max_amp", className="field-label"),
                html.Div("-", id="body_max_amp", className="field-body"),
            ],
            className="field",
        ),
    ],
    className="card",
)
