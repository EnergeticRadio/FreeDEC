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

import os
import time
import argparse

import requests
import soundfile as sf
import queue
import jack

parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('server', help='Server IP')
parser.add_argument('callsign', help='Station callsign')
parser.add_argument(
    '-p', '--port', type=int, default=80,
    help='Server port (default: %(default)s)')
parser.add_argument(
    '-c', '--channels', type=int, default=1,
    help='Number of channels (stereo pairs) (default: %(default)s)')

args = parser.parse_args()

buffer_size = 20
server_url = f'http://{args.server}:{args.port}'
callsign = args.callsign
channels = args.channels

q = queue.Queue(maxsize=buffer_size)


def check_incoming(callsign):
    r = requests.get(f'{server_url}/api/get_alert?callsign={callsign}')

    if not r.text == 'null':
        time.sleep(1)
        dl = requests.get(f'{server_url}/audio/{r.json()}')

        with open('alert.wav', 'wb') as f:
            f.write(dl.content)

        return True

    else:
        return False


def set_status(status):
    params = {
        'group': 'relay',
        'name': callsign,
        'status': status
    }

    try:
        requests.get(f'{server_url}/api/set_status', params=params)

    except requests.exceptions.ConnectionError:
        pass


def process(_):
    try:
        data = q.get_nowait()
    except queue.Empty:
        data = None

    if data is None:
        for i, o in zip(client.inports, client.outports):
            o.get_buffer()[:] = i.get_buffer()

    else:
        for port in client.outports:
            port.get_buffer()[:] = data.T


try:
    check_incoming(callsign)
except requests.exceptions.ConnectionError:
    print('Error connecting to server')
    exit(1)

try:
    client = jack.Client('FreeDEC')
except jack.JackOpenError:
    print('Failed to connect to jack')
    exit(1)

block_size = client.blocksize
samplerate = client.samplerate
timeout = block_size * buffer_size / samplerate
client.set_process_callback(process)

for channel in range(channels):
    for l_r in ['L', 'R']:
        client.inports.register(f'input_{channel}{l_r}')
        client.outports.register(f'output_{channel}{l_r}')

with client:
    print(f'Relay UP: {callsign}')

    try:
        while True:
            try:
                if check_incoming(callsign):
                    print('Relaying alert')
                    set_status('active')

                    with sf.SoundFile('alert.wav') as f:
                        block_generator = f.blocks(blocksize=block_size, dtype='float32',
                                                   always_2d=True, fill_value=0)

                        for _, data in zip(range(buffer_size), block_generator):
                            q.put_nowait(data)

                        for data in block_generator:
                            q.put(data, timeout=timeout)

                        q.put(None, timeout=timeout)

                    requests.get(f'{server_url}/api/clear_alert?callsign={callsign}')
                    os.remove('alert.wav')

                    print('EOM')

                else:
                    set_status('idle')

            except requests.exceptions.ConnectionError:
                set_status('fail')

            except RuntimeError:
                print('Error reading alert!, retrying...')
                set_status('fail')

            time.sleep(1)

    except KeyboardInterrupt:
        print('Shutdown signal received')
