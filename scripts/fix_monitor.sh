#! /bin/bash


export DISPLAY=:0


while true; do
    xrandr_output=$(xrandr)
    if [[ $xrandr_output == *"HDMI-1 connected"* ]]; then
        echo "HDMI-1 is connected!"
        break
    else
        echo "HDMI-1 not found. Waiting..."
        sleep 1
    fi
done

sleep 5
echo "Rotating display"
/usr/bin/xrandr --output HDMI-1 --rotate left

echo "Mapping input device to display"
/usr/bin/xinput map-to-output 8 "HDMI-1"

echo "Done"
