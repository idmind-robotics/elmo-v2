"""

Driver node.

This node reads the battery voltage and publishes it to the middleware.

"""

import io
import fcntl
import time
import numpy as np

import middleware as mw


I2C_SLAVE_COMMAND = 0x0703


THRESHOLD = 14.0


def battery_percentage(voltage, a=30.955, b=-412.661, c=21.604, d=-0.935):
    """
    Estimate battery percentage from a given voltage reading.

    Uses a piecewise model: linear above the threshold, exponential at or below it.

    Parameters
    ----------
    voltage : float
        Measured battery voltage in volts.
    a : float
        Linear slope coefficient (default: 30.955).
    b : float
        Linear intercept coefficient (default: -412.661).
    c : float
        Exponential scale coefficient (default: 21.604).
    d : float
        Exponential decay coefficient (default: -0.935).

    Returns
    -------
    float
        Estimated battery percentage.
    """
    x_linear = a * voltage + b
    x_exponential = c * np.exp(-d * (voltage - THRESHOLD))
    if voltage <= THRESHOLD:
        result = x_exponential
    else:
        result = x_linear
    return result


class DriverBattery:
    """
    Hardware driver for the battery monitor over I2C.

    Reads raw AD values from the battery sensor via the I2C bus, converts
    them to voltage, maintains a rolling average, and publishes voltage and
    percentage to the middleware.

    > ## Attributes
    ``battery : mw.Battery`` : Middleware battery state object used to publish voltage, percentage, and ready flag.
    ``file_handle : io.FileIO`` : Open file handle to the I2C device at ``/dev/i2c-1``.
    ``node : mw.Node`` : Middleware node used for shutdown signalling and logging.
    ``voltage_buffer : list[float]`` : Rolling buffer of the last 100 voltage readings used to compute a smoothed mean.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.

        Opens the I2C device file, binds it to the battery's I2C address,
        initialises the middleware node, and prepares the voltage rolling buffer.
        """
        self.battery = mw.Battery()
        self.file_handle = io.open("/dev/i2c-1", "rb", buffering=0)
        fcntl.ioctl(self.file_handle, I2C_SLAVE_COMMAND, self.battery.i2c_address)
        self.node = mw.Node("driver_battery")
        self.voltage_buffer = []

    def read_ad(self):
        """
        Read the AD values.

        Reads two bytes from the I2C device and combines them into a
        single 10-bit AD value.

        Returns
        -------
        float
            Raw AD value in the range [0, 1023].
        """
        values = list(self.file_handle.read(2))
        return (values[0] * 256 + values[1]) / 4

    def ad_to_voltage(self, value):
        """
        Convert the AD value to voltage.

        Applies a linear calibration formula to map the raw AD reading
        to a battery voltage in volts.

        Parameters
        ----------
        value : float
            Raw AD value as returned by ``read_ad``.

        Returns
        -------
        float
            Calibrated battery voltage in volts.
        """
        voltage = (value * 0.20618 + 2.268) / 10.0
        return voltage

    def run(self):
        """
        Main loop.

        Continuously reads the battery AD value, converts it to voltage,
        appends it to the rolling buffer, and — once 100 samples are
        accumulated — publishes the smoothed voltage mean and estimated
        percentage to middleware. Runs until a ``KeyboardInterrupt`` or
        middleware shutdown is requested, then shuts down the node.
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


if __name__ == "__main__":
    node = DriverBattery()
    node.run()
