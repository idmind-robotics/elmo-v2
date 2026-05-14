"""

Tool node.

Robot API server.

This module exposes a REST API used to monitor and control the robot,
including motors, LEDs, audio, onboard display, behaviours and power state.

"""
import time
import threading
import socket
import json
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
import logging

logging.getLogger("werkzeug").setLevel(logging.ERROR)

import middleware as mw


SERVER_PORT = 8001


app = Flask(
    __name__,
    static_url_path="",
)


class Robot:
    """
    Middleware abstraction for robot control and monitoring.

    Provides helper methods to update middleware values and expose robot
    state through the HTTP API.

    > ## Attributes

    ``mw_battery : mw.Battery`` : Middleware battery interface.

    ``mw_pan : mw.Pan`` : Middleware pan motor interface.

    ``mw_tilt : mw.Tilt`` : Middleware tilt motor interface.

    ``mw_touch_sensors : mw.TouchSensors`` : Middleware touch sensor interface.

    ``mw_server : mw.Server`` : Middleware server interface.

    ``mw_leds : mw.Leds`` : Middleware LED controller.

    ``mw_onboard : mw.Onboard`` : Middleware onboard display controller.

    ``mw_speakers : mw.Speakers`` : Middleware speakers controller.

    ``mw_microphone : mw.Microphone`` : Middleware microphone controller.

    ``mw_power : mw.Power`` : Middleware power controller.

    ``mw_behaviours : mw.Behaviours`` : Middleware behaviour configuration.

    > ## Functions
    """
    mw_battery = mw.Battery()
    mw_pan = mw.Pan()
    mw_tilt = mw.Tilt()
    mw_touch_sensors = mw.TouchSensors()
    mw_server = mw.Server()
    mw_leds = mw.Leds()
    mw_onboard = mw.Onboard()
    mw_speakers = mw.Speakers()
    mw_microphone = mw.Microphone()
    mw_power = mw.Power()
    mw_behaviours = mw.Behaviours()

    def __init__(self):
        """
        Initialize robot state values from middleware.

        Returns
        -------
        None
        """
        self.battery = self.mw_battery.voltage
        self.battery_percentage = self.mw_battery.percentage
        self.pan = self.mw_pan.current_angle
        self.tilt = self.mw_tilt.current_angle
        self.pan_min = self.mw_pan.min_angle
        self.pan_max = self.mw_pan.max_angle
        self.tilt_min = self.mw_tilt.min_angle
        self.tilt_max = self.mw_tilt.max_angle
        self.pan_torque = self.mw_pan.enabled
        self.tilt_torque = self.mw_tilt.enabled
        self.pan_temperature = self.mw_pan.temperature
        self.tilt_temperature = self.mw_tilt.temperature
        self.touch_chest = self.mw_touch_sensors.touch_chest
        self.touch_head_n = self.mw_touch_sensors.touch_head_0
        self.touch_head_s = self.mw_touch_sensors.touch_head_1
        self.touch_head_e = self.mw_touch_sensors.touch_head_2
        self.touch_head_w = self.mw_touch_sensors.touch_head_3
        self.touch_head_c = self.mw_touch_sensors.touch_head_3
        self.touch_chest_value = self.mw_touch_sensors.chest_raw
        self.touch_head_n_value = self.mw_touch_sensors.head_0_raw
        self.touch_head_s_value = self.mw_touch_sensors.head_1_raw
        self.touch_head_e_value = self.mw_touch_sensors.head_2_raw
        self.touch_head_w_value = self.mw_touch_sensors.head_3_raw
        self.touch_head_c_value = self.mw_touch_sensors.head_4_raw
        self.behaviour_look_around = self.mw_behaviours.look_around
        self.behaviour_blush = self.mw_behaviours.blush
        self.video_list = self.mw_server.get_video_list()
        self.sound_list = self.mw_server.get_sound_list()
        self.image_list = self.mw_server.get_image_list()
        self.icon_list = self.mw_server.get_icon_list()
        self.volume = self.mw_speakers.volume
        self.multimedia_port = self.mw_server.http_port
        self.microphone_is_recording = self.mw_microphone.is_recording
        self.recognized_speech = self.mw_onboard.speech

    def update(self):
        """
        Refresh all robot state values from middleware.

        Returns
        -------
        None
        """
        self.battery = self.mw_battery.voltage
        self.battery_percentage = self.mw_battery.percentage
        self.pan = self.mw_pan.current_angle
        self.tilt = self.mw_tilt.current_angle
        self.pan_min = self.mw_pan.min_angle
        self.pan_max = self.mw_pan.max_angle
        self.tilt_min = self.mw_tilt.min_angle
        self.tilt_max = self.mw_tilt.max_angle
        self.pan_torque = self.mw_pan.enabled
        self.tilt_torque = self.mw_tilt.enabled
        self.pan_temperature = self.mw_pan.temperature
        self.tilt_temperature = self.mw_tilt.temperature
        self.touch_chest = self.mw_touch_sensors.touch_chest
        self.touch_head_n = self.mw_touch_sensors.touch_head_0
        self.touch_head_s = self.mw_touch_sensors.touch_head_1
        self.touch_head_e = self.mw_touch_sensors.touch_head_2
        self.touch_head_w = self.mw_touch_sensors.touch_head_3
        self.touch_head_c = self.mw_touch_sensors.touch_head_4
        self.touch_chest_value = self.mw_touch_sensors.chest_raw
        self.touch_head_n_value = self.mw_touch_sensors.head_0_raw
        self.touch_head_s_value = self.mw_touch_sensors.head_1_raw
        self.touch_head_e_value = self.mw_touch_sensors.head_2_raw
        self.touch_head_w_value = self.mw_touch_sensors.head_3_raw
        self.touch_head_c_value = self.mw_touch_sensors.head_4_raw
        self.behaviour_look_around = self.mw_behaviours.look_around
        self.behaviour_blush = self.mw_behaviours.blush
        self.video_list = self.mw_server.get_video_list()
        self.sound_list = self.mw_server.get_sound_list()
        self.image_list = self.mw_server.get_image_list()
        self.icon_list = self.mw_server.get_icon_list()
        self.volume = self.mw_speakers.volume
        self.multimedia_port = self.mw_server.http_port
        self.microphone_is_recording = self.mw_microphone.is_recording
        self.recognized_speech = self.mw_onboard.speech
        self.video_list = self.mw_server.get_video_list()
        self.sound_list = self.mw_server.get_sound_list()
        self.image_list = self.mw_server.get_image_list()
        self.icon_list = self.mw_server.get_icon_list()

    def enable_look_around(self, control):
        """
        Enable or disable the look around behaviour.

        Parameters
        ----------
        control : bool
            Behaviour enable state.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_behaviours.look_around = bool(control)
        return True, "OK"

    def enable_blush(self, control):
        """
        Enable or disable the blush behaviour.

        Parameters
        ----------
        control : bool
            Behaviour enable state.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_behaviours.blush = bool(control)
        return True, "OK"

    def enable_change_mode(self, control):
        """
        Enable or disable the change mode behaviour.

        Parameters
        ----------
        control : bool
            Behaviour enable state.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_behaviours.change_mode = bool(control)
        return True, "OK"

    def set_pan_torque(self, control):
        """
        Enable or disable pan motor torque.

        Parameters
        ----------
        control : bool
            Torque enable state.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_pan.enable = bool(control)
        return True, "OK"

    def set_pan(self, angle):
        """
        Set the pan motor target angle.

        Parameters
        ----------
        angle : float
            Desired pan angle.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_pan.angle = angle
        return True, "OK"

    def set_tilt_torque(self, control):
        """
        Enable or disable tilt motor torque.

        Parameters
        ----------
        control : bool
            Torque enable state.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_tilt.enable = bool(control)
        return True, "OK"

    def set_tilt(self, angle):
        """
        Set the tilt motor target angle.

        Parameters
        ----------
        angle : float
            Desired tilt angle.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_tilt.angle = angle
        return True, "OK"

    def update_motor_limits(self, pan_min, pan_max, tilt_min, tilt_max):
        """
        Update motor angle limits.

        Parameters
        ----------
        pan_min : float
            Minimum pan angle.

        pan_max : float
            Maximum pan angle.

        tilt_min : float
            Minimum tilt angle.

        tilt_max : float
            Maximum tilt angle.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_pan.min_angle = pan_min
        self.mw_pan.max_angle = pan_max
        self.mw_tilt.min_angle = tilt_min
        self.mw_tilt.max_angle = tilt_max
        return True, "OK"

    def play_sound(self, name):
        """
        Play a sound resource.

        Parameters
        ----------
        name : str
            Sound filename.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        url = self.mw_server.url_for_sound(name)
        self.mw_speakers.url = url
        return True, "OK"

    def pause_audio(self):
        """
        Stop audio playback.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_speakers.url = None
        return True, "OK"

    def set_volume(self, v):
        """
        Set speaker output volume.

        Parameters
        ----------
        v : float
            Volume level.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_speakers.volume = v
        return True, "OK"

    def start_recording(self):
        """
        Start microphone recording.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_microphone.record = True
        return True, "OK"

    def stop_recording(self):
        """
        Stop microphone recording.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_microphone.record = False
        return True, "OK"

    def update_leds(self, colors):
        """
        Update LED colors.

        Parameters
        ----------
        colors : list
            List of RGB color tuples.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        if len(colors) != self.mw_leds.number:
            return False, "Need %d colors, got %d" % (self.mw_leds.number, len(colors))
        correct_size = all([len(c) == 3 for c in colors])
        if not correct_size:
            return False, "Colors must be 3-tuples"
        self.mw_leds.colors = colors
        return True, "OK"

    def update_leds_icon(self, name):
        """
        Load LED colors from an icon resource.

        Parameters
        ----------
        name : str
            Icon filename.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        url = self.mw_server.url_for_icon(name)
        self.mw_leds.load_from_url(url)
        return True, "OK"

    def set_screen(self, image=None, video=None, text=None, url=None):
        """
        Update onboard screen content.

        Parameters
        ----------
        image : str, optional
            Image filename.

        video : str, optional
            Video filename.

        text : str, optional
            Text to display.

        url : str, optional
            URL to open on the onboard display.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        if image != "":
            url = self.mw_server.url_for_image(image)
            self.mw_onboard.image = url
        else:
            self.mw_onboard.image = None
        if video != "":
            url = self.mw_server.url_for_video(video)
            self.mw_onboard.video = url
        else:
            self.mw_onboard.video = None
        if text != "":
            self.mw_onboard.text = text
        else:
            self.mw_onboard.text = None
        if url != "":
            self.mw_onboard.url = url
        else:
            self.mw_onboard.url = None
        return True, "OK"

    def reboot(self):
        """
        Trigger robot reboot.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_power.reboot = True
        return True, "OK"

    def shutdown(self):
        """
        Trigger robot shutdown.

        Returns
        -------
        tuple
            Success flag and status message.
        """
        self.mw_power.shutdown = True
        return True, "OK"


robot = Robot()


@app.route("/status")
def status():
    """
    Return the current robot status.

    Returns
    -------
    flask.wrappers.Response
        JSON response containing robot state data.
    """
    try:
        robot.update()
    except Exception as e:
        print("Error updating status: " + str(e))
    return jsonify(robot.__dict__)


@app.route("/command", methods=["POST"])
def command():
    """
    Execute robot control commands.

    Supported operations include behaviour control, motor movement,
    audio playback, LED updates, onboard display updates and power control.

    Returns
    -------
    flask.wrappers.Response
        JSON response containing operation status.
    """
    try:
        req = request.json
        # print(req)
        success = True
        message = "OK"
        op = req["op"]
        if op == "enable_behaviour":
            name = req["name"]
            control = req["control"]
            if name == "look_around":
                success, message = robot.enable_look_around(control)
            if name == "blush":
                success, message = robot.enable_blush(control)
            if name == "change_mode":
                success, message = robot.enable_change_mode(control)
            return jsonify({"success": True, "message": "OK"})
        elif op == "set_pan_torque":
            control = req["control"]
            success, message = robot.set_pan_torque(control)
        elif op == "set_pan":
            angle = req["angle"]
            success, message = robot.set_pan(angle)
        elif op == "set_tilt_torque":
            control = req["control"]
            success, message = robot.set_tilt_torque(control)
        elif op == "set_tilt":
            angle = req["angle"]
            success, message = robot.set_tilt(angle)
        elif op == "play_sound":
            name = req["name"]
            success, message = robot.play_sound(name)
        elif op == "pause_audio":
            success, message = robot.pause_audio()
        elif op == "set_volume":
            volume = req["volume"]
            success, message = robot.set_volume(volume)
        elif op == "start_recording":
            success, message = robot.start_recording()
        elif op == "stop_recording":
            success, message = robot.stop_recording()
        elif op == "set_screen":
            image = req["image"]
            video = req["video"]
            text = req["text"]
            url = req["url"]
            success, message = robot.set_screen(image, video, text, url)
        elif op == "update_leds":
            colors = req["colors"]
            success, message = robot.update_leds(colors)
        elif op == "update_leds_icon":
            name = req["name"]
            success, message = robot.update_leds_icon(name)
        elif op == "reboot":
            success, message = robot.reboot()
        elif op == "shutdown":
            success, message = robot.shutdown()
        elif op == "manual_prompt":
            robot.mw_onboard.speech = "Can you tell me the capital of spain?"
        else:
            return jsonify(
                {"success": False, "message": "%s is not a recognized operation" % op}
            )
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def quick_connect():
    """
    Start UDP discovery service for robot detection.

    Listens for discovery packets and responds with robot connection
    information.

    Returns
    -------
    None
    """
    mw_robot = mw.Robot()
    mw_server = mw.Server()
    udp_ip = "0.0.0.0"
    udp_port = mw_server.udp_port
    response_str = "iamarobot;elmo;%s;%d" % (mw_robot.name, mw_server.api_port)
    response = response_str.encode()

    running = False
    while not running:
        try:
            time.sleep(0.1)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((udp_ip, udp_port))
            running = True
        except Exception:
            pass
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if b"ruarobot" in data:
                sock.sendto(response, addr)
        except Exception:
            pass


if __name__ == "__main__":
    udp_server_thread = threading.Thread(target=quick_connect)
    udp_server_thread.daemon = True
    udp_server_thread.start()
    server_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=SERVER_PORT)
    )
    server_thread.daemon = True
    server_thread.start()
    node = mw.Node("robot_api")
    try:
        while not node.is_shutdown():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        node.logerror(e)
    finally:
        node.shutdown()
