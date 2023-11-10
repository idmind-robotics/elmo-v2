#! /usr/bin/bash

sudo apt update
sudo apt upgrade -y

# Redis
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt install redis -y
pip install redis

# Neopixel
sudo apt install python-pip -y
sudo pip install rpi_ws281x adafruit-circuitpython-neopixel

# Chromium browser
sudo apt install chromium-browser -y

# TTS
python3 -m pip install gTTS
sudo apt install mpg123


