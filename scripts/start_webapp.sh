#! /bin/bash

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

exec > /tmp/kiok.log 2>&1
/bin/bash /home/idmind/elmo-v2/scripts/start.sh &


# Wait for PipeWire and display to exist
until pw-cli info 0 &>/dev/null; do
  echo "Waiting for PipeWire..."
  sleep 2
done

until xset q &>/dev/null; do
  echo "Waiting for display..."
  sleep 2
done

# set default microphone to virtual noise cancelled using PipeWire native commands
MICROPHONE_NAME="alsa_input.usb-C-Media_Electronics_Inc._USB_PnP_Sound_Device-00.analog-mono"

# Wait for the microphone to be available and get its node ID
MICROPHONE_ID="30"
#until [ -n "$MICROPHONE_ID" ]; do
# MICROPHONE_ID=$(pw-dump Node | grep -B5 -A5 "$MICROPHONE_NAME" | grep '"id"' | head -1 | grep -oP ':\s*\K\d+')
#  [ -z "$MICROPHONE_ID" ] && sleep 1
#done

# Set as default source
pw-metadata -n default 0 default.audio.source "{ \"name\": \"$MICROPHONE_NAME\" }"

# Set volume to 40% (0.4 in PipeWire)
pw-cli set-param "$MICROPHONE_ID" Props '{ "volume": 0.4, "mute": false }'

# Wait for the server
until $(curl --output /dev/null --silent --head --fail http://localhost:8000); do
  sleep 1
done

CHROMIUM_CMD="/usr/bin/chromium"

# Start the webapp
$CHROMIUM_CMD \
  --disable-gpu \
  --use-fake-ui-for-media-stream \
  --password-store=basic \
  --kiosk \
  --app="http://localhost:8000?p=$RANDOM" &
