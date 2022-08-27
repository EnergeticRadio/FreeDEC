#
#    FreeDEC - A fully capable software based EAS encoder/decoder
#    Copyright (C) 2022  EnergeticRadio
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import numpy as np
import math
import wave

from pydub import AudioSegment, effects
from EASGen import EASGen


def _wav_np_read(filename):
    """Read wav file into a numpy array"""

    with wave.open(filename, 'rb') as f:
        assert f.getnchannels() == 1

        buffer = f.readframes(f.getnframes())
        inter = np.frombuffer(buffer, dtype=f'int{f.getsampwidth() * 8}')

        return inter, f.getframerate(), f.getsampwidth()


def _extract_peak_frequency(data, sampling_rate):
    """Find the prominent frequency in array"""

    fft_data = np.fft.fft(data)
    freqs = np.fft.fftfreq(len(data))

    peak_coefficient = np.argmax(np.abs(fft_data))
    peak_freq = freqs[peak_coefficient]

    return abs(peak_freq * sampling_rate)


def extract_message(in_file):
    """Find header, attention tone, and eom, extract only the audio message. Return Pydub audio segment"""

    data, sample_rate, sample_width = _wav_np_read(in_file)
    data_len = len(data)

    block_size = round(sample_rate / 8)

    attn_freqs = [853, 960, 1050]
    search_freqs = attn_freqs + [2083, 1563]

    matches = []
    markers = []

    mrk_started = False
    found_attn = 0
    curr_marker = None

    for i in range(math.ceil((data_len / block_size))):
        start = block_size * i
        end = min(start + block_size, data_len)

        curr_block = data[start:end]

        if start >= data_len - sample_rate*3:
            window_width = 2
        else:
            window_width = 3

        if not len(curr_block) == 0:
            found_freq = round(_extract_peak_frequency(curr_block, sample_rate))

            found_match = False

            for freq in search_freqs:
                if math.isclose(found_freq, freq, abs_tol=10):
                    found_match = True

            if not found_attn >= 16:
                for freq in attn_freqs:
                    if math.isclose(found_freq, freq, abs_tol=10):
                        found_attn += 1

            matches.append(found_match)
            matches = matches[window_width*-2:]

            if found_match:
                curr_marker = start

            if matches.count(True) >= window_width and not mrk_started:
                mrk_started = True

            elif matches.count(True) < window_width and mrk_started:
                markers.append(start)
                mrk_started = False

    markers.append(curr_marker)
    print(len(markers))

    if found_attn >= 16 and len(markers) >= 3:
        start = markers[1]
        end = markers[2]

    else:
        start = markers[0]
        end = markers[1]

    end -= block_size*5

    data = data[start:end]

    return effects.normalize(AudioSegment(
        data=data.tobytes(),
        sample_width=sample_width,
        frame_rate=sample_rate,
        channels=1
    ))


def encode_eas(header, output, msg=AudioSegment.empty(), attention_tone=True):
    """Generate a new SAME header, include audio message if provided"""

    alert = EASGen.genEAS(header=header, attentionTone=attention_tone, audio=msg,
                          endOfMessage=True, sampleRate=48000, mode='DIGITAL')

    EASGen.export_wav(output, alert, sample_rate=48000)
