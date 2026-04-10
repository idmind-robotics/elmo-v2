import io
import fcntl
import time
import numpy as np

import middleware as mw


I2C_SLAVE_COMMAND = 0x0703


THRESHOLD = 14.0


def battery_percentage(voltage, a=30.955, b=-412.661, c=21.604, d=-0.935):
    """
    Compute battery percentage from voltage using piecewise calibration.

    Parameters
    ----------
    voltage : float
        Battery voltage in volts.
    a : float, optional
        Linear model multiplier, by default 30.955.
    b : float, optional
        Linear model offset, by default -412.661.
    c : float, optional
        Exponential model scale, by default 21.604.
    d : float, optional
        Exponential model decay rate, by default -0.935.

    Returns
    -------
    float
        Estimated battery charge percentage.

    Notes
    -----
    Uses an exponential model for voltages at or below THRESHOLD (14.0 V),
    and a linear model above THRESHOLD.
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
    Middleware driver node for reading battery ADC and publishing battery state.

    Attributes
    ----------
    battery : mw.Battery
        Middleware battery object used to publish raw/voltage/percentage.
    file_handle : io.BufferedReader
        File handle to I2C device `/dev/i2c-1`.
    node : mw.Node
        Middleware node issued for driver process.
    voltage_buffer : list[float]
        Rolling buffer of recent voltage samples for smoothing percentage.
    """
    
    def __init__(self):
        """
        Initialize driver, open I2C connection, and register node.

        Side effects
        ------------
        Opens `/dev/i2c-1` and configures I2C slave address.
        """
        self.battery = mw.Battery()
        self.file_handle = io.open("/dev/i2c-1", "rb", buffering=0)
        fcntl.ioctl(self.file_handle, I2C_SLAVE_COMMAND, self.battery.i2c_address)
        self.node = mw.Node("driver_battery")
        self.voltage_buffer = []

    def read_ad(self):
        """
        Read a 2-byte ADC value from the I2C battery sensor.

        Returns
        -------
        float
            ADC value scaled by 1/4 (register interpretation).
        """
        values = list(self.file_handle.read(2))
        return (values[0] * 256 + values[1]) / 4

    def ad_to_voltage(self, value):
        """
        Convert ADC reading to battery voltage.

        Parameters
        ----------
        value : float
            Raw ADC value from `read_ad`.

        Returns
        -------
        float
            Voltage in volts computed by calibration formula.
        """
        voltage = (value * 0.20618 + 2.268) / 10.0
        return voltage

    def run(self):
        """
        Main driver loop reading ADC, updating battery state, and smoothing percentage.

        Behavior
        --------
        - Sets `battery.ready` to True.
        - Reads sensor every 0.1 second.
        - Updates `battery.raw`, `battery.voltage`.
        - Maintains 100-sample running buffer and updates `battery.percentage`
          via `battery_percentage` when buffer exceeds 100 entries.
        - Handles `KeyboardInterrupt` gracefully and shuts down node on exit.
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
