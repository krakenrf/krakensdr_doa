import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from variables import figure_font_size, trace_colors, x, y


def init_spectrum_fig(web_interface, fig_layout, trace_colors):
    spectrum_fig = go.Figure(layout=fig_layout)

    scatter_plot = go.Scattergl(
        x=x,
        y=y,
        name="Channel {:d}".format(1),
        line=dict(color=trace_colors[1], width=1),
    )

    for m in range(0, web_interface.module_receiver.M):  # +1 for the auto decimation window selection
        scatter = scatter_plot
        scatter["name"] = "Channel {:d}".format(m)
        scatter["line"] = dict(color=trace_colors[m], width=1)
        spectrum_fig.add_trace(scatter)

    # trace_colors[web_interface.module_receiver.M + 2], width = 0)
    VFO_color = dict(color="green", width=0)
    # trace_colors[web_interface.module_receiver.M + 1], width = 0)
    VFO_squelch_color = dict(color="yellow", width=0)
    VFO_scatter = go.Scattergl(
        x=x,
        y=y,
        name="VFO" + str(0),
        line=VFO_color,
        # dict(color = trace_colors[m], width = 0),
        opacity=0.6,
        fill="toself",
        visible=False,
    )
    for i in range(web_interface.module_signal_processor.max_vfos):
        scatter = VFO_scatter
        scatter["name"] = "VFO" + str(i)
        scatter["line"] = VFO_color
        spectrum_fig.add_trace(scatter)

        scatter["name"] = "VFO" + str(i) + " Squelch"
        scatter["line"] = VFO_squelch_color
        spectrum_fig.add_trace(scatter)

        spectrum_fig.add_annotation(
            x=415640000,
            y=-5,
            text="VFO-" + str(i),
            font=dict(size=12, family="Courier New"),
            showarrow=False,
            yshift=10,
            visible=False,
        )

    # Now add the angle display text
    # web_interface.module_signal_processor.active_vfos):
    for _ in range(web_interface.module_signal_processor.max_vfos):
        spectrum_fig.add_annotation(
            x=415640000,
            y=-5,
            text="Angle",
            font=dict(size=12, family="Courier New"),
            showarrow=False,
            yshift=-5,
            visible=False,
        )

    spectrum_fig.update_xaxes(
        color="rgba(255,255,255,1)",
        title_font_size=20,
        tickfont_size=15,  # figure_font_size,
        # range=[np.min(x), np.max(x)],
        # rangemode='normal',
        mirror=True,
        ticks="outside",
        showline=True,
        # fixedrange=True
    )
    spectrum_fig.update_yaxes(
        title_text="Amplitude [dB]",
        color="rgba(255,255,255,1)",
        title_font_size=20,
        tickfont_size=figure_font_size,
        range=[-90, 0],
        mirror=True,
        ticks="outside",
        showline=True,
        # fixedrange=True
    )

    spectrum_fig.update_layout(margin=go.layout.Margin(b=5, t=0), hoverdistance=10000)
    spectrum_fig.update(layout_showlegend=False)

    return spectrum_fig


