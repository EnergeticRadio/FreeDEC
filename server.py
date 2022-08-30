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
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import toml

import _same as same


class Status:
    def __init__(self):
        self.status = {
            'source': {},
            'relay': {}
        }
        self.status_styles = {
            'check': ['idle', 'active', 'fail', 'not-started'],
            'idle': 'is-success',
            'active': 'is-warning blink',
            'fail': 'is-danger',
            'not-started': ''
        }

        sources, relays = same.get_modules()

        for source in sources:
            self.set('source', source, 'not-started')

        for relay in relays:
            self.set('relay', relay, 'not-started')

    def set(self, group, name, status):
        """Set the status of a component. Similar to heartbeat"""

        if status in self.status_styles['check']:
            self.status[group][name] = {
                'name': name,
                'status': status,
                'status_style': self.status_styles[status],
                'timestamp': round(time.time())
            }

    def get(self):
        """Returns all statuses, marks status as failed if time of last heartbeat was too long ago"""

        out = {}

        for group_name in self.status:
            group = self.status[group_name]

            # Don't check sources for now due to sources blocking
            if group_name != 'source':

                for s in group:
                    last_ping = round(time.time()) - self.status[group_name][s]['timestamp']
                    last_status = self.status[group_name][s]['status']

                    if last_status == 'idle' and last_ping > 5 \
                            or last_status == 'active' and last_ping > 60 * 3:

                        self.status[group_name][s]['status'] = 'fail'
                        self.status[group_name][s]['status_style'] = self.status_styles['fail']

            out[group_name] = [self.status[group_name][s] for s in sorted(group)]

        return out


config = toml.load('config/config.toml')
audio_base_dir = config['audio_base_dir']

s = Status()
app = FastAPI()
test = False

app.mount('/audio', StaticFiles(directory=audio_base_dir), name='audio')
app.mount('/static', StaticFiles(directory='html/static'), name='static')


# ===== API URLs ===== #


@app.get('/api/get_alert')
async def read_item(callsign):
    for file in os.listdir(audio_base_dir):
        if f'{callsign}.wav' in file:
            return file

    return None


@app.get('/api/clear_alert')
async def clear_alert(callsign):
    for file in os.listdir(audio_base_dir):
        if f'{callsign}.wav' in file:
            os.remove(f'{audio_base_dir}/{file}')

            return 'ok'

    return None


@app.get('/api/get_status')
async def get_status():
    return s.get()


@app.get('/api/set_status')
async def set_status(group, name, status):
    s.set(group, name, status)

    return 'ok'


# ===== API URLs ===== #


@app.get('/')
async def admin_home():
    with open('html/home.html', 'r') as html_f:
        html = html_f.read()

    return HTMLResponse(content=html, status_code=200)


if __name__ == '__main__':
    uvicorn.run(
        'server:app',
        port=config['server']['port'],
        host=config['server']['host'],
        log_level='info')
