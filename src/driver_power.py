#! /usr/bin/env python


"""

Driver node.

This node manages the power.

Control it by setting the reboot or shutdown flags of the middleware.Power class.

Also reacts to the GPIO shutdown event and battery at 0%.

"""


import os
import time

import middleware as mw


class DriverPower:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.power = mw.Power()
        self.gpio = mw.GPIO()
        self.battery = mw.Battery()
        self.node = mw.Node("driver_power")
    
    def reboot(self):
        self.node.loginfo("Rebooting")
        os.system("sudo /usr/sbin/reboot")

    def shutdown(self):
        self.node.loginfo("Shutting down")
        os.system("sudo /usr/sbin/shutdown -h now")

    def run(self):
        """
        Main loop.
        """
        try:
            while not self.node.is_shutdown():
                time.sleep(0.1)
                # reboot flag of the middleware.Power class
                if self.power.reboot:
                    self.reboot()
                    break
                # shutdown flag of the middleware.Power class
                if self.power.shutdown:
                    self.shutdown()
                    break
                # GPIO shutdown event
                if self.power.gpio_shutdown and self.gpio.robot_shutdown:
                    self.shutdown()
                    break
                # battery at 0%
                if self.power.battery_shutdown and self.battery.percentage <= 0:
                    self.shutdown()
                    break
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.node.logerror(e)
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    driver = DriverPower()
    driver.run()
