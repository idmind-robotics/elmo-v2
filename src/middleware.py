#! /usr/bin/env python


"""

Middleware.

This module provides a set of classes to interact with the middleware.

Defines several classes to interact with the underlying redis database.

Classes that extend DBEntry define data that will be stored in the database.

Clients can use these classes to exchange messages between each other.

Additionally, the module defines several tools to manage node processes.

Clients can use the Node class to signal that they are running, and check for shutdown events.

The NodeManager class can be used to list, shutdown or kill all nodes.

When used as a script, the module provides a command line interface to manage nodes.

"""


import redis
import json
import os
import signal
import psutil
import time
import sys
import requests
from io import BytesIO
from PIL import Image
import threading



def get_connection():
    """
    Get a connection to the redis database.
    """
    return redis.Redis()

# global connection
connection = get_connection()


def set_key(key, value):
    """
    Set a key in the redis database.
    """
    connection.set(key, json.dumps(value))

def get_key(key):
    """
    Get a key from the redis database.
    """
    return json.loads(connection.get(key))

def has_key(key):
    """
    Check if a key exists in the redis database.
    """
    return connection.exists(key) != 0

def has_any_key(prefix):
    """
    Check if any key with the given prefix exists in the redis database.
    """
    return len(connection.keys(prefix + "*")) > 0

def delete_all():
    """
    Delete all keys from the redis database.
    """
    connection.flushall()

def get_all(*prefixes):
    """
    Get all keys from the redis database.
    Optionally, filter by prefix.
    """
    for k in sorted(connection.keys()):
        if len(prefixes) == 0 or any([k.decode().startswith(p) for p in prefixes]):
            print(f'{k.decode()}:\t{get_key(k.decode())}')

def has_any(key):
    """
    Check if any key with the given prefix exists in the redis database.
    """
    return len(connection.keys(key)) > 0


class Node:
    """
    Node class.
    Initialize this class to signal node is running.
    Use is_shutdown() to check if node should shutdown.
    Use shutdown() to signal node is shutting down.
    Use loginfo(), logwarn() and logerror() to log messages.
    """

    INFO = 0
    WARN = 1
    ERROR = 2

    def __init__(self, name, log_level=INFO):
        self.name = name
        set_key("node_" + name, os.getpid())
        set_key(name + "_is_shutdown", False)
        print(f'{name}: running')
        self.log_level = log_level

    def loginfo(self, message):
        if self.log_level <= Node.INFO:
            print(f'[INFO]\t/{self.name}: {message}')
    
    def logerror(self, message):
        if self.log_level <= Node.WARN:
            print(f'[WARN]\t/{self.name}: {message}')

    def logwarn(self, message):
        if self.log_level <= Node.ERROR:
            print(f'[ERROR]\t/{self.name}: {message}')
        
    def set_log_level(self, level):
        self.log_level = level

    def is_shutdown(self):
        return get_key(self.name + "_is_shutdown")

    def shutdown(self):
        connection.delete("node_" + self.name)
        connection.delete(self.name + "_is_shutdown")
        print(f'{self.name}: shutdown')


class NodeManager:

    """
    NodeManager class.
    Use this class to list, shutdown or kill all nodes.
    Nodes that hang can be force shutdown.
    """

    def list_nodes(self):
        return [k.decode()[5:] for k in connection.keys("node_*")]
    
    def get_pid(self, name):
        return get_key("node_" + name)

    def is_running(self, name):        
        pid = self.get_pid(name)
        return psutil.pid_exists(pid)

    def is_alive(self, name):
        return name in self.list_nodes() and self.is_running(name)

    def shutdown(self, name):
        if self.is_alive(name):
            set_key(name + "_is_shutdown", True)
    
    def force_shutdown(self, name):
        if name in self.list_nodes():
            if self.is_running(name):
                pid = self.get_pid(name)
                os.kill(pid, signal.SIGKILL)
                time.sleep(1.0)
            if not self.is_running(name):
                connection.delete("node_" + name)
                connection.delete(name + "_is_shutdown")


