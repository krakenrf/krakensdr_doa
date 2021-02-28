import json
import os

if os.path.exists('settings.json'):
    with open('settings.json', 'r') as myfile:
        settings=json.loads(myfile.read())
else:
    settings = {}
    with open('settings.json', 'w') as outfile:
        json.dump(settings, outfile)

# Receiver Configuration
center_freq = settings.get("center_freq", 100.0)
samp_index = settings.get("samp_index", 2)
uniform_gain = settings.get("uniform_gain", 0)
gain_index = settings.get("gain_index", 0)
gain_index_2 = settings.get("gain_index_2", 0)
gain_index_3 = settings.get("gain_index_3", 0)
gain_index_4 = settings.get("gain_index_4", 0)
dc_comp = settings.get("dc_comp", 0)
filt_bw = settings.get("filt_bw", 150.0)
fir_size = settings.get("fir_size", 0)
decimation = settings.get("decimation", 1)
data_interface = settings.get("data_interface", "eth")
logging_level = settings.get("logging_level", 0)
default_ip = settings.get("default_ip", "0.0.0.0")
user_interface = settings.get("user_interface", "gtgui")

# Sync
en_sync = settings.get("en_sync", 0)
en_noise = settings.get("en_noise", 0)

# DOA Estimation
ant_arrangement_index = settings.get("ant_arrangement_index", "0")
ant_spacing = settings.get("ant_spacing", "0.5")
en_doa = settings.get("en_doa", None)
en_bartlett = settings.get("en_bartlett", None)
en_capon = settings.get("en_capon", None)
en_MEM = settings.get("en_MEM", None)
en_MUSIC = settings.get("en_MUSIC", None)
en_fbavg = settings.get("en_fbavg", None)


def write():
    data = {}

    # Configuration
    data["center_freq"] = center_freq
    data["samp_index"] = samp_index
    data["uniform_gain"] = uniform_gain
    data["gain_index"] = gain_index
    data["gain_index_2"] = gain_index_2
    data["gain_index_3"] = gain_index_3
    data["gain_index_4"] = gain_index_4
    data["dc_comp"] = dc_comp
    data["filt_bw"] = filt_bw
    data["fir_size"] = fir_size
    data["decimation"] = decimation

    # Sync
    data["en_sync"] = en_sync
    data["en_noise"] = en_noise

    # DOA Estimation
    data["ant_arrangement_index"] = ant_arrangement_index
    data["ant_spacing"] = ant_spacing
    data["en_doa"] = en_doa
    data["en_bartlett"] = en_bartlett
    data["en_capon"] = en_capon
    data["en_MEM"] = en_MEM
    data["en_MUSIC"] = en_MUSIC
    data["en_fbavg"] = en_fbavg

    with open('settings.json', 'w') as outfile:
        json.dump(data, outfile)
