import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import web_interface

# isort: on
from variables import option


def get_recording_config_card_layout():
    en_data_record = [1] if web_interface.module_signal_processor.en_data_record else []
    return html.Div(
        [
            html.H2("Local Data Recording", id="data_recording_title"),
            html.Div(
                [
                    html.Div("Filename:", id="filename_label", className="field-label"),
                    dcc.Input(
                        id="filename_input",
                        value=web_interface.module_signal_processor.data_recording_file_name,
                        # web_interface.module_signal_processor.station_id,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Data Format:", id="data_format_label", className="field-label"),
                    dcc.Dropdown(
                        id="data_format_type",
                        options=[
                            {"label": "Kraken App", "value": "Kraken App"},
                        ],
                        value="Kraken App",  # web_interface.module_signal_processor.DOA_data_format,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Write Interval (s):", id="write_interval_label", className="field-label"),
                    dcc.Input(
                        id="write_interval_input",
                        value=web_interface.module_signal_processor.write_interval,
                        # web_interface.module_signal_processor.station_id,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Enable Local Data Recording:", id="label_en_data_record", className="field-label"),
                    dcc.Checklist(options=option, id="en_data_record", className="field-body", value=en_data_record),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("File Size (MB):", id="label_file_size", className="field-label"),
                    html.Div("- MB", id="body_file_size", className="field-body"),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Button("Download File", id="btn_download_file", className="btn"),
                    dcc.Download(id="download_recorded_file"),
                ],
                className="field",
            ),
        ],
        className="card",
    )
