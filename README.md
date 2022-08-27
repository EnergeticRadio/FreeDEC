![FreeDEC logo](https://raw.githubusercontent.com/EnergeticRadio/FreeDEC/main/logo.svg "FreeDEC")
###  A fully capable software based EAS encoder/decoder

This software is currently in beta, and potentially unstable. Use at your own risk.

## Features
- Modular design
- Built with networked use in mind
- Unlimited audio sources
- Unlimited audio relays

## Architecture
FreeDEC is designed to be modular, with networked use in mind. FreeDEC consists of several components:
- Audio source monitors
- Monitor core
- Relays
- Raw message handlers

#### Audio source monitors
Audio source monitors will monitor an audio source, and upon detecting a SAME header, output the SAME data. Audio source monitors will be executed and interfaced directly by the monitor core.

*In the future audio source monitors will also be responsible for recording detected alerts.*

#### Monitor core
The monitor core is responsible for receiving alerts from an audio source monitor, decoding, processing, filtering and logging alerts, and disseminating alerts to Relays and Raw message handlers. The monitor core runs a http server, which is used to communicate with Relays and Raw message handlers, as well as hosting an admin interface with status, configuration, and encoding functions.

#### Relays
Relays receive audio from the monitor core via it's http server, and relay a re-encoded version of the alert. The re-encoded alert is generated for each relay, and includes a same header modified with the relay's callsign, alert tone, audio message, and EOM. RWTs may not include an alert tone, or message.

In most instances, the relay will accept an incoming audio stream, mirroring it to it's output, and interrupting the input to play an alert upon receiving one.

#### Raw message handlers
Raw message handlers receive the raw audio and data recorded from an audio source monitor, and preform various tasks with the information. A few examples are: printing the alert on a printer or receipt printer, sending the alert to serial devices, and uploading the alert to online platforms such as YouTube, or discord. Alerts sent to raw message handlers are not filtered, aside from rejecting duplicates, as raw message handlers are designed for archival and logging.

## Installing
FreeDEC is currently only supported on linux based systems.

#### Dependencies:
python3
multimon-ng

#### Python dependencies:
easgen
fastapi
jack_client
moviepy
numpy
pydub
requests
soundfile
toml
uvicorn

#### Download and setup
Get the source
```
>>> git clone https://github.com/EnergeticRadio/FreeDEC.git
```

Alternatively
```
>>> wget https://github.com/EnergeticRadio/FreeDEC/archive/master.tar.gz
>>> tar -xvf master.tar.gz
```

Install python3, multimon-ng, as well as pip requirements
```
>>> pip3 install -r requirements.txt
```

setup (see below for configuration)
```
>>> cd FreeDEC-main
>>> nano config/config.toml
```
Start server and monitor
```
>>> python3 server.py & python3 monitor.py
FreeDEC Beta
Active audio sources: ...
All systems UP
Monitoring
```

## Configuration
#### timezone
The server's timezone, used for translating time of issue (UTC) to local time

#### audio_base_dir
The directory alert audio and data are located. If the path does not exist, FreeDEC will create it upon startup.

#### [server]
Configuration of the http server

#### [event_codes]
Event codes with the value of 'True' are relayed on all stations, if the alert matches the station's enabled FIPS codes.

#### [[stations]]

Multiple stations, or relays can be defined here, one per stations block.
```
[[stations]]
name="Station"
callsign="KXXX"
fips=[
    "48000",
    "48439",
    "48113",
]
````

name: Name of station. Can be anything.

callsign: Callsign of station or relay. max 8 characters, should be capitalized, and only contain A-Z, 0-9, and -.

fips: An alert must match at least one code in this list to be relayed

#### [[sources]]

Multiple audio sources can be defined here, one per block.
```
[[sources]]
name="KXXX"
type="pulse"
device="ALSA_DEVICE_NAME"
```

name: Name of source. Can be anything.
type: Type of audio source. pulseaudio is currently the only supported source.
device: Name of pulseaudio device
To get a list of pulseaudio devices, run the command:
```
>>> pacmd list-sources | grep name:
name: <alsa_output.pci-0000_00_14.2.analog-stereo.monitor>
```

The pulseaudio device name would be
> alsa_output.pci-0000_00_14.2.analog-stereo.monitor

## FreeDEC in action
#### Radio
[RadioC5 (DFW)](https://radioc5.com "RadioC5 (DFW)")

[Chad FM (DFW)](https://mytuner-radio.com/radio/chad-fm-490035/ "Chad FM (DFW)")

#### YouTube
[North Texas EAS Archive (DFW)](https://www.youtube.com/channel/UCyN9A5gQVlQaEHZ1tZ27PfA "North Texas EAS Archive (DFW)")