class DBEntry:

    """
    DBEntry class.
    Extend this class to define data that will be stored in the database.
    The fields attribute defines the data that will be stored.
    The prefix attribute defines the prefix that will be used to store the data.
    """

    prefix = ''
    fields = {}
    def __init__(self):
        for k in self.fields:
            setattr(self.__class__, k, property(self.getter(k), self.setter(k)))
    
    def getter(self, key):
        def do_get(self):
            if not has_key(f'{self.prefix}_{key}'):
                set_key(f'{self.prefix}_{key}', self.fields[key])
            return get_key(f'{self.prefix}_{key}')
        return do_get
    
    def setter(self, key):
        def do_set(self, value):
            set_key(f'{self.prefix}_{key}', value)
        return do_set


class Robot(DBEntry):
    """
    Database entry.
    General information about the robot.
    """
    prefix = "robot"
    fields = {
        "name": "Elmo V2",
    }


class Camera(DBEntry):
    """
    Database entry.
    Camera information.
    """
    prefix = "camera"
    fields = {
        "url": "http://elmo2:8080/stream.mjpg",
    }


class Microphone(DBEntry):
    """
    Database entry.
    Microphone information.
    Set record to True to start recording.
    Set record to False to stop recording.
    Check is_recording to see if recording is in progress.
    """
    prefix = "microphone"
    fields = {
        "is_recording": False,
        "record": False
    }


class Battery(DBEntry):
    """
    Database entry.
    Battery information.
    Check ready to see if battery driver is ready.
    Check raw to see the raw AD value.
    Check voltage to see the voltage.
    Driver will connect to the battery at address defined by i2c_address.
    """
    prefix = "battery"
    fields = {
        'ready': False,
        'raw': 0,
        'voltage': 0.0,
        'i2c_address': 0x48,
        'ad_at_13v': 619.517,
        'ad_at_16v': 765.021,
        'percentage': 100.0
    }


class Leds(DBEntry):
    """
    Database entry.
    LED information.
    Set colors to a list of 3-element tuples to set the colors.
    The led matrix has 169 leds, arranged in a 13x13 grid.
    Set brightness to a value between 0.0 and 1.0 to set the brightness.
    """
    prefix = "leds"
    fields = {
        'ready': False,
        'number': 169,
        'colors': [[0, 0, 0]] * 169,
        'brightness': 0.3
    }

    def load_from_url(self, url):
        # gif
        if ".gif" in url:
            response = requests.get(url)
            img = BytesIO(response.content)
            image = Image.open(img)
            # create image buffer
            frames = []
            try:
                while 1:
                    image.seek(image.tell() + 1)
                    colors = []
                    for row in range(13):
                        for col in range(13):
                            im = image.convert("RGB")
                            color = im.getpixel((12 - col, row))[0:3]
                            colors.append(color)
                    frames.append(colors)
            except EOFError:
                final_color = [[0, 0, 0]] * self.number
                frames.append(final_color)
            # schedule the publishing of the messages
            time_between_frames = image.info["duration"] / 1000.0
            for i in range(len(frames)):
                def set_colors(colors):
                    def update_colors():
                        self.colors = colors
                    return update_colors
                t = threading.Timer(time_between_frames * i, set_colors(frames[i]))
                t.start()
        else:
            colors = []
            response = requests.get(url)
            img = BytesIO(response.content)
            image = Image.open(img)
            for row in range(13):
                for col in range(13):
                    # color = image.getpixel((col, 12 - row))
                    color = image.getpixel((12 - col, row))[0:3]
                    colors.append(color)
            self.colors = colors
    
    def clear(self):
        self.colors = [[0, 0, 0]] * self.number



class GPIO(DBEntry):
    """
    Database entry.
    GPIO information.
    Set audio_enable to True to enable audio power.
    Set audio_enable to False to disable audio power.
    Set monitor_enable to True to enable monitor power.
    Set monitor_enable to False to disable monitor power.
    Check audio_enabled to see if audio power is enabled.
    Check monitor_enabled to see if monitor power is enabled.
    Check button_pressed to see if the button is pressed.
    Check robot_shutdown to see if the robot should shutdown.
    """
    prefix = "gpio"
    fields = {
        'ready': False,
        'button_pin': 17,
        'shutdown_pin': 27,
        'stay_enable_pin': 4,
        'audio_pin': 22,
        'monitor_pin': 10,
        'audio_enabled': False,
        'monitor_enabled': False,
        'audio_enable': True,
        'monitor_enable': True,
        'button_pressed': False,
        'robot_shutdown': False,
    }


