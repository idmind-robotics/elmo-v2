#! /usr/bin/env python


"""

This module logs the battery voltage to a csv file.

"""


import time
import datetime


import middleware as mw


battery = mw.Battery()

outfile = open('/home/idmind/battery_log.csv', 'w')
outfile.write('Time, Battery\n')
outfile.close()

delay = 60.0 * 1.0 # 1 minutes


while True:
    now = datetime.datetime.now()
    voltage = battery.voltage
    print('{}, {}'.format(now, voltage))
    with open('/home/idmind/battery_log.csv', 'a') as outfile:
        outfile.write('{}, {}\n'.format(now, voltage))
    time.sleep(delay)