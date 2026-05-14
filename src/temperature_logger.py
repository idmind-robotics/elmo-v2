#! /usr/bin/env python


"""

Tool node.

Temperature logger.

This module periodically reads raw motor temperatures, converts them
to calibrated values and stores them in a CSV log file.

"""


import time
import datetime


import middleware as mw


pan = mw.Pan()
tilt = mw.Tilt()

slope = 0.7105
intercept = -79.47

outfile = open("/home/idmind/temperature_log.csv", "w")
outfile.write("Time, Pan, Tilt\n")
outfile.close()

delay = 60.0 * 1.0  # 1 minutes


def convert(temperature):
    """
    Convert raw temperature readings to calibrated values.

    Parameters
    ----------
    temperature : float
        Raw temperature sensor value.

    Returns
    -------
    float
        Calibrated temperature value.
    """
    return slope * temperature + intercept


while True:
    now = datetime.datetime.now()
    pan_temperature = convert(pan.temperature_raw)
    tilt_temperature = convert(tilt.temperature_raw)
    print("{}, {}, {}".format(now, pan_temperature, tilt_temperature))
    with open("/home/idmind/temperature_log.csv", "a") as outfile:
        outfile.write("{}, {}, {}\n".format(now, pan_temperature, tilt_temperature))
    time.sleep(delay)