class Speakers(DBEntry):
    """
    Database entry.
    Speaker information.
    Set url to a url to play a sound.
    Set volume to a value between 0 and 100 to set the volume.
    Check playing to see if a sound is playing.
    """
    prefix = "speakers"
    fields = {
        "ready": False,
        "volume": 70,
        "url": None,
        "playing": None,
    }


class TouchSensors(DBEntry):
    """
    Database entry.
    Touch sensor information.
    Check ready to see if touch sensor driver is ready.
    Check touch_chest to see if the chest is touched.
    Check touch_head_0 to see if the head is touched.
    Check touch_head_1 to see if the head is touched.
    Check touch_head_2 to see if the head is touched.
    Check touch_head_3 to see if the head is touched.
    Check chest_raw to see the raw AD value.
    Check head_0_raw to see the raw AD value.
    Check head_1_raw to see the raw AD value.
    Check head_2_raw to see the raw AD value.
    Check head_3_raw to see the raw AD value.
    """
    prefix = "touch_sensors"
    fields = {
        "ready": False,
        "touch_chest": False,
        "touch_head_0": False,
        "touch_head_1": False,
        "touch_head_2": False,
        "touch_head_3": False,
        "chest_raw": 0,
        "head_0_raw": 0,
        "head_1_raw": 0,
        "head_2_raw": 0,
        "head_3_raw": 0,
        "sensitivity": 5,
    }

    def head_touch(self):
        """
        Check if any head sensor is touched.
        """
        return any((
            self.touch_head_0,
            self.touch_head_1,
            self.touch_head_2,
            self.touch_head_3,
        ))


class Pan(DBEntry):
    """
    Database entry.
    Pan servo information.
    Check ready to see if pan driver is ready.
    Check angle to see the current angle.
    Set angle to a value between -40 and 40 to set the angle.
    Set enable to True to enable torque.
    Set enable to False to disable torque.
    Check enabled to see if torque is enabled.
    Set pid_p to a value between 0 and 255 to set the proportional gain.
    Set pid_d to a value between 0 and 255 to set the derivative gain.
    Check temperature to see the temperature.
    """
    prefix = "pan"
    fields = {
        "ready": False,
        "id": 3,
        "angle": 0,
        "current_angle": 0,
        "angle_ref": None,
        "enable": False,
        "enabled": False,
        "pid_p": 150,
        "pid_current_p": 0,
        "pid_d": 100,
        "pid_current_d": 0,
        "max_angle": 40,
        "min_angle": -40,
        "min_playtime": 100,
        "max_playtime": 200,
        "temperature": 0,
        "angle_bias": 12.0
    }


class Tilt(DBEntry):
    """
    Database entry.
    Tilt servo information.
    Check ready to see if tilt driver is ready.
    Check angle to see the current angle.
    Set angle to a value between -15 and 15 to set the angle.
    Set enable to True to enable torque.
    Set enable to False to disable torque.
    Check enabled to see if torque is enabled.
    Set pid_p to a value between 0 and 255 to set the proportional gain.
    Set pid_d to a value between 0 and 255 to set the derivative gain.
    Check temperature to see the temperature.
    """
    prefix = "tilt"
    fields = {
        "ready": False,
        "id": 4,
        "angle": 0,
        "current_angle": 0,
        "angle_ref": None,
        "enable": False,
        "enabled": False,
        "pid_p": 140,
        "pid_current_p": 0,
        "pid_d": 100,
        "pid_current_d": 0,
        "max_angle": 15,
        "min_angle": -15,
        "min_playtime": 100,
        "max_playtime": 200,
        "temperature": 0,
        "angle_bias": 2.3
    }


