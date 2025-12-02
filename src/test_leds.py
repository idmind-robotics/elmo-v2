#! /usr/bin/env python


import time

import middleware as mw


rate = 5  # Hz


leds = mw.Leds()
server = mw.Server()

red_url = server.url_for_icon("red.png")
green_url = server.url_for_icon("green.png")
blue_url = server.url_for_icon("blue.png")
black_url = server.url_for_icon("black.png")
idm_url = server.url_for_icon("elmo_idm.png")


try:
    while True:
        leds.load_from_url(red_url)
        time.sleep(1.0 / rate)
        leds.load_from_url(green_url)
        time.sleep(1.0 / rate)
        leds.load_from_url(blue_url)
        time.sleep(1.0 / rate)
        leds.load_from_url(black_url)
        time.sleep(1.0 / rate)
        leds.load_from_url(idm_url)
        time.sleep(1.0 / rate)
finally:
    time.sleep(1.0)
    leds.load_from_url(idm_url)
