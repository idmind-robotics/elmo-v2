"""

Behaviour node.

While enabled, the behaviour makes the head look around, randomly.

"""

import time
import random
import middleware as mw


MAX_RANGE = 30.0
MIN_SLEEP = 2.0
MAX_SLEEP = 4.0


class BehaviourLookAround:
    """
    Middleware behaviour that randomly moves the robot's head while active.
    Waits for pan and tilt servos to be ready before entering the main loop.
    Enables torque when the look_around flag is set, and disables it (returning
    the head to centre) when the flag is cleared.

    > ## Attributes

    ``node : mw.Node`` : Middleware node used for logging and shutdown signalling.

    ``behaviours : mw.Behaviours`` : Middleware behaviour configuration flags, used to read the look_around toggle.

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
        self.node = mw.Node("behaviour_look_around")
        self.behaviours = mw.Behaviours()
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()

    def run(self):
        """
        Main behaviour loop.

        Blocks until both pan and tilt servos report ready, then polls at ~10 Hz.
        On each tick:
        - If look_around transitions from False to True, enables torque on both servos.
        - If look_around transitions from True to False, resets angles to 0°, waits
          2 s for the head to return to centre, then disables torque.
        - While enabled and servos are powered, picks a random pan angle within
          ±MAX_RANGE degrees of the current position (clamped to hardware limits),
          does the same for tilt, commands both servos, then sleeps for a random
          interval between MIN_SLEEP and MAX_SLEEP seconds.

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
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.behaviours.look_around and not enabled:
                    # behaviour was enabled, enable torque
                    enabled = True
                    self.pan.enable = True
                    self.tilt.enable = True
                if not self.behaviours.look_around and enabled:
                    # behaviour was disabled, disable torque and reset angles
                    enabled = False
                    self.pan.angle = 0.0
                    self.tilt.angle = 0.0
                    time.sleep(2.0)
                    self.pan.enable = False
                    self.tilt.enable = False
                if enabled and self.pan.enabled and self.tilt.enabled:
                    # behaviour is enabled, move randomly
                    current_pan = self.pan.angle
                    pan_angle = random.uniform(
                        current_pan - MAX_RANGE, current_pan + MAX_RANGE
                    )
                    pan_angle = max(
                        self.pan.min_angle, min(self.pan.max_angle, pan_angle)
                    )
                    self.pan.angle = pan_angle
                    current_tilt = self.tilt.angle
                    tilt_angle = random.uniform(
                        current_tilt - MAX_RANGE, current_tilt + MAX_RANGE
                    )
                    tilt_angle = max(
                        self.tilt.min_angle, min(self.tilt.max_angle, tilt_angle)
                    )
                    self.tilt.angle = tilt_angle
                    time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    behaviour = BehaviourLookAround()
    behaviour.run()