def plot_spectrum(app, web_interface, spectrum_fig, waterfall_fig):
    # if spectrum_fig == None:
    if web_interface.reset_spectrum_graph_flag:
        # Reset the peak hold each time the spectrum page is loaded
        web_interface.module_signal_processor.resetPeakHold()

        x = web_interface.spectrum[0, :] + web_interface.daq_center_freq * 10**6

        # Plot traces
        for m in range(np.size(web_interface.spectrum, 0) - 1):
            spectrum_fig.data[m]["x"] = x

        # As we use CH1 as the DISPLAY channel (due to lower noise characteristics), ensure we label it as CH1
        # also we can hide the other channels
        if web_interface.module_signal_processor.spectrum_fig_type == "Single":
            spectrum_fig.update_layout(hovermode="closest")
            spectrum_fig.data[0]["name"] = "Channel 1"
            hide_channels_from = 2 if web_interface.module_signal_processor.en_peak_hold else 1
            if hide_channels_from > 1:
                spectrum_fig.data[1]["name"] = "Peak Hold"
                peak_hold_color_rgb = px.colors.label_rgb(px.colors.hex_to_rgb(spectrum_fig.data[0]["line"]["color"]))
                peak_hold_color_rgba = f"rgba{peak_hold_color_rgb[3:-1]}, 0.5)"
                spectrum_fig.data[1]["line"]["color"] = peak_hold_color_rgba
            for m in range(web_interface.module_receiver.M):
                spectrum_fig.data[m]["visible"] = True if m < hide_channels_from else False
        else:
            spectrum_fig.update_layout(hovermode="x")
            for m in range(web_interface.module_receiver.M):
                spectrum_fig.data[m]["name"] = "Channel {:d}".format(m)
                spectrum_fig.data[m]["visible"] = True
                spectrum_fig.data[m]["line"]["color"] = trace_colors[m]

        # Hide non active traces
        for i in range(web_interface.module_signal_processor.max_vfos):
            if i < web_interface.module_signal_processor.active_vfos:
                spectrum_fig.data[web_interface.module_receiver.M + (i * 2)]["visible"] = True
                spectrum_fig.data[web_interface.module_receiver.M + (i * 2 + 1)]["visible"] = True
                spectrum_fig.layout.annotations[i]["visible"] = True
                spectrum_fig.layout.annotations[web_interface.module_signal_processor.max_vfos + i]["visible"] = True
            else:
                spectrum_fig.data[web_interface.module_receiver.M + (i * 2)]["visible"] = False
                spectrum_fig.data[web_interface.module_receiver.M + (i * 2 + 1)]["visible"] = False
                spectrum_fig.layout.annotations[i]["visible"] = False
                spectrum_fig.layout.annotations[web_interface.module_signal_processor.max_vfos + i]["visible"] = False

        waterfall_fig.data[0]["x"] = x
        waterfall_fig.update_xaxes(tickfont_size=1, range=[np.min(x), np.max(x)], showgrid=False)

        web_interface.reset_spectrum_graph_flag = False
        app.push_mods(
            {
                "spectrum-graph": {"figure": spectrum_fig},
                "waterfall-graph": {"figure": waterfall_fig},
            }
        )

    else:
        # Update entire graph to update VFO-0 text. There is no way to just update annotations in Dash, but updating the entire spectrum is fast
        # enough to do on click
        x = web_interface.spectrum[0, :] + web_interface.daq_center_freq * 10**6
        for i in range(web_interface.module_signal_processor.active_vfos):
            # Find center of VFO display window
            maxIndex = web_interface.spectrum[web_interface.module_receiver.M + (i * 2 + 1), :].argmax()

            reverseSpectrum = web_interface.spectrum[web_interface.module_receiver.M + (i * 2 + 1), ::-1]
            maxIndexReverse = reverseSpectrum.argmax()
            maxIndexReverse = len(reverseSpectrum) - maxIndexReverse - 1
            maxIndexCenter = (maxIndex + maxIndexReverse) // 2

            # Update VFO Text Bearing
            doa = web_interface.max_doas_list[i]
            if web_interface._doa_fig_type == "Compass":
                doa = (360 - doa + web_interface.compass_offset) % 360
            spectrum_fig.layout.annotations[web_interface.module_signal_processor.max_vfos + i]["text"] = str(doa) + "°"

            maxX = x[maxIndexCenter]
            spectrum_fig.layout.annotations[i]["x"] = maxX
            spectrum_fig.layout.annotations[web_interface.module_signal_processor.max_vfos + i]["x"] = maxX

            # Update selected VFO border
            width = 0
            if web_interface.selected_vfo == i:
                width = 3

            # Update squelch/active colors
            if web_interface.squelch_update[i]:
                spectrum_fig.data[web_interface.module_receiver.M + (i * 2)]["line"] = dict(color="green", width=width)
            else:
                spectrum_fig.data[web_interface.module_receiver.M + (i * 2)]["line"] = dict(color="red", width=width)

        # Make y values too so that the graph does not rapidly flash with
        # random data on every click
        for m in range(1, np.size(web_interface.spectrum, 0)):
            spectrum_fig.data[m - 1]["x"] = x
            spectrum_fig.data[m - 1]["y"] = web_interface.spectrum[m, :]

        z = web_interface.spectrum[1, :]
        app.push_mods(
            {
                "spectrum-graph": {"figure": spectrum_fig},
                # Add up spectrum for waterfall
                "waterfall-graph": {"extendData": [dict(z=[[z]]), [0], 50]},
            }
        )
