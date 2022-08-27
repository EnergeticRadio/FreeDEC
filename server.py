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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import toml


class Status:
    def __init__(self):
        self.status = {}

    def set(self, name, status_str, status_type):
        # type idle (green), active (green, flashing), fail (red)

        self.status[name] = {
            'status_str': status_str,
            'status_color': status_type,
            'timestamp': round(time.time())
        }

    def get(self):
        for key in self.status:
            if round(time.time()) - self.status[key]['timestamp'] > 5:
                self.status[key]['status_str'] = 'fail'

        return self.status


config = toml.load('config/config.toml')
audio_base_dir = config['audio_base_dir']

s = Status()
app = FastAPI()
test = False

app.mount('/audio', StaticFiles(directory=audio_base_dir), name='audio')


@app.get('/api/get_alert')
async def read_item(callsign):
    for file in os.listdir(audio_base_dir):
        if f'{callsign}-LIVE' in file:
            return file

    return None


@app.get('/api/clear_alert')
async def read_item(callsign):
    for file in os.listdir(audio_base_dir):
        if f'{callsign}-LIVE' in file:
            os.remove(f'{audio_base_dir}/{file}')

            return 'ok'

    return None


@app.get('/api/set_status')
async def set_status(name, status_str, status_type):
    s.set(name, status_str, status_type)


if __name__ == '__main__':
    uvicorn.run(
        'server:app',
        port=config['server']['port'],
        host=config['server']['host'],
        log_level='info')
