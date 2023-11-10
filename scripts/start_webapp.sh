#! /bin/bash

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000
until $(curl --output /dev/null --silent --head --fail http://localhost:8000); do
  sleep 1
done
/usr/bin/chromium --kiosk --app=http://localhost:8000?p=$RANDOM
#/usr/bin/chromium http://localhost:8000?p=$RANDOM
