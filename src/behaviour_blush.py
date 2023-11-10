#! /usr/bin/env python


"""

Behaviour node.

When a head touch is detected, the behaviour updates the onboard image,
plays a sound and changes the leds.

"""


import time

import middleware as mw


LOOP_RATE = 10
TOUCH_COUNTER_THRESHOLD = 3
COOLDOWN = 5 * LOOP_RATE


class BehaviourBlush:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.touch_sensors = mw.TouchSensors()
        self.leds = mw.Leds()
        self.onboard = mw.Onboard()
        self.speakers = mw.Speakers()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.node = mw.Node("behaviour_blush")
    
    def blush(self):
        """
        Blush routine.
        Updates the onboard image, plays a sound and changes the leds.
        """
        self.node.loginfo("blushing")
        image_url = self.server.url_for_image("love.png")
        self.onboard.image = image_url
        sound_url = self.server.url_for_sound("love.wav")
        self.speakers.url = sound_url
        icon_url = self.server.url_for_icon("heartbeat.gif")
        self.leds.load_from_url(icon_url) 
        time.sleep(5.0)
        image_url = self.server.url_for_image("normal.png")
        self.onboard.image = image_url
        icon_url = self.server.url_for_icon("elmo_idm.png")
        self.leds.load_from_url(icon_url)

    def run(self):
        """
        Main loop.
        """
        try:
            self.node.loginfo("starting behaviour")
            touch_counter = 0
            cooldown_counter = 0
            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)
                if cooldown_counter > 0:
                    cooldown_counter -= 1
                if self.behaviours.blush and self.touch_sensors.head_touch():
                    if touch_counter < TOUCH_COUNTER_THRESHOLD:
                        touch_counter += 1
                    if touch_counter == TOUCH_COUNTER_THRESHOLD:
                        if cooldown_counter == 0:
                            self.blush()
                            cooldown_counter = COOLDOWN
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = BehaviourBlush()
    node.run()
