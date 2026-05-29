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
    return redis.Redis()


connection = get_connection()


def set_key(key, value):
    connection.set(key, json.dumps(value))


def get_key(key):
    return json.loads(connection.get(key))


def has_key(key):
    return connection.exists(key) != 0


def has_any_key(prefix):
    return len(connection.keys(prefix + "*")) > 0


def delete_all():
    connection.flushall()


def get_all(*prefixes):
    for k in connection.keys():
        if len(prefixes) == 0 or any([k.decode().startswith(p) for p in prefixes]):
            print(f"{k.decode()}:\t{get_key(k.decode())}")


def has_any(key):
    return len(connection.keys(key)) > 0


class Node:
    INFO = 0
    WARN = 1
    ERROR = 2

    def __init__(self, name, log_level=INFO):
        self.name = name
        set_key("node_" + name, os.getpid())
        set_key(name + "_is_shutdown", False)
        print(f"{name}: running")
        self.log_level = log_level

    def loginfo(self, message):
        if self.log_level <= Node.INFO:
            print(f"[INFO]\t/{self.name}: {message}")

    def logerror(self, message):
        if self.log_level <= Node.WARN:
            print(f"[WARN]\t/{self.name}: {message}")

    def logwarn(self, message):
        if self.log_level <= Node.ERROR:
            print(f"[ERROR]\t/{self.name}: {message}")

    def set_log_level(self, level):
        self.log_level = level

    def is_shutdown(self):
        return get_key(self.name + "_is_shutdown")

    def shutdown(self):
        connection.delete("node_" + self.name)
        connection.delete(self.name + "_is_shutdown")
        print(f"{self.name}: shutdown")


class NodeManager:
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
    prefix = ""
    fields = {}

    def __init__(self):
        for k in self.fields:
            setattr(self.__class__, k, property(self.getter(k), self.setter(k)))

    def getter(self, key):
        def do_get(self):
            if not has_key(f"{self.prefix}_{key}"):
                set_key(f"{self.prefix}_{key}", self.fields[key])
            return get_key(f"{self.prefix}_{key}")

        return do_get

    def setter(self, key):
        def do_set(self, value):
            set_key(f"{self.prefix}_{key}", value)

        return do_set


class Robot(DBEntry):
    prefix = "robot"
    fields = {
        "name": "Elmo V2",
    }


class Camera(DBEntry):
    prefix = "camera"
    fields = {
        "url": "http://elmo2:8080/stream.mjpg",
        "take_picture": False,
        "taking_picture": False,
        "error": None,
        "face_detected": False,
        "face_x": 0.0,
        "face_y": 0.0,
    }


class Microphone(DBEntry):
    prefix = "microphone"
    fields = {"is_recording": False, "record": False}


class Battery(DBEntry):
    prefix = "battery"
    fields = {
        "ready": False,
        "raw": 0,
        "voltage": 0.0,
        "i2c_address": 0x48,
        "percentage": 100.0,
    }


class Leds(DBEntry):
    prefix = "leds"
    fields = {
        "ready": False,
        "number": 169,
        "colors": [[0, 0, 0]] * 169,
        "brightness": 0.3,
        "url": None,
    }

    def set_colors(self, colors):
        # check if colors has the right size
        if len(colors) != self.number:
            self.logerror("colors has the wrong size")
            return
        # check if colors has the right format
        if not all([isinstance(c, list) and len(c) == 3 for c in colors]):
            self.logerror("colors has the wrong format")
            return
        # check if colors has the right values
        if not all(
            [0 <= c[0] <= 255 and 0 <= c[1] <= 255 and 0 <= c[2] <= 255 for c in colors]
        ):
            self.logerror("colors has the wrong values")
            return
        self.colors = colors

    def load_from_url(self, url):
        self.url = url
        if url is None:
            return
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
                pass
            #   final_color = [[0, 0, 0]] * self.number
            #                frames.append(final_color)
            # schedule the publishing of the messages
            time_between_frames = image.info["duration"] / 1000.0
            for i in range(len(frames)):

                def set_colors(colors):
                    def update_colors():
                        self.colors = colors

                    return update_colors

                t = threading.Timer(time_between_frames * i, set_colors(frames[i]))
                t.start()

            # clear the leds after the gif ends
            def clear_leds():
                self.colors = [[0, 0, 0]] * self.number
                self.url = None

            t = threading.Timer(time_between_frames * len(frames), clear_leds)
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
        self.url = None


class GPIO(DBEntry):
    prefix = "gpio"
    fields = {
        "ready": False,
        "button_pin": 17,
        #'shutdown_pin': 27,
        #'stay_enable_pin': 4,
        "audio_pin": 22,
        "monitor_pin": 10,
        "audio_enabled": False,
        "monitor_enabled": False,
        "audio_enable": True,
        "monitor_enable": True,
        "button_pressed": False,
        "robot_shutdown": False,
    }


class Speakers(DBEntry):
    prefix = "speakers"
    fields = {
        "ready": False,
        "volume": 70,
        "url": None,
        "playing": None,
    }


