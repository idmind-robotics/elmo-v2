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
    """
    Middleware driver node for capacitive touch inputs.

    Attributes
    ----------
    mpr121 : MPR121
        I2C touch sensor controller instance.
    touch_sensors : mw.TouchSensors
        Middleware touch sensor state object.
    node : mw.Node
        Middleware node used for shutdown and logging.
    """
    def __init__(self):
        """
        Initialize I2C touch sensor and middleware node.

        Side effects
        ------------
        - Opens I2C bus (board.SCL, board.SDA).
        - Attaches MPR121 controller.
        - Creates middleware node `driver_touch_sensors`.
        """
        # Use I2C bus 1 (/dev/i2c-1) for Pi5
        i2c = busio.I2C(board.SCL, board.SDA)
        self.mpr121 = MPR121(i2c)
        self.touch_sensors = mw.TouchSensors()
        self.node = mw.Node("driver_touch_sensors")

    def run(self):
        """
        Main loop sampling touch sensor values and writing them to middleware.

        Behavior
        --------
        - Sets `touch_sensors.ready` True.
        - Reads raw filtered values of all 6 touch channels continuously.
        - Updates the middleware with chest and head sensor values.
        - Sleeps 0.1 seconds between polls.
        - Shuts down middleware node on exit.

        Returns
        -------
        None
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
