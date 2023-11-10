#! /usr/bin/env python


"""

Driver node.

This node manages the GPIO pins.

GPIO pins are used to control audio and monitor power, the stay enable pin and the power button.

"""


import RPi.GPIO as GPIO
import os

import time
import middleware as mw


class DriverGpio:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.node = mw.Node("driver_gpio")
        self.gpio = mw.GPIO()

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.gpio.button_pin, GPIO.IN)
        GPIO.setup(self.gpio.shutdown_pin, GPIO.IN)
        GPIO.setup(self.gpio.stay_enable_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.gpio.audio_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.gpio.monitor_pin, GPIO.OUT, initial=GPIO.HIGH)
    
    def enable_audio(self, control):
        """
        Enable or disable the audio power.
        """
        if control:
            self.node.loginfo("gpio: audio on")
            GPIO.output(self.gpio.audio_pin, GPIO.HIGH)
        else:
            self.node.loginfo("gpio: audio off")
            GPIO.output(self.gpio.audio_pin, GPIO.LOW)
    
    def enable_monitor(self, control):
        """
        Enable or disable the monitor power.
        """
        if control:
            self.node.loginfo("gpio: monitor on")
            GPIO.output(self.gpio.monitor_pin, GPIO.HIGH)
        else:
            self.node.loginfo("gpio: monitor off")
            GPIO.output(self.gpio.monitor_pin, GPIO.LOW)

    def run(self):
        """
        Main loop.
        """
        try:
            self.gpio.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.gpio.audio_enable and not self.gpio.audio_enabled:
                    self.enable_audio(True)
                    self.gpio.audio_enabled = True
                elif not self.gpio.audio_enable and self.gpio.audio_enabled:
                    self.enable_audio(False)
                    self.gpio.audio_enabled = False
                if self.gpio.monitor_enable and not self.gpio.monitor_enabled:
                    self.enable_monitor(True)
                    self.gpio.monitor_enabled = True
                elif not self.gpio.monitor_enable and self.gpio.monitor_enabled:
                    self.enable_monitor(False)
                    self.gpio.monitor_enabled = False
                if GPIO.input(self.gpio.button_pin):
                    self.gpio.button_pressed = True
                    self.node.loginfo("gpio: button pressed")
                else:
                    self.gpio.button_pressed = False
                if GPIO.input(self.gpio.shutdown_pin):
                    self.gpio.robot_shutdown = True
                    self.node.loginfo("gpio: shutdown")
                else:
                    self.gpio.robot_shutdown = False
        except KeyboardInterrupt:
            pass
        finally:
            """
            Cleanup routine.
            Disable audio and monitor power.
            """
            self.enable_audio(False)
            self.gpio.audio_enabled = False
            time.sleep(0.1)
            self.enable_monitor(False)
            self.gpio.monitor_enabled = False
            time.sleep(0.1)
            GPIO.cleanup()
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverGpio()
    node.run()