class TouchSensors(DBEntry):
    prefix = "touch_sensors"
    fields = {
        "ready": False,
        "touch_chest": False,
        "touch_head_0": False,
        "touch_head_1": False,
        "touch_head_2": False,
        "touch_head_3": False,
        "touch_head_4": False,
        "chest_raw": 0,
        "head_0_raw": 0,
        "head_1_raw": 0,
        "head_2_raw": 0,
        "head_3_raw": 0,
        "head_4_raw": 0,
    }

    def head_touch(self):
        return any(
            (
                self.touch_head_0,
                self.touch_head_1,
                self.touch_head_2,
                self.touch_head_3,
                self.touch_head_4,
            )
        )


class Pan(DBEntry):
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
        "temperature_raw": 0,
        "temperature": 0,
        "hot_temperature": 60,
        "cool_temperature": 40,
        "angle_bias": 0,
    }


class Tilt(DBEntry):
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
        "temperature_raw": 0,
        "temperature": 0,
        "hot_temperature": 60,
        "cool_temperature": 40,
        "angle_bias": 0,
    }


class Onboard(DBEntry):
    prefix = "onboard"
    fields = {
        "ready": False,
        "image": "images/normal.png",
        "text": None,
        "url": None,
        "video": None,
        "speech": None,
        "log": None,
    }


class Speech(DBEntry):
    prefix = "speech"
    fields = {
        "ready": False,
        "language": "en",
        # "language": "pt",
        "say": None,
        "saying": None,
    }


class Conversation(DBEntry):
    prefix = "conversation"
    fields = {
        "ready": False,
        "context": None,
        "api_key": None,
        "max_tokens": 100,
        "temperature": 0.1,
        "model": None,
    }


class Akinator(DBEntry):
    prefix = "akinator"
    fields = {"running": False, "guessed": False, "error": None}


class Server(DBEntry):
    prefix = "server"
    fields = {
        "ready": False,
        "http_port": 8000,
        "udp_port": 5000,
        "api_port": 8001,
        "static_path": "static",
    }

    def url_for_image(self, name):
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/images/" + name

    def url_for_sound(self, name):
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/sounds/" + name

    def url_for_icon(self, name):
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/icons/" + name

    def url_for_video(self, name):
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/videos/" + name

    def url_for_camera(self):
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return ""

    def get_image_list(self):
        try:
            url = self.url_for_image("")[:-1]
            response = requests.get(url)
            return response.json()
        except Exception:
            return []

    def get_sound_list(self):
        try:
            url = self.url_for_sound("")[:-1]
            response = requests.get(url)
            return response.json()
        except Exception:
            return []

    def get_icon_list(self):
        try:
            url = self.url_for_icon("")[:-1]
            response = requests.get(url)
            return response.json()
        except Exception:
            return []

    def get_video_list(self):
        try:
            url = self.url_for_video("")[:-1]
            response = requests.get(url)
            return response.json()
        except Exception:
            return []


class Power(DBEntry):
    prefix = "power"
    fields = {"reboot": False, "shutdown": False, "gpio_shutdown": True}


class Behaviours(DBEntry):
    prefix = "behaviour"
    fields = {
        "look_around": False,
        "test_motors": False,
        "blush": True,
        "conversation": False,
        "photographer": False,
        "akinator": False,
        "wifi_connect": False,
    }

    def list_behaviours(self):
        return self.fields.keys()


class Printer(DBEntry):
    prefix = "printer"
    fields = {
        "wifi": "INSTAX-03222647",
        "connected": False,
    }


def test1():
    print("listing nodes")
    manager = NodeManager()
    print(manager.list_nodes())
    print("creating node")
    # node = Node("test")
    print("node created")
    print("listing nodes")
    print(manager.list_nodes())
    print("is alive?")
    print(manager.is_alive("test"))
    print("shutting down")
    manager.shutdown("test")
    print("is alive?")
    print(manager.is_alive("test"))
    print("force shutting down")
    manager.force_shutdown("test")
    print("is alive?")
    print(manager.is_alive("test"))


if __name__ == "__main__":
    usage = "usage: python3 middleware.py <list|killall|shutdown|force_shutdown|state|monitor|reset>"
    if len(sys.argv) == 1:
        print(usage)
        sys.exit(1)
    manager = NodeManager()
    if sys.argv[1] == "list":
        print(json.dumps(sorted(manager.list_nodes()), indent=2))
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
    elif sys.argv[1] == "set":
        if len(sys.argv) != 5:
            print("usage: python3 middleware.py set <type> <key> <value>")
            sys.exit(1)
        if sys.argv[2] == "int":
            set_key(sys.argv[3], int(sys.argv[4]))
        elif sys.argv[2] == "float":
            set_key(sys.argv[3], float(sys.argv[4]))
        elif sys.argv[2] == "str":
            set_key(sys.argv[3], sys.argv[4])
        elif sys.argv[2] == "bool":
            set_key(sys.argv[3], sys.argv[4] in ("True", "true"))
        else:
            print("unknown type")
            sys.exit(1)
    elif sys.argv[1] == "get":
        if len(sys.argv) != 3:
            print("usage: python3 middleware.py get <key>")
            sys.exit(1)
        print(get_key(sys.argv[2]))
    else:
        print(usage)
        sys.exit(1)
