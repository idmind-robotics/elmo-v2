 #! /bin/bash

# Set environment for X11 / Pi if needed
export XDG_RUNTIME_DIR=/run/user/1000
export DISPLAY=0:0

# Wait for UART0 to be ready
UART_DEVICE="/dev/serial0"  # could be /dev/ttyAMA0 on some models
echo "Waiting for UART device $UART_DEVICE to be ready..."

while [ ! -e "$UART_DEVICE" ]; do
    echo "$(date): UART device $UART_DEVICE not ready yet. Sleeping 2 seconds..."
    sleep 2
done

echo "Waiting for Redis..."
until redis-cli ping >/dev/null 2>&1; do
    sleep 2
done
echo "Redis is ready!"

# create log folder, if it doesn't exist
mkdir -p /home/elmo/logs

cd /home/elmo/elmo-v2/src

# Activate virtual environment
source /home/elmo/.pyenv/versions/3.9.25/envs/py39-elmo/bin/activate

# Run all the scripts in python 3.9.25
# All the scripts that are heavily depedent on hardware are run with python 3.13 (native)
python middleware.py reset
python load_config.py

python driver_battery.py >> /home/elmo/logs/driver_battery.log &
python driver_gpio.py >> /home/elmo/logs/driver_gpio.log &
sudo /usr/bin/python driver_leds.py &
python driver_microphone.py >> /home/elmo/logs/driver_microphone.log &
python driver_pan_tilt.py >> /home/elmo/logs/driver_pan_tilt.log &
python driver_power.py >> /home/elmo/logs/driver_power.log &
python driver_speakers.py >> /home/elmo/logs/driver_speakers.log &
python driver_speech.py >> /home/elmo/logs/driver_speech.log &
/usr/bin/python driver_touch_sensors.py >> /home/elmo/logs/driver_touch_sensors.log &

python http_server.py >> /home/elmo/logs/http_server.log &
python robot_api.py >> /home/elmo/logs/robot_api.log &
python touch_calibrator.py >> /home/elmo/logs/touch_calibrator.log &
/usr/bin/python mjpeg_server_2.py >> /home/elmo/logs/mjpeg_server_2.log &
python motor_temperature_watchdog.py >> /home/elmo/logs/motor_temperature_watchdog.log &

python behaviour_blush.py >> /home/elmo/logs/behaviour_blush.log &
python behaviour_look_around.py >> /home/elmo/logs/behaviour_look_around.log &
python behaviour_test_motors.py >> /home/elmo/logs/behaviour_test_motors.log &
python behaviour_wifi_connect.py >> /home/elmo/logs/behaviour_wifi_connect.log &

sleep 5
python mode_manager.py >> /home/elmo/logs/mode_manager.log &

