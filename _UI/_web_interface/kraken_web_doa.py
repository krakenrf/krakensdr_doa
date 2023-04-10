import numpy as np
import plotly.graph_objects as go
from variables import *

def plot_doa(app, webInterface_inst, doa_fig):

    if webInterface_inst.reset_doa_graph_flag == True:
        doa_fig.data = []
        #Just generate with junk data initially, as the spectrum array may not be ready yet if we have sqeulching active etc.
        if True: #webInterface_inst.doa_thetas is not None:
            # --- Linear plot ---
            if webInterface_inst._doa_fig_type == 'Linear':
                # Plot traces
                doa_fig.add_trace(go.Scattergl(x=x, #webInterface_inst.doa_thetas,
                                  y=y,
                            ))

                doa_fig.update_xaxes(title_text="Incident angle [deg]",
                            color='rgba(255,255,255,1)',
                            title_font_size=20,
                            tickfont_size=figure_font_size,
                            mirror=True,
                            ticks='outside',
                            showline=True)
                doa_fig.update_yaxes(title_text="Amplitude [dB]",
                            color='rgba(255,255,255,1)',
                            title_font_size=20,
                            tickfont_size=figure_font_size,
                            #range=[-5, 5],
                            mirror=True,
                            ticks='outside',
                            showline=True)
# --- Polar plot ---
            elif webInterface_inst._doa_fig_type == 'Polar':

                label = "DOA Angle" #webInterface_inst.doa_labels[i]
                doa_fig.add_trace(go.Scatterpolargl(theta=x, #webInterface_inst.doa_thetas,
                                             r=y, #doa_result,
                                             name=label,
                                             fill= 'toself',
                                             ))

                doa_fig.update_layout(polar = dict(radialaxis_tickfont_size = figure_font_size,
                                           angularaxis = dict(rotation=90,
                                                              tickfont_size = figure_font_size)
                                                             )
                                     )

            # --- Compass  ---
            elif webInterface_inst._doa_fig_type == 'Compass' :
                doa_fig.update_layout(polar = dict(radialaxis_tickfont_size = figure_font_size,
                                        angularaxis = dict(rotation=90+webInterface_inst.compass_offset,
                                                            direction="clockwise",
                                                            tickfont_size = figure_font_size)
                                                          )
                                     )

                label = "DOA Angle"

                doa_fig.add_trace(go.Scatterpolargl(theta=x, #(360-webInterface_inst.doa_thetas+webInterface_inst.compass_offset)%360,
                                                r=y, #doa_result,
                                                name= label,
                                               # line = dict(color = doa_trace_colors[webInterface_inst.doa_labels[i]]),
                                                fill= 'toself'
                                                ))

        webInterface_inst.reset_doa_graph_flag = False
    else:
        update_data = []
        fig_type = []
        doa_max_str = ""
        if webInterface_inst.doa_thetas is not None and webInterface_inst.doa_results[0].size > 0:
            doa_max_str = str(webInterface_inst.doas[0])+"°"

            thetas = webInterface_inst.doa_thetas
            result = webInterface_inst.doa_results[0]

            update_data = dict(x=[thetas], y=[result])

            if webInterface_inst._doa_fig_type == 'Polar' :
                thetas = np.append(webInterface_inst.doa_thetas, webInterface_inst.doa_thetas[0])
                result = np.append(webInterface_inst.doa_results[0], webInterface_inst.doa_results[0][0])
                update_data = dict(theta=[thetas], r=[result])
            elif webInterface_inst._doa_fig_type == 'Compass' :
                thetas = np.append(webInterface_inst.doa_thetas, webInterface_inst.doa_thetas[0])
                result = np.append(webInterface_inst.doa_results[0], webInterface_inst.doa_results[0][0])
                doa_max_str = (360-webInterface_inst.doas[0]+webInterface_inst.compass_offset)%360
                update_data = dict(theta=[(360-thetas+webInterface_inst.compass_offset)%360], r=[result])

            app.push_mods({
                'doa-graph': {'extendData': [update_data, [0], len(thetas)]},
                'body_doa_max': {'children': doa_max_str}
            })