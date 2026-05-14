"""
Behaviour node.

While enabled, the behaviour makes the head look around, systematically.
"""

import time
import random
import middleware as mw


MAX_RANGE = 30.0
SLEEP = 3.0
TILT_MIN = -15.0
TILT_MAX = 15.0
PAN_MIN = -40.0
PAN_MAX = 40.0
ANGLES = [
    [0.0, 0.0],
    [PAN_MIN, TILT_MIN],
    [PAN_MIN, TILT_MAX],
    [PAN_MAX, TILT_MIN],
    [PAN_MAX, TILT_MAX],
]


class BehaviourTestMotors:
    """
    Middleware behaviour that exercises the pan and tilt servos through a fixed
    sequence of positions for diagnostic purposes.
    Waits for both servos to be ready, then cycles through the predefined ANGLES
    list (centre, four corners) at a fixed interval while the test_motors flag is set.
    Enables torque when the flag is set and disables it (returning to centre) when cleared.

    > ## Attributes

    ``node : mw.Node`` : Middleware node used for logging and shutdown signalling.

    ``behaviours : mw.Behaviours`` : Middleware behaviour configuration flags, used to read the test_motors toggle.

    ``pan : mw.Pan`` : Middleware pan servo controller for horizontal head movement.
    
    ``tilt : mw.Tilt`` : Middleware tilt servo controller for vertical head movement.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware and initialise the node, behaviour flags, and servo controllers.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.node = mw.Node("behaviour_test_motors")
        self.behaviours = mw.Behaviours()
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()

    def run(self):
        """
        Main behaviour loop.

        Blocks until both pan and tilt servos report ready, then polls at ~10 Hz.
        On each tick:
        - If test_motors transitions from False to True, enables torque on both servos.
        - If test_motors transitions from True to False, resets angles to 0°, waits
          2 s for the head to return to centre, then disables torque.
        - While enabled and servos are powered, commands the next [pan, tilt] pair
          from the ANGLES sequence (wrapping around with modulo), increments the
          index, then sleeps for SLEEP seconds before the next move.

        Shuts down the middleware node on exit (including on KeyboardInterrupt or
        any other exception).

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        try:
            self.node.loginfo("waiting for pan and tilt to be ready")
            # wait for pan and tilt to be ready
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.pan.ready and self.tilt.ready:
                    break
            self.node.loginfo("starting behaviour")
            enabled = False
            next_angle_ref_idx = 0
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.behaviours.test_motors and not enabled:
                    # behaviour was enabled, enable torque
                    print("enabling torque")
                    enabled = True
                    self.pan.enable = True
                    self.tilt.enable = True
                if not self.behaviours.test_motors and enabled:
                    # behaviour was disabled, disable torque and reset angles
                    print("disabling torque")
                    enabled = False
                    self.pan.angle = 0.0
                    self.tilt.angle = 0.0
                    time.sleep(2.0)
                    self.pan.enable = False
                    self.tilt.enable = False
                if enabled and self.pan.enabled and self.tilt.enabled:
                    # behaviour is enabled, move systematically
                    print("mobializing")
                    pan, tilt = ANGLES[next_angle_ref_idx]
                    self.pan.angle = pan
                    self.tilt.angle = tilt
                    next_angle_ref_idx = (next_angle_ref_idx + 1) % len(ANGLES)
                    time.sleep(SLEEP)

        finally:
            self.node.shutdown()


if __name__ == "__main__":
    behaviour = BehaviourTestMotors()
    behaviour.run()
