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

import time
import re
import os
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import toml
import _audio as audio

all_fips = toml.load('config/fips.toml')
config = toml.load('config/config.toml')


def _message_applicable(eas):
    """Check event code against enabled events, and message FIPS code(s) against each station's enabled FIPS codes"""

    if config['event_codes'][eas['event_code']]:
        applicable_stations = []
        eas_fips = [f['code'][1:] for f in eas['areas']]

        for station in config['stations']:
            if any(check in eas_fips for check in station['fips']) or eas['entire_us']:
                applicable_stations.append(station['callsign'])

        if len(applicable_stations) >= 1:
            return applicable_stations

    return False


def _update_callsign(raw_same, callsign):
    """Replace header callsign"""

    new_same = raw_same.rsplit('-', 2)[0]
    new_same += f'-{callsign.replace("-", "/").ljust(8)}-'

    return new_same


def message_type(raw_same):
    """Check type of message: Header, End of Message, or Invalid"""

    if raw_same != 'NNNN':
        if re.search('ZCZC-[A-Z]{3}-[A-Z?]{3}-(\d{6}[-+])+\d{4}-\d{7}-[^-]{4,}-', raw_same):
            return 'eas'
        else:
            return 'invalid'
    else:
        return 'eom'


def is_dupe(decoded):
    """Check if received message is a duplicate"""

    raw_same = decoded['same']
    msg_ident = raw_same.rsplit('-', 2)[0]
    timestamp = decoded['timestamp']

    found_dupe = False

    try:
        with open('eas.log', 'r') as f:
            log_lines = f.readlines()

    except FileNotFoundError:
        log_lines = []

    for line in log_lines:
        line_ident = line.split(':')[1].rsplit('-', 2)[0]

        if msg_ident == line_ident:
            found_dupe = True
            break

    log_lines.append(f'{timestamp}:{raw_same}\n')

    with open('eas.log', 'w+') as f:
        for line in log_lines[-1000:]:
            f.write(line)

    return found_dupe


def get_modules():
    sources = [s['name'] for s in config['sources']]
    stations = [s['callsign'] for s in config['stations']]

    return sources, stations


def get_log(max_lines):
    """Return max_lines latest received alerts"""

    try:
        with open('eas.log', 'r') as f:
            alerts = []

            lines = f.readlines()[max_lines*-1:]
            lines.reverse()

            for line in lines:
                line = line.strip().split(':')
                received, same = line

                decoded = decode(same)

                archive_path = f'ARCHIVE/{received}-' \
                               f'{decoded["event_code"]}-{decoded["from_callsign"]}.wav'

                received = datetime.fromtimestamp(int(received)).strftime("%A, %B %d at %H:%M")
                issue = decoded['issue'].strftime("%A, %B %d at %H:%M")
                purge = decoded['purge'].strftime("%H:%M")

                decoded['received'] = received
                decoded['issue'] = issue
                decoded['purge'] = purge

                if os.path.exists(f'{config["audio_base_dir"]}/{archive_path}'):
                    decoded['raw_audio'] = f'audio/{archive_path}'

                alerts.append(decoded)

    except FileNotFoundError:
        alerts = []

    return alerts


def decode(raw_same):
    """Decode raw SAME string into dictionary"""

    same_a = raw_same.split('+')[0].split('-')
    same_b = raw_same.split('+')[1].split('-')

    same_a.pop(0)
    org = same_a.pop(0)
    event_code = same_a.pop(0)
    event = all_fips['event'][event_code]
    eas_purge = same_b.pop(0)
    eas_issue = same_b.pop(0)
    callsign = same_b.pop(0).strip()
    fips = []
    us_all = False
    timestamp = int(time.time())

    year = datetime.now().year
    issue_dt = datetime.strptime(f"{year}{eas_issue}", '%Y%j%H%M').replace(tzinfo=timezone.utc)
    issue = issue_dt.astimezone(ZoneInfo(config['timezone']))
    purge = issue + timedelta(hours=int(eas_purge[:2]), minutes=int(eas_purge[2:]))

    for fips_code in same_a:
        if bool(int(fips_code[0])):
            us_all = True

        if fips_code[1:3] != '00':
            state = all_fips['state'][fips_code[1:3]]
        else:
            us_all = True
            state = 'USA'

        if fips_code[3:6] != '000':
            county = all_fips['county'][f'{fips_code[1:3]}{fips_code[3:6]}']
        else:
            county = 'All of'

        fips.append({
            'code': fips_code,
            'county': county,
            'state': state
        })

    areas_str = '; '.join([f'{s["county"]} {s["state"]}' for s in fips])

    eas = {
        'same': raw_same,
        'ident': raw_same.rsplit('-', 2)[0],
        'originator': org,
        'event_code': event_code,
        'event': event,
        'areas': fips,
        'areas_str': areas_str,
        'entire_us': us_all,
        'from_callsign': callsign.replace('/', '-'),
        'filename': f'{timestamp}-{event_code}',
        'timestamp': timestamp,
        'issue': issue,
        'purge': purge
    }

    return eas


def re_encode(eas):
    """Generate EAS with new SAME header and EOM for each station, keeping the audio message"""

    base = config['audio_base_dir']
    filename = eas["filename"]
    same = eas['same']
    sender = eas["from_callsign"]

    stations = _message_applicable(eas)

    if stations:
        msg = audio.extract_message(f'{base}/{filename}.wav')

        for station in stations:
            header = _update_callsign(same, station)
            out_filename = f'{base}/{filename}-{station}.wav'

            audio.encode_eas(header, out_filename, msg=msg)

    os.rename(f'{base}/{filename}.wav', f'{base}/ARCHIVE/{filename}-{sender}.wav')

    with open(f'{base}/ARCHIVE/{filename}-{sender}.toml', 'w') as f:
        toml.dump(eas, f)