class Onboard(DBEntry):
    """
    Database entry.
    Onboard information.
    Check ready to see if onboard driver is ready.
    Set image to a url to display an image.
    Set text to a string to display text.
    Set url to a url to open a url.
    Set video to a url to play a video.
    Check speech to see if speech is being recognized. 
    """
    prefix = "onboard"
    fields = {
        "ready": False,
        "image": "images/normal.png",
        "text": None,
        "url": None,
        "video": None,
        "speech": None,
    }


class Speech(DBEntry):
    """
    Database entry.
    Speech information.
    Check ready to see if speech driver is ready.
    Set language to a language code to set the language.
    Set say to a string to say something.
    Check saying to see what is being said.
    """
    prefix = "speech"
    fields = {
        "ready": False,
        "language": "en",
        "say": None,
        "saying": None,
    }


class Server(DBEntry):
    """
    Database entry.
    Server information.
    Configure the http server port, udp server port and api server port.
    Configure the path to static resources, served by the http server.
    """
    prefix = "server"
    fields = {
        "ready": False,
        "http_port": 8000,
        "udp_port": 5000,
        "api_port": 8001,
        "static_path": "static",
    }

    # def wait_for_ready(self):
    #     while not self.ready:
    #         time.sleep(0.1)
    def wait_for_ready(self):
        while True:
            try:
                requests.get("http://elmo:8000/")
                break
            except Exception:
                time.sleep(0.5)


    def url_for_image(self, name):
        return "http://elmo:8000/images/" + name

    def url_for_sound(self, name):
        return "http://elmo:8000/sounds/" + name
    
    def url_for_icon(self, name):
        return "http://elmo:8000/icons/" + name
    
    def url_for_video(self, name):
        return "http://elmo:8000/videos/" + name
    
    def url_for_camera(self):
        return ""
    
    def get_image_list(self):
        try:
            url = self.url_for_image("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []
    
    def get_sound_list(self):
        try:
            url = self.url_for_sound("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []
    
    def get_icon_list(self):
        try:
            url = self.url_for_icon("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []
    
    def get_video_list(self):
        try:
            url = self.url_for_video("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []


class Power(DBEntry):
    """
    Database entry.
    Power information.
    Set reboot to True to reboot the robot.
    Set shutdown to True to shutdown the robot.
    Set gpio_shutdown to True to shutdown the robot when the GPIO shutdown pin is activated.
    """
    prefix = "power"
    fields = {
        "reboot": False,
        "shutdown": False,
        "gpio_shutdown": True,
        "battery_shutdown": True,
    }


class Behaviours(DBEntry):
    """
    Database entry.
    Behaviour information.
    Set look_around to True to enable look around behaviour.
    Set blush to True to enable blush behaviour.
    Set change_mode to True to enable change mode behaviour.
    """
    prefix = "behaviour"
    fields = {
        "look_around": False,
        "blush": True,
        "change_mode": True,
    }

    def list_behaviours(self):
        return self.fields.keys()


if __name__ == '__main__':
    usage = "usage: python3 middleware.py <list|killall|shutdown|force_shutdown|state|monitor|reset>"
    if len(sys.argv) == 1:
        print(usage)
        sys.exit(1)
    manager = NodeManager()    
    if sys.argv[1] == "list":
        node_list = manager.list_nodes()
        print(json.dumps(sorted(node_list), indent=2))
    elif sys.argv[1] == "killall":
        for name in manager.list_nodes():
            manager.shutdown(name)
    elif sys.argv[1] == "shutdown":
        if len(sys.argv) != 3:
            print("usage: python3 middleware.py shutdown <node_name>")
            sys.exit(1)
        manager.shutdown(sys.argv[2])
    elif sys.argv[1] == "force_shutdown":
        if len(sys.argv) != 3:
            print("usage: python3 middleware.py force_shutdown <node_name>")
            sys.exit(1)
        manager.force_shutdown(sys.argv[2])
    elif sys.argv[1] == "state":
        get_all()
    elif sys.argv[1] == "monitor":
        try:
            while True:
                print("---")
                get_all(*sys.argv[2:])
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    elif sys.argv[1] == "reset":
        delete_all()
    else:
        print(usage)
        sys.exit(1)
    

