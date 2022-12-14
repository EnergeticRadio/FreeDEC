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

import subprocess
import threading
import time

import toml
import requests

import _same as same

print('FreeDEC Beta')
config = toml.load('config/config.toml')


class Monitor:
    def __init__(self, name, device):
        self.name = name
        self.device = device

        self.monitor = None
        self.recorder = None

        self.awaiting_eom = False
        self.last_eas = None

        self._start_monitor()

    def set_status(self, status):
        host = config["server"]["host"]
        port = config["server"]["port"]
        params = {
            'group': 'source',
            'name': self.name,
            'status': status
        }

        try:
            requests.put(f'http://{host}:{port}/api/status', params=params)

        except requests.exceptions.ConnectionError:
            pass

    def _start_monitor(self):
        """Start monitor process"""

        self.monitor = subprocess.Popen(['monitors/multimon-pulse.sh', self.device], stdout=subprocess.PIPE)
        self.set_status('idle')

    @property
    def _is_alive(self):
        """Check if decoder process is still running"""

        return self.monitor.poll() is None

    def _record_pulse(self):
        """Records from a specific pulseaudio device"""

        self.recorder = subprocess.Popen([
            'pacat', f'{config["audio_base_dir"]}/{self.last_eas["filename"]}.wav', '-r', f'--device={self.device}',
            '--file-format=wav', '--rate=48000', '--channels=1', '--latency-msec=100'
        ])

    def handle_alert(self):
        """Read and decode updates from decoder process"""

        raw_same = self.monitor.stdout.readline().decode('utf-8').strip('EAS: ').strip()
        msg_type = same.message_type(raw_same)

        if not self._is_alive:
            # Restart monitor if killed
            print(f'Monitor {self.name} died, restarting...')

            self._start_monitor()

        elif msg_type == 'eas':
            # Decode and start recording

            self.last_eas = same.decode(raw_same)

            if not same.is_dupe(self.last_eas):
                if not self.awaiting_eom:
                    print(f'Receiving EAS from: {self.last_eas["from_callsign"]} | '
                          f'{self.last_eas["event"]} for '
                          f'{self.last_eas["areas_str"]}')

                    self._record_pulse()
                    self.awaiting_eom = True
                    self.set_status('active')

                else:
                    self.awaiting_eom = False

            else:
                print(f'Received duplicate message from: {self.last_eas["from_callsign"]}')
                print('Monitoring')

        elif msg_type == 'eom' and self.awaiting_eom:
            # Stop recording and process alert audio

            print('EOM')

            self.recorder.terminate()
            self.recorder.wait()

            same.re_encode(self.last_eas)

            self.awaiting_eom = False
            self.set_status('idle')

            print('Monitoring')

        elif msg_type == 'invalid':
            print(f'Received invalid SAME: {raw_same}')


def run_monitor(name, device):
    m = Monitor(name, device)

    while True:
        m.handle_alert()


def main():
    monitors = {}

    for source in config['sources']:
        monitors[source['name']] = threading.Thread(target=run_monitor, args=(source['name'], source['device'], ),
                                                    daemon=True)
        monitors[source['name']].start()

    print(f"""Active audio sources: {', '.join([f"{s['name']} ({s['type']})" for s in config['sources']])}""")
    print('All systems UP')
    print('Monitoring')

    while True:
        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Shutdown signal received')
