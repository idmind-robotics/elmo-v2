#!/usr/bin/env python


"""

Driver node.

This node reads the battery voltage and publishes it to the middleware.

"""


import io
import fcntl
import time

import middleware as mw


I2C_SLAVE_COMMAND=0x0703


class DriverBattery:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.battery = mw.Battery()
        self.file_handle =  io.open("/dev/i2c-1", "rb", buffering=0)
        fcntl.ioctl(self.file_handle, I2C_SLAVE_COMMAND, self.battery.i2c_address)
        self.node = mw.Node("driver_battery")
    
    def read_ad(self):
        """
        Read the AD values.
        """
        values = list(self.file_handle.read(2))
        return (values[0] * 256 + values[1]) / 4
    
    def ad_to_voltage(self, value):
        """
        Convert the AD value to voltage.
        """
        voltage = (value * 0.20618 + 2.268) / 10.0
        return voltage
    
    def run(self):
        """
        Main loop.
        """
        try:
            self.battery.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
                raw = self.read_ad()
                self.battery.raw = raw
                self.battery.voltage = self.ad_to_voltage(raw)
        except KeyboardInterrupt:
            pass
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverBattery()
    node.run()