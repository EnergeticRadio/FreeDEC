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


def is_dupe(raw_same):
    """Check if received message is a duplicate"""

    msg_ident = raw_same.rsplit('-', 2)[0]

    try:
        with open('eas.log', 'r') as f:
            prev_idents = []

            for _ in range(10):
                line = f.readline()

                if not line == '':
                    prev_idents.append(line.split(':')[1].rsplit('-', 2)[0])

                else:
                    break

    except FileNotFoundError:
        prev_idents = ['']

    with open('eas.log', 'a+') as f:
        f.write(f'{round(time.time())}:{raw_same}\n')

    return msg_ident in prev_idents


def decode(raw_same):
    """Decode raw SAME string into dictionary"""

    same_a = raw_same.split('+')[0].split('-')
    same_b = raw_same.split('+')[1].split('-')

    same_a.pop(0)
    org = same_a.pop(0)
    event_code = same_a.pop(0)
    event = all_fips['event'][event_code]
    purge = same_b.pop(0)
    issue = same_b.pop(0)
    callsign = same_b.pop(0).strip()
    fips = []
    us_all = False

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

    eas = {
        'same': raw_same,
        'ident': raw_same.rsplit('-', 2)[0],
        'originator': org,
        'event_code': event_code,
        'event': event,
        'areas': fips,
        'entire_us': us_all,
        'purge': purge,
        'time_issued': issue,
        'from_callsign': callsign.replace('/', '-'),
        'filename': f'{int(time.time())}-{event_code}'
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