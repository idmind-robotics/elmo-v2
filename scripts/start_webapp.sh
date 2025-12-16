#! /bin/bash

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

# Wait for PipeWire and display to exist
until pw-cli info core &>/dev/null; do
  echo "Waiting for PipeWire..."
  sleep 2
done

until xset q &>/dev/null; do
  echo "Waiting for display..."
  sleep 2
done

# set default microphone to virtual noise cancelled using PipeWire native commands
MICROPHONE_NAME="alsa_input.usb-GeneralPlus_USB_Audio_Device-00.mono-fallback"

# Wait for the microphone to be available and get its node ID
MICROPHONE_ID=""
until [ -n "$MICROPHONE_ID" ]; do
  MICROPHONE_ID=$(pw-dump Node | grep -B5 -A5 "$MICROPHONE_NAME" | grep '"id"' | head -1 | grep -oP ':\s*\K\d+')
  [ -z "$MICROPHONE_ID" ] && sleep 1
done

# Set as default source
pw-cli set-default Audio/Source "$MICROPHONE_ID"

# Set volume to 40% (0.4 in PipeWire)
pw-cli set_param "$MICROPHONE_ID" Props '{ volume: 0.4 }'

# Wait for the server
until $(curl --output /dev/null --silent --head --fail http://localhost:8000); do
  sleep 1
done


# Determine which chromium executable to use
CHROMIUM_CMD=""
if [ -x /usr/bin/chromium ]; then
  CHROMIUM_CMD="/usr/bin/chromium"
elif [ -x /usr/bin/chromium-browser ]; then
  CHROMIUM_CMD="/usr/bin/chromium-browser"
else
  echo "No suitable Chromium executable found."
  exit 1
fi

# Start the webapp
$CHROMIUM_CMD --use-fake-ui-for-media-stream --password-store=basic --kiosk --app=http://localhost:8000?p=$RANDOM
