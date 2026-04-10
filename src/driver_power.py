"""

Driver node.

This node manages the power.

Control it by setting the reboot or shutdown flags of the middleware.Power class.

Also reacts to the GPIO shutdown event.

"""

import os
import time

import middleware as mw


class DriverPower:
    """
    Middleware driver node for handling system reboot and shutdown commands.

    Attributes
    ----------
    power : mw.Power
        Middleware power state object with `reboot` and `shutdown` flags.
    gpio : mw.GPIO
        Middleware GPIO object for shutdown signal propagation (currently unused).
    node : mw.Node
        Middleware node used for shutdown detection and logging.
    """
    def __init__(self):
        """
        Initialize middleware objects for power and node control.
        """
        self.power = mw.Power()
        self.gpio = mw.GPIO()
        self.node = mw.Node("driver_power")

    def reboot(self):
        """
        Perform a system reboot.

        Side effects
        ------------
        - Logs "Rebooting".
        - Executes `sudo /usr/sbin/reboot`.
        """
        self.node.loginfo("Rebooting")
        os.system("sudo /usr/sbin/reboot")

    def shutdown(self):
        """
        Perform a system shutdown.

        Side effects
        ------------
        - Logs "Shutting down".
        - Executes `sudo /usr/sbin/shutdown -h now`.
        """
        self.node.loginfo("Shutting down")
        os.system("sudo /usr/sbin/shutdown -h now")

    def run(self):
        """
        Main loop that monitors middleware power flags and triggers actions.

        Behavior
        --------
        - Polls every 0.1 seconds.
        - If `power.reboot` is True, calls `reboot()` and exits loop.
        - If `power.shutdown` is True, calls `shutdown()` and exits loop.
        - Catches `KeyboardInterrupt` and all exceptions; logs errors.
        - Shuts down middleware node on exit.

        Returns
        -------
        None
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

        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.node.logerror(e)
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    driver = DriverPower()
    driver.run()
