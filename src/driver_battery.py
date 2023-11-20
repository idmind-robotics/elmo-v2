#!/usr/bin/env python


"""

Driver node.

This node reads the battery voltage and publishes it to the middleware.

"""


import io
import fcntl
import time
import numpy as np

import middleware as mw


I2C_SLAVE_COMMAND=0x0703
THRESHOLD = 14.0


def battery_percentage(voltage, a=30.955, b=-412.661, c=21.604, d=-0.935):
    x_linear = a * voltage + b
    x_exponential = c * np.exp(-d * (voltage - THRESHOLD))
    if voltage <= THRESHOLD:
        result = x_exponential
    else:
        result = x_linear
    result = min(100.0, max(0.0, result))
    return result


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
        value_at_13v = self.battery.ad_at_13v
        value_at_16v = self.battery.ad_at_16v
        x = [value_at_13v, value_at_16v]
        y = [130, 160]
        self.slope, self.bias = np.polyfit(x, y, 1)
        self.voltage_buffer = []
    
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
        # voltage = (value * 0.20618 + 2.268) / 10.0
        voltage = (value * self.slope + self.bias) / 10.0
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
                voltage = self.ad_to_voltage(raw)
                self.battery.voltage = voltage
                self.voltage_buffer.append(voltage)
                if len(self.voltage_buffer) > 100:
                    self.voltage_buffer.pop(0)
                    m = np.mean(self.voltage_buffer)
                    self.battery.percentage = battery_percentage(m)
        except KeyboardInterrupt:
            pass
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverBattery()
    node.run()