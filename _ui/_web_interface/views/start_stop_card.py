import dash_html_components as html

# -----------------------------
#   Start/Stop Configuration Card
# -----------------------------
layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [html.Button("Start Processing", id="btn-start_proc", className="btn_start", n_clicks=0)],
                    className="ctr_toolbar_item",
                ),
                html.Div(
                    [html.Button("Stop Processing", id="btn-stop_proc", className="btn_stop", n_clicks=0)],
                    className="ctr_toolbar_item",
                ),
            ],
            className="ctr_toolbar",
        ),
    ]
)
