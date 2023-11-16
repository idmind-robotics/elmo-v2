#! /usr/bin/env python


"""

Touch sensor calibration.

This module calculates if a touch event has occurred, based on the raw values of the touch sensors.

The raw values are compared to a moving average of the raw values.

If the raw values are below the moving average, a touch event is triggered.

The moving average is calculated over a window of values.

The window size and sensitivity can be configured.

"""


import numpy as np


import time
import middleware as mw


WINDOW_SIZE = 100


class TouchCalibrator:

    def __init__(self):
        self.windows = {
            "chest": [],
            "head_0": [],
            "head_1": [],
            "head_2": [],
            "head_3": [],
        }
        self.touch_sensors = mw.TouchSensors()
        self.node = mw.Node("touch_calibrator")

    def run(self):
        try:
            self.node.loginfo("waiting for touch sensors to be ready")
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.touch_sensors.ready:
                    break
            self.node.loginfo("calibrating")
            while not self.node.is_shutdown(): 
                time.sleep(0.1)
                chest_raw = self.touch_sensors.chest_raw
                head_0_raw = self.touch_sensors.head_0_raw
                head_1_raw = self.touch_sensors.head_1_raw
                head_2_raw = self.touch_sensors.head_2_raw
                head_3_raw = self.touch_sensors.head_3_raw
                self.windows["chest"].append(chest_raw)
                self.windows["head_0"].append(head_0_raw)
                self.windows["head_1"].append(head_1_raw)
                self.windows["head_2"].append(head_2_raw)
                self.windows["head_3"].append(head_3_raw)
                if len(self.windows["chest"]) > WINDOW_SIZE:
                    self.node.loginfo("calibration complete")
                    break
            while not self.node.is_shutdown():
                time.sleep(0.1)
                # get values
                chest_raw = self.touch_sensors.chest_raw
                head_0_raw = self.touch_sensors.head_0_raw
                head_1_raw = self.touch_sensors.head_1_raw
                head_2_raw = self.touch_sensors.head_2_raw
                head_3_raw = self.touch_sensors.head_3_raw
                # add to buffers
                self.windows["chest"].append(chest_raw)
                self.windows["head_0"].append(head_0_raw)
                self.windows["head_1"].append(head_1_raw)
                self.windows["head_2"].append(head_2_raw)
                self.windows["head_3"].append(head_3_raw)
                # remove old values
                self.windows["chest"] = self.windows["chest"][-WINDOW_SIZE:]
                self.windows["head_0"] = self.windows["head_0"][-WINDOW_SIZE:]
                self.windows["head_1"] = self.windows["head_1"][-WINDOW_SIZE:]
                self.windows["head_2"] = self.windows["head_2"][-WINDOW_SIZE:]
                self.windows["head_3"] = self.windows["head_3"][-WINDOW_SIZE:]
                # calculate bounds
                sensitivity = self.touch_sensors.sensitivity
                chest_mean = np.mean(self.windows["chest"])
                chest_upper, chest_lower = chest_mean + sensitivity, chest_mean - sensitivity
                head_0_mean = np.mean(self.windows["head_0"])
                head_0_upper, head_0_lower = head_0_mean + sensitivity, head_0_mean - sensitivity
                head_1_mean = np.mean(self.windows["head_1"])
                head_1_upper, head_1_lower = head_1_mean + sensitivity, head_1_mean - sensitivity
                head_2_mean = np.mean(self.windows["head_2"])
                head_2_upper, head_2_lower = head_2_mean + sensitivity, head_2_mean - sensitivity
                head_3_mean = np.mean(self.windows["head_3"])
                head_3_upper, head_3_lower = head_3_mean + sensitivity, head_3_mean - sensitivity
                # check if latest values are below lower bounds
                chest_last_3 = self.windows["chest"][-3:]
                head_0_last_3 = self.windows["head_0"][-3:]
                head_1_last_3 = self.windows["head_1"][-3:]
                head_2_last_3 = self.windows["head_2"][-3:]
                head_3_last_3 = self.windows["head_3"][-3:]
                touch_chest = all([v < chest_lower for v in chest_last_3])
                touch_head_0 = all([v < head_0_lower for v in head_0_last_3])
                touch_head_1 = all([v < head_1_lower for v in head_1_last_3])
                touch_head_2 = all([v < head_2_lower for v in head_2_last_3])
                touch_head_3 = all([v < head_3_lower for v in head_3_last_3])
                # update db
                self.touch_sensors.touch_chest = touch_chest
                self.touch_sensors.touch_head_0 = touch_head_0
                self.touch_sensors.touch_head_1 = touch_head_1
                self.touch_sensors.touch_head_2 = touch_head_2
                self.touch_sensors.touch_head_3 = touch_head_3
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = TouchCalibrator()
    node.run()
