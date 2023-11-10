#! /usr/bin/env python


"""

Driver node.

This node manages the touch sensors.

Uses the adafruit_mpr121 library to read the touch sensors.

"""

import time
import board
import busio
import adafruit_mpr121

import middleware as mw


class DriverTouchSensors:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        i2c = busio.I2C(board.SCL, board.SDA)
        self.mpr121 = adafruit_mpr121.MPR121(i2c)
        self.touch_sensors = mw.TouchSensors()
        self.node = mw.Node("driver_touch_sensors")

    def run(self):
        """
        Main loop.
        """
        try:
            self.touch_sensors.ready = True
            while not self.node.is_shutdown():
                self.touch_sensors.chest_raw = self.mpr121.filtered_data(0)
                self.touch_sensors.head_0_raw = self.mpr121.filtered_data(1)
                self.touch_sensors.head_1_raw = self.mpr121.filtered_data(2)
                self.touch_sensors.head_2_raw = self.mpr121.filtered_data(3)
                self.touch_sensors.head_3_raw = self.mpr121.filtered_data(4)    
                time.sleep(0.1)
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverTouchSensors()
    node.run()