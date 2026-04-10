#! /usr/bin/env python


"""

This node disables the look_around behaviour, if the motors temperatures exceed their max.

"""

import time
import middleware as mw


class MotorTemperatureWatchdog:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.node = mw.Node("motor_temperature_watchdog")
        self.behaviours = mw.Behaviours()
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()

    def run(self):
        """
        Main loop.
        """
        was_hot = False
        was_cool = True
        behaviour_was_enabled = False
        try:
            self.node.loginfo("waiting for pan and tilt to be ready")
            # wait for pan and tilt to be ready
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.pan.ready and self.tilt.ready:
                    break
            self.node.loginfo("watching temperatures")
            while not self.node.is_shutdown():
                time.sleep(1.0)
                pan_hot_temperature = self.pan.hot_temperature
                tilt_hot_temperature = self.tilt.hot_temperature
                pan_cool_temperature = self.pan.cool_temperature
                tilt_cool_temperature = self.tilt.cool_temperature

                pan_temperature = self.pan.temperature
                tilt_temperature = self.tilt.temperature
                behaviour_enabled = self.behaviours.look_around
                hot = (
                    pan_temperature > pan_hot_temperature
                    or tilt_temperature > tilt_hot_temperature
                )
                cool = (
                    pan_temperature < pan_cool_temperature
                    and tilt_temperature < tilt_cool_temperature
                )
                if hot and not was_hot:
                    self.node.logwarn(
                        "motors temperature too high: pan=%f/%f, tilt=%f/%f"
                        % (
                            pan_temperature,
                            pan_hot_temperature,
                            tilt_temperature,
                            tilt_hot_temperature,
                        )
                    )
                    was_hot = True
                    was_cool = False
                    behaviour_was_enabled = behaviour_enabled
                    self.node.logwarn("disabling look_around behaviour")
                    self.behaviours.look_around = False
                if cool and not was_cool:
                    self.node.logwarn(
                        "motors temperature back to normal: pan=%f/%f, tilt=%f/%f"
                        % (
                            pan_temperature,
                            pan_cool_temperature,
                            tilt_temperature,
                            tilt_cool_temperature,
                        )
                    )
                    was_hot = False
                    was_cool = True
                    if behaviour_was_enabled:
                        self.node.logwarn("enabling look_around behaviour")
                        self.behaviours.look_around = True
                    else:
                        self.node.logwarn("look_around behaviour was disabled")

        finally:
            self.node.shutdown()


if __name__ == "__main__":
    node = MotorTemperatureWatchdog()
    node.run()
