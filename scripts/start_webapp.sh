#! /bin/bash

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

# Wait for PulseAudio and display to exist
until [ -d /run/user/1000/pulse ] && pactl info &>/dev/null; do
  echo "Waiting for PulseAudio..."
  sleep 2
done

until xset q &>/dev/null; do
  echo "Waiting for display..."
  sleep 2
done

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


# Start the webapp

# /usr/bin/chromium --kiosk --app=http://localhost:8000?p=$RANDOM
# /usr/bin/chromium-browser --use-fake-ui-for-media-stream --kiosk --app=http://localhost:8000?p=$RANDOM
# /usr/bin/chromium --use-fake-ui-for-media-stream --kiosk --app=http://localhost:8000?p=$RANDOM
# /usr/bin/chromium http://localhost:8000?p=$RANDOM

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
