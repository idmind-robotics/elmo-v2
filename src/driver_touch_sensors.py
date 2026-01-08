"""
Driver node.

This node manages the touch sensors.

Uses the adafruit_mpr121 library to read the touch sensors.
"""

import time
import middleware as mw

# Pi5 Neo / RPi5 support for I2C
import busio
from adafruit_mpr121 import MPR121

# On Pi 5, use the Blinka compatibility import
try:
    import board
except ImportError:
    # Fallback for Pi 5: define SCL and SDA manually
    import digitalio
    import adafruit_blinka.microcontroller.rp2040.board as rpboard  # Pi5 Blinka I2C

    board = rpboard


class DriverTouchSensors:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        # Use I2C bus 1 (/dev/i2c-1) for Pi5
        i2c = busio.I2C(board.SCL, board.SDA)
        self.mpr121 = MPR121(i2c)
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
                self.touch_sensors.head_4_raw = self.mpr121.filtered_data(5)
                time.sleep(0.1)
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    node = DriverTouchSensors()
    node.run()
