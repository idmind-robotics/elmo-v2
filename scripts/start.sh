#! /bin/bash


export XDG_RUNTIME_DIR=/run/user/1000
export DISPLAY=0:0

cd /home/idmind/elmo-v2/src

/usr/bin/python middleware.py reset
/usr/bin/python load_config.py

/usr/bin/python driver_battery.py &
/usr/bin/python driver_gpio.py &
sudo /usr/bin/python driver_leds.py &
/usr/bin/python driver_pan_tilt.py &
/usr/bin/python driver_power.py &
/usr/bin/python driver_speakers.py &
/usr/bin/python driver_touch_sensors.py &
/usr/bin/python driver_microphone.py &
/usr/bin/python driver_speech.py &

/usr/bin/python http_server.py &
/usr/bin/python robot_api.py &
/usr/bin/python touch_calibrator.py &
/usr/bin/python mjpeg_server_2.py &

/usr/bin/python behaviour_blush.py &
/usr/bin/python behaviour_look_around.py &
/usr/bin/python behaviour_change_mode.py &

