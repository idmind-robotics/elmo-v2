#! /usr/bin/env python


"""

Driver node.

This node manages the pan tilt servos.

Uses the herkulex library to control the servos.

"""


import time

import herkulex as hx
import middleware as mw


class DriverPanTilt:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()
        self.node = mw.Node("driver_pan_tilt")
    
    def connect(self):
        """
        Connect to servos.
        """
        pan_id = self.pan.id
        tilt_id = self.tilt.id
        hx.connect("/dev/ttyS0", 115200)
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
                        angle = max(self.pan.min_angle, min(self.pan.max_angle, self.pan.angle))
                        # calculate playtime based on motion range.
                        motion_range = abs(self.pan.current_angle - angle)
                        max_motion_range = abs(self.pan.max_angle - self.pan.min_angle)
                        motion_range_percent = motion_range / max_motion_range
                        playtime = int(self.pan.min_playtime + (self.pan.max_playtime - self.pan.min_playtime) * motion_range_percent)
                        # self.node.loginfo("setting pan angle to %s with playtime %s" % (angle, playtime))
                        angle += self.pan.angle_bias
                        self.servo_pan.set_servo_angle(angle, playtime, 0)
                        time.sleep(0.2)
                        # self.node.loginfo("pan angle set")
                    # set tilt angle
                    if self.tilt.enabled and self.tilt.angle_ref != self.tilt.angle:
                        self.tilt.angle_ref = self.tilt.angle
                        angle = max(self.tilt.min_angle, min(self.tilt.max_angle, self.tilt.angle))
                        # calculate playtime based on motion range.
                        motion_range = abs(self.tilt.current_angle - angle)
                        max_motion_range = abs(self.tilt.max_angle - self.tilt.min_angle)
                        motion_range_percent = motion_range / max_motion_range
                        playtime = int(self.tilt.min_playtime + (self.tilt.max_playtime - self.tilt.min_playtime) * motion_range_percent)
                        # self.node.loginfo("setting tilt angle to %s with playtime %s" % (angle, playtime))
                        angle += self.tilt.angle_bias
                        self.servo_tilt.set_servo_angle(angle, playtime, 0)
                        time.sleep(0.2)
                        # self.node.loginfo("tilt angle set")
                    # update current angles
                    self.pan.current_angle = self.servo_pan.get_servo_angle() - self.pan.angle_bias
                    time.sleep(0.2)
                    self.tilt.current_angle = self.servo_tilt.get_servo_angle() - self.tilt.angle_bias
                    time.sleep(0.2)
                    # update current temperature
                    self.pan.temperature = self.servo_pan.get_servo_temperature()
                    time.sleep(0.2)
                    self.tilt.temperature = self.servo_tilt.get_servo_temperature()
                    time.sleep(0.2)
                except IndexError:
                    hx.clear_errors()
                    time.sleep(0.1)
        except hx.HerkulexError as e:
            print(f'herkulex error: {e}')
        finally:
            time.sleep(1.0)
            self.node.shutdown()
            hx.close()


if __name__ == '__main__':
    node = DriverPanTilt()
    node.run()
