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
until redis-cli ping >/dev/null; do
    sleep 2
done
echo "Redis is ready!"

# Ensure hostnames
grep -q "127.0.0.1 elmo" /etc/hosts || echo "127.0.0.1 elmo" | sudo tee -a /etc/hosts
grep -q "127.0.0.1 elmo2" /etc/hosts || echo "127.0.0.1 elmo2" | sudo tee -a /etc/hosts

mkdir -p /home/idmind/elmo-v2/logs

cd /home/idmind/elmo-v2/src
source /home/idmind/elmo-v2/.venv/bin/activate
python middleware.py reset > /dev/null
python load_config.py > /dev/null

python driver_battery.py >> /home/idmind/elmo-v2/logs/driver_battery.log &
python driver_gpio.py >> /home/idmind/elmo-v2/logs/driver_gpio.log &
sudo -n /home/idmind/elmo-v2/.venv/bin/python driver_leds.py >> /home/idmind/elmo-v2/logs/driver_leds.log &
# python driver_microphone.py >> /home/idmind/elmo-v2/logs/driver_microphone.log &
python driver_pan_tilt.py >> /home/idmind/elmo-v2/logs/driver_pan_tilt.log &
python driver_power.py >> /home/idmind/elmo-v2/logs/driver_power.log &
python driver_speakers.py >> /home/idmind/elmo-v2/logs/driver_speakers.log &
# python driver_speech.py >> /home/idmind/elmo-v2/logs/driver_speech.log &
python driver_touch_sensors.py >> /home/idmind/elmo-v2/logs/driver_touch_sensors.log &

python http_server.py >> /home/idmind/elmo-v2/logs/http_server.log &
python robot_api.py >> /home/idmind/elmo-v2/logs/robot_api.log &
python touch_calibrator.py >> /home/idmind/elmo-v2/logs/touch_calibrator.log &
python mjpeg_server_2.py >> /home/idmind/elmo-v2/logs/mjpeg_server_2.log &
python motor_temperature_watchdog.py >> /home/idmind/elmo-v2/logs/motor_temperature_watchdog.log &

python behaviour_blush.py >> /home/idmind/elmo-v2/logs/behaviour_blush.log &
python behaviour_test_motors.py >> /home/idmind/elmo-v2/logs/behaviour_test_motors.log &
# python behaviour_wifi_connect.py >> /home/idmind/elmo-v2/logs/behaviour_wifi_connect.log &
(sleep 8; python behaviour_photographer.py) >> /home/idmind/elmo-v2/logs/behaviour_photographer.log &
(sleep 8; python behaviour_hello.py) >> /home/idmind/elmo-v2/logs/behaviour_hello.log &

(sleep 5; python mode_manager.py >> /home/idmind/elmo-v2/logs/mode_manager.log) &

sleep 2
exec > /tmp/kiosk.log 2>&1
/bin/bash /home/idmind/elmo-v2/scripts/start_webapp.sh &