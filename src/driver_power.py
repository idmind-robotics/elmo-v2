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
    Hardware driver for system power management.

    Monitors middleware flags and issues the appropriate OS-level reboot
    or shutdown command when requested. Intended to be the single point
    of authority for all power-state transitions so that no other node
    needs direct OS access.

    > ## Attributes
    ``power : mw.Power`` : Middleware power state object whose ``reboot`` and ``shutdown`` flags trigger the corresponding OS commands.
    ``gpio : mw.GPIO`` : Middleware GPIO state object monitored for hardware-level shutdown signals.
    ``node : mw.Node`` : Middleware node used for shutdown signalling and logging.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.

        Instantiates the middleware power, GPIO, and node objects used
        throughout the driver's lifetime.
        """
        self.power = mw.Power()
        self.gpio = mw.GPIO()
        self.node = mw.Node("driver_power")

    def reboot(self):
        """
        Issue a system reboot command.

        Logs the action and invokes ``sudo reboot`` via the OS shell.
        """
        self.node.loginfo("Rebooting")
        os.system("sudo /usr/sbin/reboot")

    def shutdown(self):
        """
        Issue a system shutdown command.

        Logs the action and invokes ``sudo shutdown -h now`` via the OS
        shell to perform an immediate halt.
        """
        self.node.loginfo("Shutting down")
        os.system("sudo /usr/sbin/shutdown -h now")

    def run(self):
        """
        Main loop.

        Polls the middleware power flags at 10 Hz until a shutdown or
        reboot is requested, or until the middleware node signals
        shutdown. On each tick:

        - If ``power.reboot`` is set, calls ``reboot()`` and exits the loop.
        - If ``power.shutdown`` is set, calls ``shutdown()`` and exits the loop.

        Unexpected exceptions are logged via ``node.logerror``. The node
        is shut down cleanly in the ``finally`` block regardless of the
        exit path.
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
