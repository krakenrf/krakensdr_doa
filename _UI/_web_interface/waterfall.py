import plotly.graph_objects as go
from variables import *


def init_waterfall(webInterface_inst):
    waterfall_fig = go.Figure(layout=fig_layout)
    waterfall_init_x = list(
        range(0, webInterface_inst.module_signal_processor.spectrum_plot_size - 1)
    )  # [1] * webInterface_inst.module_signal_processor.spectrum_window_size
    waterfall_init = [[-80] * webInterface_inst.module_signal_processor.spectrum_plot_size] * 50

    waterfall_fig.add_trace(
        go.Heatmapgl(
            x=waterfall_init_x,
            z=waterfall_init,
            zsmooth=False,
            showscale=False,
            # hoverinfo='skip',
            colorscale=[
                [0.0, "#000020"],  # CREDIT: Youssef SDR# color scale
                [0.0714, "#000030"],
                [0.1428, "#000050"],
                [0.2142, "#000091"],
                [0.2856, "#1E90FF"],
                [0.357, "#FFFFFF"],
                [0.4284, "#FFFF00"],
                [0.4998, "#FE6D16"],
                [0.5712, "#FE6D16"],
                [0.6426, "#FF0000"],
                [0.714, "#FF0000"],
                [0.7854, "#C60000"],
                [0.8568, "#9F0000"],
                [0.9282, "#750000"],
                [1.0, "#4A0000"],
            ],
        )
    )

    waterfall_fig.update_xaxes(tickfont_size=1)
    waterfall_fig.update_yaxes(tickfont_size=1, showgrid=False)
    waterfall_fig.update_layout(
        margin=go.layout.Margin(t=5), hoverdistance=10000
    )  # Set hoverdistance to 1000 seems to be a hack that fixed clickData events not always firing

    return waterfall_fig
