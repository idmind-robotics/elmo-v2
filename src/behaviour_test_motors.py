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
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.node = mw.Node("behaviour_test_motors")
        self.behaviours = mw.Behaviours()
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()

    def run(self):
        """
        Main loop.
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
