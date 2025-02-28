import math
import operator
import shutil

import numpy as np
from scipy.signal import (
    butter,
    firwin,
    lfilter,
    resample_poly,
)

DEFAULT_NUM_OF_FREQ = 1024
DEFAULT_FILTER_ORDER = 5
DEFAULT_FILTER_WINDOW = "hamming"
DEFAULT_NUM_TAPS = 256

DISK_SPACE_HEADROOM = 0.1


def decimate_custom_fir(x, q, b, a):
    """
    Downsample the signal after applying given FIR filter.

    Parameters
    ----------
    x : array_like
        The signal to be downsampled, as an N-dimensional array.
    q : int
        The downsampling factor.
    b: array_like
        Numerator of the transfer function.
    a: array_like
        Denominator of the transfer function.
    """

    x = np.asarray(x)
    q = operator.index(q)

    sl = [slice(None)] * x.ndim

    b = b / a
    y = resample_poly(x, 1, q, axis=-1, window=b)

    return y[tuple(sl)]


def audible(signal):
    """
    Scale so it's audible
    """
    signal = np.int16(signal / np.max(np.abs(signal)) * 32767)
    return signal


def butter_lowpass(highcut, fs, order=DEFAULT_FILTER_ORDER):
    return butter(order, highcut, fs=fs, btype="low")


def butter_lowpass_filter(signal, highcut, fs, order=DEFAULT_FILTER_ORDER):
    b, a = butter_lowpass(highcut, fs, order=order)
    rx = lfilter(b, a, signal)
    return rx


def firwin_lowpass(highcut, fs, ntaps=DEFAULT_NUM_TAPS, window=DEFAULT_FILTER_WINDOW):
    taps = firwin(ntaps, highcut, fs=fs, window=window, scale=False)
    return taps


def firwin_lowpass_filter(data, highcut, fs, ntaps=DEFAULT_NUM_TAPS, window=DEFAULT_FILTER_WINDOW):
    taps = firwin_lowpass(highcut, fs, ntaps, window)
    y = lfilter(taps, 1, data)
    return y


def audio_agc(samples, sample_freq, t_max):
    """
    Audio Adaptive Gain Control.
    Primitive version of AGC with slicing samples by time and rescaling each time-slice
    """
    t_slice = int(t_max * sample_freq)
    demod_channel = samples

    new_demod_channel = None
    demod_channel_chunks = np.array_split(demod_channel, math.ceil(demod_channel.size / t_slice))
    for chunk in demod_channel_chunks:
        aud_chunk = audible(chunk)
        if new_demod_channel is not None:
            new_demod_channel = np.concatenate((new_demod_channel, aud_chunk))
        else:
            new_demod_channel = aud_chunk

    return audible(new_demod_channel)


def fm_demod(samples, sample_freq, freq_width):
    demod_channel = samples

    demod_channel = firwin_lowpass_filter(demod_channel, int(freq_width / 2), sample_freq)

    baseband = demod_channel
    demod_channel = np.angle(baseband[1::1] * np.conjugate(baseband[0:-1:1]))
    demod_channel = (demod_channel * sample_freq) / (2 * np.pi)

    # Adjust amplitude of signal in case noise
    demod_channel = audio_agc(demod_channel, sample_freq, t_max=0.2)

    return demod_channel


def write_wav(f, sample_freq, x):
    """
    NumPy array to WAV
    """
    from scipy.io.wavfile import write

    write(f, sample_freq, x.astype(np.int16))


def can_store_file(path: str) -> bool:
    total, _, free = shutil.disk_usage(path)
    return True if (free / total) >= DISK_SPACE_HEADROOM else False
