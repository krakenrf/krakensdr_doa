import numpy as np
import plotly.express as px
from variables import *

def plot_spectrum(app, webInterface_inst, spectrum_fig, waterfall_fig):
    # if spectrum_fig == None:
    if webInterface_inst.reset_spectrum_graph_flag:

        # Reset the peak hold each time the spectrum page is loaded
        webInterface_inst.module_signal_processor.resetPeakHold()

        x = webInterface_inst.spectrum[0, :] + webInterface_inst.daq_center_freq * 10 ** 6

        # Plot traces
        for m in range(np.size(webInterface_inst.spectrum, 0) - 1):
            spectrum_fig.data[m]['x'] = x

        # As we use CH1 as the DISPLAY channel (due to lower noise characteristics), ensure we label it as CH1
        # also we can hide the other channels
        if webInterface_inst.module_signal_processor.spectrum_fig_type == 'Single':
            spectrum_fig.update_layout(hovermode="closest")
            spectrum_fig.data[0]['name'] = "Channel 1"
            hide_channels_from = 2 if webInterface_inst.module_signal_processor.en_peak_hold else 1
            if hide_channels_from > 1:
                spectrum_fig.data[1]['name'] = "Peak Hold"
                peak_hold_color_rgb = px.colors.label_rgb(px.colors.hex_to_rgb(spectrum_fig.data[0]['line']['color']))
                peak_hold_color_rgba = f"rgba{peak_hold_color_rgb[3:-1]}, 0.5)"
                spectrum_fig.data[1]['line']['color'] = peak_hold_color_rgba
            for m in range(webInterface_inst.module_receiver.M):
                spectrum_fig.data[m]['visible'] = True if m < hide_channels_from else False
        else:
            spectrum_fig.update_layout(hovermode="x")
            for m in range(webInterface_inst.module_receiver.M):
                spectrum_fig.data[m]['name'] = "Channel {:d}".format(m)
                spectrum_fig.data[m]['visible'] = True
                spectrum_fig.data[m]['line']['color'] = trace_colors[m]

        # Hide non active traces
        for i in range(webInterface_inst.module_signal_processor.max_vfos):
            if i < webInterface_inst.module_signal_processor.active_vfos:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i * 2)]['visible'] = True
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i * 2 + 1)]['visible'] = True
                spectrum_fig.layout.annotations[i]['visible'] = True
                spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos + i][
                    'visible'] = True
            else:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i * 2)]['visible'] = False
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i * 2 + 1)]['visible'] = False
                spectrum_fig.layout.annotations[i]['visible'] = False
                spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos + i][
                    'visible'] = False

        waterfall_fig.data[0]['x'] = x
        waterfall_fig.update_xaxes(tickfont_size=1, range=[np.min(x), np.max(x)], showgrid=False)

        webInterface_inst.reset_spectrum_graph_flag = False
        app.push_mods({
            'spectrum-graph': {'figure': spectrum_fig},
            'waterfall-graph': {'figure': waterfall_fig},
        })

    else:
        # Update entire graph to update VFO-0 text. There is no way to just update annotations in Dash, but updating the entire spectrum is fast
        # enough to do on click
        x = webInterface_inst.spectrum[0, :] + webInterface_inst.daq_center_freq * 10 ** 6
        for i in range(webInterface_inst.module_signal_processor.active_vfos):

            # Find center of VFO display window
            maxIndex = webInterface_inst.spectrum[webInterface_inst.module_receiver.M + (i * 2 + 1), :].argmax()

            reverseSpectrum = webInterface_inst.spectrum[webInterface_inst.module_receiver.M + (i * 2 + 1), ::-1]
            maxIndexReverse = reverseSpectrum.argmax()
            maxIndexReverse = len(reverseSpectrum) - maxIndexReverse - 1
            maxIndexCenter = (maxIndex + maxIndexReverse) // 2

            # Update VFO Text Bearing
            doa = webInterface_inst.max_doas_list[i]
            if webInterface_inst._doa_fig_type == "Compass":
                doa = (360 - doa + webInterface_inst.compass_offset) % 360
            spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos + i]['text'] = \
                str(doa) + "°"

            maxX = x[maxIndexCenter]
            spectrum_fig.layout.annotations[i]['x'] = maxX
            spectrum_fig.layout.annotations[webInterface_inst.module_signal_processor.max_vfos + i]['x'] = maxX

            # Update selected VFO border
            width = 0
            if webInterface_inst.selected_vfo == i:
                width = 3

            # Update squelch/active colors
            if webInterface_inst.squelch_update[i]:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i * 2)]['line'] = dict(color='green',
                                                                                                width=width)
            else:
                spectrum_fig.data[webInterface_inst.module_receiver.M + (i * 2)]['line'] = dict(color='red',
                                                                                                width=width)

        # Make y values too so that the graph does not rapidly flash with random data on every click
        for m in range(1, np.size(webInterface_inst.spectrum, 0)):
            spectrum_fig.data[m - 1]['x'] = x
            spectrum_fig.data[m - 1]['y'] = webInterface_inst.spectrum[m, :]

        z = webInterface_inst.spectrum[1, :]
        app.push_mods({
            'spectrum-graph': {'figure': spectrum_fig},
            'waterfall-graph': {'extendData': [dict(z=[[z]]), [0], 50]},  # Add up spectrum for waterfall
        })