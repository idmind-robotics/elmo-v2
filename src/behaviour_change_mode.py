#! /usr/bin/env python


"""

Behaviour node.

When the power button is pressed, the behaviour changes the leds.

"""

import time

import middleware as mw


LOOP_RATE = 10


MODE_IDLE = 0
MODE_MUSIC = 1
MODE_CALL = 2


class ModeManager:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        Set internal variables.
        """
        self.leds = mw.Leds()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.server.wait_for_ready()
        self.gpio = mw.GPIO()
        self.node = mw.Node("behaviour_change_mode")
        self.modes = [
            MODE_IDLE,
            MODE_MUSIC,
            MODE_CALL,
        ]
        self.current_mode_idx = -1

    def idle_mode(self):
        """
        Load default icon.
        """
        self.node.loginfo("idle mode")
        url = self.server.url_for_icon("elmo_idm.png")
        self.leds.load_from_url(url)

    def music_mode(self):
        """
        Load music icon.
        """
        self.node.loginfo("music mode")
        url = self.server.url_for_icon("music.png")
        self.leds.load_from_url(url)
    
    def call_mode(self):
        """
        Load call icon.
        """
        self.node.loginfo("call mode")
        url = self.server.url_for_icon("call.png")
        self.leds.load_from_url(url)
    
    def next_mode(self):
        """
        Change to next mode.
        """
        self.node.loginfo("next mode")
        self.current_mode_idx += 1
        if self.current_mode_idx >= len(self.modes):
            self.current_mode_idx = 0
        mode = self.modes[self.current_mode_idx]
        if mode == MODE_IDLE:
            self.idle_mode()
        elif mode == MODE_MUSIC:
            self.music_mode()
        elif mode == MODE_CALL:
            self.call_mode()
        else:
            raise RuntimeError("unknown mode")

    def run(self):
        """
        Main loop.
        """
        try:
            self.node.loginfo("starting behaviour")
            was_pressed = False
            self.next_mode()
            while not self.node.is_shutdown():
                if not self.behaviours.change_mode:
                    continue
                is_pressed = self.gpio.button_pressed
                if is_pressed and not was_pressed:
                    self.next_mode()
                was_pressed = is_pressed
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = ModeManager()
    node.run()