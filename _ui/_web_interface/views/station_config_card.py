import dash_core_components as dcc
import dash_html_components as html

# isort: off
from maindash import web_interface

# isort: on
from variables import option


def get_station_config_card_layout():
    en_fixed_heading = [1] if web_interface.module_signal_processor.fixed_heading else []
    # --------------------------------
    # Misc station config parameters
    # --------------------------------
    return html.Div(
        [
            html.H2("Station Information", id="station_conf_title"),
            html.Div(
                [
                    html.Div("Station ID:", id="station_id_label", className="field-label"),
                    dcc.Input(
                        id="station_id_input",
                        value=web_interface.module_signal_processor.station_id,
                        pattern="[A-Za-z0-9\\-]*",
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                className="field",
                display="none",
            ),
            html.Div(
                [
                    html.Div("DOA Data Format:", id="doa_format_label", className="field-label"),
                    dcc.Dropdown(
                        id="doa_format_type",
                        options=[
                            {"label": "Kraken App", "value": "Kraken App"},
                            {"label": "Kraken Pro Local", "value": "Kraken Pro Local"},
                            {"label": "Kraken Pro Remote", "value": "Kraken Pro Remote"},
                            {"label": "Kerberos App", "value": "Kerberos App"},
                            {"label": "DF Aggregator", "value": "DF Aggregator"},
                            {"label": "RDF Mapper", "value": "RDF Mapper"},
                            {"label": "Full POST", "value": "Full POST"},
                        ],
                        value=web_interface.module_signal_processor.DOA_data_format,
                        style={"display": "inline-block"},
                        className="field-body",
                    ),
                ],
                className="field",
                display="none",
            ),
            html.Div(
                [
                    html.Div("RDF Mapper / Generic Server URL:", className="field-label"),
                    dcc.Input(
                        id="rdf_mapper_server_address",
                        value=web_interface.module_signal_processor.RDF_mapper_server,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                id="rdf_mapper_server_address_field",
                className="field",
                display="none",
            ),
            html.Div(
                [
                    html.Div("Kraken Pro Key:", className="field-label"),
                    dcc.Input(
                        id="krakenpro_key",
                        value=web_interface.module_signal_processor.krakenpro_key,
                        type="text",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                id="krakenpro_field",
                className="field",
                display="none",
            ),
            html.Div(
                [
                    html.Div("Location Source:", id="location_src_label", className="field-label"),
                    dcc.Dropdown(
                        id="loc_src_dropdown",
                        options=[
                            {"label": "None", "value": "None"},
                            {"label": "Static", "value": "Static"},
                            {
                                "label": "GPS",
                                "value": "gpsd",
                                "disabled": not web_interface.module_signal_processor.hasgps,
                            },
                        ],
                        value=web_interface.location_source,
                        style={"display": "inline-block"},
                        className="field-body",
                        disabled=True,
                    ),
                ],
                className="field",
            ),
            html.Div(
                [
                    html.Div("Fixed Heading", id="fixed_heading_label", className="field-label"),
                    dcc.Checklist(
                        options=option, id="fixed_heading_check", className="field-body", value=en_fixed_heading
                    ),
                    # html.Div("Fixed Heading:", className="field-label"),
                    # daq.BooleanSwitch(id="fixed_heading_check",
                    #                   on=web_interface.module_signal_processor.fixed_heading,
                    #                   label="Use Fixed Heading",
                    #                   labelPosition="right"),
                ],
                className="field",
                id="fixed_heading_div",
                disabled=True,
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Latitude:", className="field-label"),
                            dcc.Input(
                                id="latitude_input",
                                value=web_interface.module_signal_processor.latitude,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                            ),
                        ],
                        id="latitude_field",
                        className="field",
                        disabled=True,
                    ),
                    html.Div(
                        [
                            html.Div("Longitude:", className="field-label"),
                            dcc.Input(
                                id="longitude_input",
                                value=web_interface.module_signal_processor.longitude,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                            ),
                        ],
                        id="logitude_field",
                        className="field",
                        disabled=True,
                    ),
                ],
                id="location_fields",
            ),
            html.Div(
                [
                    html.Div("Heading:", className="field-label"),
                    dcc.Input(
                        id="heading_input",
                        value=web_interface.module_signal_processor.heading,
                        type="number",
                        className="field-body-textbox",
                        debounce=True,
                    ),
                ],
                id="heading_field",
                className="field",
                disabled=True,
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("GPS:", className="field-label"),
                            html.Div("-", id="gps_status", className="field-body"),
                        ],
                        id="gps_status_field",
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Latitude:", id="label_gps_latitude", className="field-label"),
                            html.Div("-", id="body_gps_latitude", className="field-body"),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Longitude:", id="label_gps_longitude", className="field-label"),
                            html.Div("-", id="body_gps_longitude", className="field-body"),
                        ],
                        className="field",
                    ),
                    html.Div(
                        [
                            html.Div("Heading:", id="label_gps_heading", className="field-label"),
                            html.Div("-", id="body_gps_heading", className="field-body"),
                        ],
                        className="field",
                    ),
                ],
                id="gps_status_info",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Min speed for heading [m/s]:", className="field-label"),
                            dcc.Input(
                                id="min_speed_input",
                                value=web_interface.module_signal_processor.gps_min_speed_for_valid_heading,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                                min=0,
                            ),
                        ],
                        id="min_speed_field",
                        className="field",
                        disabled=True,
                    ),
                    html.Div(
                        [
                            html.Div("Min speed duration for heading [s]", className="field-label"),
                            dcc.Input(
                                id="min_speed_duration_input",
                                value=web_interface.module_signal_processor.gps_min_duration_for_valid_heading,
                                type="number",
                                className="field-body-textbox",
                                debounce=True,
                                min=0,
                            ),
                        ],
                        id="min_speed_duration_field",
                        className="field",
                        disabled=True,
                    ),
                ],
                id="min_speed_heading_fields",
            ),
        ],
        className="card",
    )
