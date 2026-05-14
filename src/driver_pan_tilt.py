"""

Driver node.

This node manages the pan tilt servos.

Uses the herkulex library to control the servos.

"""

import time

import herkulex as hx
import middleware as mw


TEMPERATURE_SLOPE = 0.7105
TEMPERATURE_INTERCEPT = -79.47


class DriverPanTilt:
    """
    Hardware driver for the pan and tilt Herkulex servo system.

    Connects to both servos over a serial port and, on each tick, applies
    any pending PID tuning changes, synchronises torque state, issues
    angle commands with dynamically calculated playtimes, and reads back
    current angles and temperatures into middleware. All coordination with
    the rest of the system happens exclusively through the middleware Pan
    and Tilt objects.

    > ## Attributes
    ``pan : mw.Pan`` : Middleware pan state object containing the target angle, PID parameters, torque flags, angle bias, playtime limits, and current sensor readings.
    ``tilt : mw.Tilt`` : Middleware tilt state object with the same structure as ``pan`` but for the tilt axis.
    ``node : mw.Node`` : Middleware node used for shutdown signalling and logging.
    ``servo_pan : hx.servo`` : Herkulex servo handle for the pan axis, created during ``connect()``.
    ``servo_tilt : hx.servo`` : Herkulex servo handle for the tilt axis, created during ``connect()``.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.

        Instantiates the middleware Pan, Tilt, and Node objects. The
        physical servo connection is established separately by calling
        ``connect()``.
        """
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()
        self.node = mw.Node("driver_pan_tilt")

    def connect(self):
        """
        Connect to servos.

        Opens the serial port at ``/dev/ttyAMA0`` at 115200 baud, clears
        any existing Herkulex errors, then binds ``servo_pan`` and
        ``servo_tilt`` handles using the IDs stored in the middleware Pan
        and Tilt objects. Logs each step of the connection sequence and
        waits briefly between stages to allow the hardware to settle.
        """
        pan_id = self.pan.id
        tilt_id = self.tilt.id
        hx.connect("/dev/ttyAMA0", 115200)
        self.node.loginfo("connected to serial port")
        hx.clear_errors()
        time.sleep(1.0)
        self.node.loginfo("errors cleared")
        self.node.loginfo("connecting to pan servo using id %s" % pan_id)
        self.servo_pan = hx.servo(pan_id)
        self.node.loginfo("connected to pan servo")
        self.node.loginfo("connecting to tilt servo using id %s" % tilt_id)
        self.servo_tilt = hx.servo(tilt_id)
        self.node.loginfo("connected to tilt servo")
        time.sleep(1.0)
        self.node.loginfo("connected to pan tilt servos")

    def run(self):
        """
        Main loop.

        Calls ``connect()`` to establish the servo connection, marks both
        axes as ready in middleware, then enters a polling loop that runs
        until a ``hx.HerkulexError`` is raised or the middleware node
        signals shutdown. On each tick the loop performs the following
        steps for both axes:

        - **PID calibration**: compares the requested P and D gains
          against the currently applied values and writes any changed
          gain to the servo hardware.
        - **Torque control**: calls ``torque_on()`` or ``torque_off()``
          whenever the ``enable`` flag diverges from the ``enabled``
          state, then syncs the flag.
        - **Angle command**: if the servo is enabled and the target angle
          has changed, clamps it to ``[min_angle, max_angle]``, computes
          a playtime proportional to the motion range relative to the
          full axis range, adds the axis bias, and issues
          ``set_servo_angle()``.
        - **Angle readback**: reads the current angle from each servo,
          subtracts the axis bias, and writes the result to
          ``current_angle`` in middleware.
        - **Temperature readback**: reads the raw temperature register,
          stores it in ``temperature_raw``, and applies the linear
          calibration (``TEMPERATURE_SLOPE`` and ``TEMPERATURE_INTERCEPT``)
          to compute the value written to ``temperature``.

        ``IndexError`` exceptions from the Herkulex library are caught
        per tick, errors are cleared on the hardware, and the loop
        continues. A ``hx.HerkulexError`` terminates the loop and is
        printed. The node is shut down and the serial port is closed in
        the ``finally`` block regardless of the exit path.
        """
        try:
            self.error_count = 0
            self.connected = False
            self.connect()
            self.pan.ready = True
            self.tilt.ready = True
            while not self.node.is_shutdown():
                try:
                    # calibrate pid
                    if self.pan.pid_p != self.pan.pid_current_p:
                        self.servo_pan.set_position_p(self.pan.pid_p)
                        time.sleep(0.2)
                        self.pan.pid_current_p = self.pan.pid_p
                    if self.pan.pid_d != self.pan.pid_current_d:
                        self.servo_pan.set_position_d(self.pan.pid_d)
                        time.sleep(0.2)
                        self.pan.pid_current_d = self.pan.pid_d
                    if self.tilt.pid_p != self.tilt.pid_current_p:
                        self.servo_tilt.set_position_p(self.tilt.pid_p)
                        time.sleep(0.2)
                        self.tilt.pid_current_p = self.tilt.pid_p
                    if self.tilt.pid_d != self.tilt.pid_current_d:
                        self.servo_tilt.set_position_d(self.tilt.pid_d)
                        time.sleep(0.2)
                        self.tilt.pid_current_d = self.tilt.pid_d
                    # torque
                    if self.pan.enable and not self.pan.enabled:
                        self.servo_pan.torque_on()
                        time.sleep(0.2)
                        self.pan.enabled = True
                    elif not self.pan.enable and self.pan.enabled:
                        self.servo_pan.torque_off()
                        time.sleep(0.2)
                        self.pan.enabled = False
                    if self.tilt.enable and not self.tilt.enabled:
                        self.servo_tilt.torque_on()
                        time.sleep(0.2)
                        self.tilt.enabled = True
                    elif not self.tilt.enable and self.tilt.enabled:
                        self.servo_tilt.torque_off()
                        time.sleep(0.2)
                        self.tilt.enabled = False
                    # set pan angle
                    if self.pan.enabled and self.pan.angle_ref != self.pan.angle:
                        self.pan.angle_ref = self.pan.angle
                        angle = max(
                            self.pan.min_angle, min(self.pan.max_angle, self.pan.angle)
                        )
                        # calculate playtime based on motion range.
                        motion_range = abs(self.pan.current_angle - angle)
                        max_motion_range = abs(self.pan.max_angle - self.pan.min_angle)
                        motion_range_percent = motion_range / max_motion_range
                        playtime = int(
                            self.pan.min_playtime
                            + (self.pan.max_playtime - self.pan.min_playtime)
                            * motion_range_percent
                        )
                        # self.node.loginfo("setting pan angle to %s with playtime %s" % (angle, playtime))
                        angle += self.pan.angle_bias
                        self.servo_pan.set_servo_angle(angle, playtime, 0)
                        time.sleep(0.2)
                        # self.node.loginfo("pan angle set")
                    # set tilt angle
                    if self.tilt.enabled and self.tilt.angle_ref != self.tilt.angle:
                        self.tilt.angle_ref = self.tilt.angle
                        angle = max(
                            self.tilt.min_angle,
                            min(self.tilt.max_angle, self.tilt.angle),
                        )
                        # calculate playtime based on motion range.
                        motion_range = abs(self.tilt.current_angle - angle)
                        max_motion_range = abs(
                            self.tilt.max_angle - self.tilt.min_angle
                        )
                        motion_range_percent = motion_range / max_motion_range
                        playtime = int(
                            self.tilt.min_playtime
                            + (self.tilt.max_playtime - self.tilt.min_playtime)
                            * motion_range_percent
                        )
                        # self.node.loginfo("setting tilt angle to %s with playtime %s" % (angle, playtime))
                        angle += self.tilt.angle_bias
                        self.servo_tilt.set_servo_angle(angle, playtime, 0)
                        time.sleep(0.2)
                        # self.node.loginfo("tilt angle set")
                    # update current angles
                    self.pan.current_angle = (
                        self.servo_pan.get_servo_angle() - self.pan.angle_bias
                    )
                    time.sleep(0.2)
                    self.tilt.current_angle = (
                        self.servo_tilt.get_servo_angle() - self.tilt.angle_bias
                    )
                    time.sleep(0.2)
                    # update current temperature
                    pan_temperature_raw = self.servo_pan.get_servo_temperature()
                    self.pan.temperature_raw = pan_temperature_raw
                    self.pan.temperature = (
                        TEMPERATURE_SLOPE * pan_temperature_raw + TEMPERATURE_INTERCEPT
                    )
                    time.sleep(0.2)
                    tilt_temperature_raw = self.servo_tilt.get_servo_temperature()
                    self.tilt.temperature_raw = tilt_temperature_raw
                    self.tilt.temperature = (
                        TEMPERATURE_SLOPE * tilt_temperature_raw + TEMPERATURE_INTERCEPT
                    )
                    time.sleep(0.2)
                except IndexError:
                    hx.clear_errors()
                    time.sleep(0.1)
        except hx.HerkulexError as e:
            print(f"herkulex error: {e}")
        finally:
            time.sleep(1.0)
            self.node.shutdown()
            hx.close()


if __name__ == "__main__":
    node = DriverPanTilt()
    node.run()
