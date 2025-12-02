#!/bin/bash

#export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

# set default microphone to virtual noise cancelled
/usr/bin/pactl set-default-source alsa_input.usb-GeneralPlus_USB_Audio_Device-00.mono-fallback.echo-cancel

# Wait for the virtual microphone to be created
MICROPHONE="alsa_input.usb-GeneralPlus_USB_Audio_Device-00.mono-fallback.echo-cancel"
until pactl list sources short | grep -q "$MICROPHONE"; do
  sleep 1
done

# Adjust microphone volume
/usr/bin/pactl set-source-volume alsa_input.usb-GeneralPlus_USB_Audio_Device-00.mono-fallback.echo-cancel 40%

# Wait for the server
until $(curl --output /dev/null --silent --head --fail http://localhost:8000); do
  sleep 1
done

source /home/elmo/.pyenv/versions/3.9.25/envs/py39-elmo/bin/activate
python /home/elmo/elmo-v2-idmind/src/vosk_transcriber.py