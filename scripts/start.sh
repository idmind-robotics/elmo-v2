 #! /bin/bash

# Set environment for X11 / Pi if needed
export XDG_RUNTIME_DIR=/run/user/1000
export DISPLAY=0:0

# Wait for UART0 to be ready
#UART_DEVICE="/dev/serial0"  # could be /dev/ttyAMA0 on some models
#echo "Waiting for UART device $UART_DEVICE to be ready..."

#while [ ! -e "$UART_DEVICE" ]; do
#    echo "$(date): UART device $UART_DEVICE not ready yet. Sleeping 2 seconds..."
#    sleep 2
#done

echo "Waiting for Redis..."
until redis-cli ping >/dev/null 2>&1; do
    sleep 2
done
echo "Redis is ready!"

# create log folder, if it doesn't exist
mkdir -p /home/idmind/logs


# Activate virtual environment
source /home/idmind/elmo-v2/.venv/bin/activate

cd /home/idmind/elmo-v2/src


uv run middleware.py reset
uv run load_config.py

uv run driver_battery.py >> /home/idmind/logs/driver_battery.log &
uv run driver_gpio.py >> /home/idmind/logs/driver_gpio.log &
sudo /usr/bin/python driver_leds.py &
uv run driver_microphone.py >> /home/idmind/logs/driver_microphone.log &
uv run driver_pan_tilt.py >> /home/idmind/logs/driver_pan_tilt.log &
uv run driver_power.py >> /home/idmind/logs/driver_power.log &
uv run driver_speakers.py >> /home/idmind/logs/driver_speakers.log &
uv run driver_speech.py >> /home/idmind/logs/driver_speech.log &
/usr/bin/python driver_touch_sensors.py >> /home/idmind/logs/driver_touch_sensors.log &

uv run http_server.py >> /home/idmind/logs/http_server.log &
uv run robot_api.py >> /home/idmind/logs/robot_api.log &
uv run touch_calibrator.py >> /home/idmind/logs/touch_calibrator.log &
/usr/bin/python mjpeg_server_2.py >> /home/idmind/logs/mjpeg_server_2.log &
uv run motor_temperature_watchdog.py >> /home/idmind/logs/motor_temperature_watchdog.log &

uv run behaviour_blush.py >> /home/idmind/logs/behaviour_blush.log &
uv run behaviour_look_around.py >> /home/idmind/logs/behaviour_look_around.log &
uv run behaviour_test_motors.py >> /home/idmind/logs/behaviour_test_motors.log &
uv run behaviour_wifi_connect.py >> /home/idmind/logs/behaviour_wifi_connect.log &

sleep 5
uv run mode_manager.py >> /home/idmind/logs/mode_manager.log &

