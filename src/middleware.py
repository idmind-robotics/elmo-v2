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
    Establish and return a Redis connection.

    Returns
    -------
    redis.Redis
        Redis connection instance.
    """
    return redis.Redis()


connection = get_connection()


def set_key(key, value):
    """
    Store a key-value pair in Redis, serializing the value as JSON.

    Parameters
    ----------
    key : str
        The Redis key under which the value will be stored.
    value : any
        The Python object to store (will be JSON serialized).
    """
    connection.set(key, json.dumps(value))


def get_key(key):
    """
    Retrieve a value from Redis by key and deserialize it from JSON.

    Parameters
    ----------
    key : str
        The Redis key to retrieve.

    Returns
    -------
    any
        The Python object stored in Redis under the given key.
    """
    return json.loads(connection.get(key))


def has_key(key):
    """
    Check if a key exists in Redis.

    Parameters
    ----------
    key : str
        The Redis key to check.

    Returns
    -------
    bool
        True if the key exists, False otherwise.
    """
    return connection.exists(key) != 0


def has_any_key(prefix):
    """
    Check if any Redis keys exist that start with a given prefix.

    Parameters
    ----------
    prefix : str
        The prefix to search for.

    Returns
    -------
    bool
        True if at least one key exists with the prefix, False otherwise.
    """
    return len(connection.keys(prefix + "*")) > 0


def delete_all():
    """
    Delete all keys from the Redis database.
    """
    connection.flushall()


def get_all(*prefixes):
    """
    Print all key-value pairs in Redis, optionally filtered by prefixes.

    Parameters
    ----------
    *prefixes : str
        Optional prefixes to filter which keys are printed.
    """
    for k in connection.keys():
        if len(prefixes) == 0 or any([k.decode().startswith(p) for p in prefixes]):
            print(f"{k.decode()}:\t{get_key(k.decode())}")


def has_any(key):
    """
    Check if any Redis keys match a given pattern.

    Parameters
    ----------
    key : str
        The pattern to match (supports Redis glob-style patterns).

    Returns
    -------
    bool
        True if at least one matching key exists, False otherwise.
    """
    return len(connection.keys(key)) > 0


class Node:
    """
    Represents a node in the system with logging and shutdown management.

    Attributes
    ----------
    name : str
        Name of the node.
    log_level : int
        Current logging level (0=INFO, 1=WARN, 2=ERROR).
    INFO : int
        Constant representing INFO log level.
    WARN : int
        Constant representing WARN log level.
    ERROR : int
        Constant representing ERROR log level.
    """
    INFO = 0
    WARN = 1
    ERROR = 2

    def __init__(self, name, log_level=INFO):
        """
        Initialize a Node instance and register it in Redis.

        Parameters
        ----------
        name : str
            The name of the node.
        log_level : int, optional
            The logging level (default is Node.INFO).
        """
        self.name = name
        set_key("node_" + name, os.getpid())
        set_key(name + "_is_shutdown", False)
        print(f"{name}: running")
        self.log_level = log_level

    def loginfo(self, message):
        """
        Log an INFO-level message if log_level permits.

        Parameters
        ----------
        message : str
            The message to log.
        """
        if self.log_level <= Node.INFO:
            print(f"[INFO]\t/{self.name}: {message}")

    def logerror(self, message):
        """
        Log a WARN-level message if log_level permits.

        Parameters
        ----------
        message : str
            The message to log.
        """
        if self.log_level <= Node.WARN:
            print(f"[WARN]\t/{self.name}: {message}")

    def logwarn(self, message):
        """
        Log an ERROR-level message if log_level permits.

        Parameters
        ----------
        message : str
            The message to log.
        """
        if self.log_level <= Node.ERROR:
            print(f"[ERROR]\t/{self.name}: {message}")

    def set_log_level(self, level):
        """
        Set the node's logging level.

        Parameters
        ----------
        level : int
            The new logging level.
        """
        self.log_level = level

    def is_shutdown(self):
        """
        Check whether the node is marked as shutdown in Redis.

        Returns
        -------
        bool
            True if the node is shutdown, False otherwise.
        """
        return get_key(self.name + "_is_shutdown")

    def shutdown(self):
        """
        Remove the node's keys from Redis and log the shutdown.
        """
        connection.delete("node_" + self.name)
        connection.delete(self.name + "_is_shutdown")
        print(f"{self.name}: shutdown")


class NodeManager:
    """
    Manage multiple Node instances by interacting with Redis and system processes.

    Provides methods to list, query, and control nodes.
    """
    def list_nodes(self):
        """
        List all registered nodes.

        Returns
        -------
        list of str
            Names of all nodes currently registered in Redis.
        """
        return [k.decode()[5:] for k in connection.keys("node_*")]

    def get_pid(self, name):
        """
        Get the process ID (PID) of a node.

        Parameters
        ----------
        name : str
            The name of the node.

        Returns
        -------
        int
            PI
        """
        return get_key("node_" + name)

    def is_running(self, name):
        """
        Check if a process with the node's PID is currently running.

        Parameters
        ----------
        name : str
            Name of the node.

        Returns
        -------
        bool
            True if the process exists, False otherwise.
        """
        pid = self.get_pid(name)
        return psutil.pid_exists(pid)

    def is_alive(self, name):
        """
        Determine if a node is both registered and its process is running.

        Parameters
        ----------
        name : str
            Name of the node.

        Returns
        -------
        bool
            True if the node is alive, False otherwise.
        """
        return name in self.list_nodes() and self.is_running(name)

    def shutdown(self, name):
        """
        Mark a node as shutdown in Redis.

        Parameters
        ----------
        name : str
            Name of the node.
        """
        if self.is_alive(name):
            set_key(name + "_is_shutdown", True)

    def force_shutdown(self, name):
        """
        Forcefully terminate a node's process and remove its Redis keys.

        Parameters
        ----------
        name : str
            Name of the node.
        """
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
    Base class for Redis-backed data objects with automatic property mapping.

    Attributes
    ----------
    prefix : str
        Prefix used in Redis keys for this entry.
    fields : dict
        Dictionary of field names and default values.
    """
    prefix = ""
    fields = {}

    def __init__(self):
        """
        Initialize the DBEntry, creating dynamic properties for each field.
        """
        for k in self.fields:
            setattr(self.__class__, k, property(self.getter(k), self.setter(k)))

    def getter(self, key):
        """
        Create a getter function for a field that retrieves its value from Redis.

        Parameters
        ----------
        key : str
            Name of the field.

        Returns
        -------
        function
            Getter function for the specified field.
        """

        def do_get(self):
            if not has_key(f"{self.prefix}_{key}"):
                set_key(f"{self.prefix}_{key}", self.fields[key])
            return get_key(f"{self.prefix}_{key}")

        return do_get

    def setter(self, key):
        """
        Create a setter function for a field that updates its value in Redis.

        Parameters
        ----------
        key : str
            Name of the field.

        Returns
        -------
        function
            Setter function for the specified field.
        """
        def do_set(self, value):
            set_key(f"{self.prefix}_{key}", value)

        return do_set


class Robot(DBEntry):
    """
    Represents a robot configuration stored in Redis.

    Fields
    ------
    name : str
        Name of the robot (default: "Elmo V2").
    """
    prefix = "robot"
    fields = {
        "name": "Elmo V2",
    }


class Camera(DBEntry):
    """
    Represents a camera module with state stored in Redis.

    Fields
    ------
    url : str
        Stream URL of the camera.
    take_picture : bool
        Indicates whether a picture should be taken.
    taking_picture : bool
        True if currently taking a picture.
    error : any
        Last error encountered by the camera.
    face_detected : bool
        True if a face was detected.
    face_x : float
        X-coordinate of detected face.
    face_y : float
        Y-coordinate of detected face.
    """
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
    """
    Represents a microphone module with recording state stored in Redis.

    Fields
    ------
    is_recording : bool
        True if the microphone is currently recording.
    record : bool
        Flag to start/stop recording.
    """
    prefix = "microphone"
    fields = {"is_recording": False, "record": False}


class Battery(DBEntry):
    """
    Represents battery state and configuration stored in Redis.

    Fields
    ------
    ready : bool
        Indicates if the battery system is initialized.
    raw : int
        Raw sensor reading.
    voltage : float
        Measured voltage.
    i2c_address : int
        I2C address of the battery sensor.
    percentage : float
        Battery charge percentage.
    """
    prefix = "battery"
    fields = {
        "ready": False,
        "raw": 0,
        "voltage": 0.0,
        "i2c_address": 0x48,
        "percentage": 100.0,
    }


class Leds(DBEntry):
    """
    Represents an LED matrix with color and animation control.

    Fields
    ------
    ready : bool
        Indicates if the LED system is initialized.
    number : int
        Total number of LEDs.
    colors : list of list of int
        RGB color values for each LED.
    brightness : float
        Brightness level (0.0 to 1.0).
    url : str or None
        Source URL for image or animation.

    Notes
    -----
    Supports loading static images and GIF animations from URLs.
    GIFs are processed frame-by-frame and scheduled using timers.
    """
    prefix = "leds"
    fields = {
        "ready": False,
        "number": 169,
        "colors": [[0, 0, 0]] * 169,
        "brightness": 0.3,
        "url": None,
    }

    def set_colors(self, colors):
        """
        Set LED colors after validating format and size.

        Parameters
        ----------
        colors : list of list of int
            List of RGB values (0–255) for each LED.

        Notes
        -----
        Validation ensures correct length, structure, and value ranges.
        Invalid input will be ignored.
        """
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
        """
        Load LED colors from an image or GIF URL.

        Parameters
        ----------
        url : str or None
            URL pointing to an image or GIF.

        Notes
        -----
        - GIFs are processed into frames and displayed sequentially.
        - Static images are mapped directly to the LED grid.
        - Uses network requests and may block during download.
        - Schedules updates using threading timers.
        """
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
                final_color = [[0, 0, 0]] * self.number
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
                """
                Reset all LEDs to off state and clear the source URL.
                """
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
    """
    Represents GPIO configuration and state.

    Fields
    ------
    ready : bool
        Indicates if GPIO is initialized.
    button_pin : int
        GPIO pin for button input.
    audio_pin : int
        GPIO pin controlling audio.
    monitor_pin : int
        GPIO pin controlling monitor.
    audio_enabled : bool
        Current audio state.
    monitor_enabled : bool
        Current monitor state.
    audio_enable : bool
        Desired audio state.
    monitor_enable : bool
        Desired monitor state.
    button_pressed : bool
        Indicates if button is pressed.
    robot_shutdown : bool
        Indicates shutdown request from GPIO.
    """
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
    """
    Represents speaker configuration and playback state.

    Fields
    ------
    ready : bool
        Indicates if speakers are initialized.
    volume : int
        Playback volume (0–100).
    url : str or None
        Audio source URL.
    playing : any
        Current playback state or metadata.
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
    Represents touch sensor inputs and raw readings.

    Fields
    ------
    ready : bool
        Indicates if sensors are initialized.
    touch_chest : bool
        Chest touch state.
    touch_head_0..4 : bool
        Head touch sensor states.
    chest_raw : int
        Raw chest sensor value.
    head_0_raw..head_4_raw : int
        Raw head sensor values.
    """
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
    """
    Check if any head touch sensor is active.

    Returns
    -------
    bool
    True if any head sensor is triggered.
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
        "temperature_raw": 0,
        "temperature": 0,
        "hot_temperature": 60,
        "cool_temperature": 40,
        "angle_bias": 0,
    }


class Tilt(DBEntry):
    """
    Represents tilt motor control parameters and state.

    Fields
    ------
    Similar to Pan but configured for tilt movement.
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
        "temperature_raw": 0,
        "temperature": 0,
        "hot_temperature": 60,
        "cool_temperature": 40,
        "angle_bias": 0,
    }


class Onboard(DBEntry):
    """
    Represents onboard display and media state.

    Fields
    ------
    image : str
        Path to displayed image.
    text : str or None
        Display text.
    url : str or None
        External content URL.
    video : str or None
        Video content.
    speech : str or None
        Speech output.
    log : str or None
        Log message.
    """
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
    """
    Represents speech synthesis configuration and state.

    Fields
    ------
    language : str
        Language code for speech.
    say : str or None
        Text to be spoken.
    saying : str or None
        Currently spoken text.
    """
    prefix = "speech"
    fields = {
        "ready": False,
        "language": "en",
        # "language": "pt",
        "say": None,
        "saying": None,
    }


class Conversation(DBEntry):
    """
    Represents conversational AI configuration.

    Fields
    ------
    context : any
        Conversation context.
    api_key : str or None
        API key for external services.
    max_tokens : int
        Maximum tokens for responses.
    temperature : float
        Sampling temperature.
    model : str or None
        Model identifier.
    """

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
    """
    Represents Akinator game state.

    Fields
    ------
    running : bool
        Indicates if the game is active.
    guessed : bool
        Indicates if a guess was made.
    error : any
        Error state.
    """
    prefix = "akinator"
    fields = {"running": False, "guessed": False, "error": None}


class Server(DBEntry):
    """
    Represents server configuration and resource access helpers.

    Fields
    ------
    http_port : int
        HTTP server port.
    udp_port : int
        UDP server port.
    api_port : int
        API server port.
    static_path : str
        Path to static resources.

    Notes
    -----
    URL helper methods block until the server is marked as ready.
    """
    prefix = "server"
    fields = {
        "ready": False,
        "http_port": 8000,
        "udp_port": 5000,
        "api_port": 8001,
        "static_path": "static",
    }

    def url_for_image(self, name):
        """
        Generate URL for an image resource.

        Parameters
        ----------
        name : str
            Image filename.

        Returns
        -------
        str
            Full URL to the image.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/images/" + name

    def url_for_sound(self, name):
        """
        Generate URL for a sound resource.

        Parameters
        ----------
        name : str
            Sound filename.

        Returns
        -------
        str
            Full URL to the sound.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/sounds/" + name

    def url_for_icon(self, name):
        """
        Generate URL for an icon resource.

        Parameters
        ----------
        name : str
            Icon filename.

        Returns
        -------
        str
            Full URL to the icon.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/icons/" + name

    def url_for_video(self, name):
        """
        Generate URL for a video resource.

        Parameters
        ----------
        name : str
            Video filename.

        Returns
        -------
        str
            Full URL to the video.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/videos/" + name

    def url_for_camera(self):
        """
        Generate URL for camera stream.

        Returns
        -------
        str
            Camera URL (currently empty).
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return ""

    def get_image_list(self):
        """
        Retrieve list of available images from the server.

        Returns
        -------
        list
            List of image metadata or empty list on failure.
        """
        try:
            url = self.url_for_image("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []

    def get_sound_list(self):
        """
        Retrieve list of available sounds.

        Returns
        -------
        list
            List of sound metadata or empty list on failure.
        """
        try:
            url = self.url_for_sound("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []

    def get_icon_list(self):
        """
        Retrieve list of available icons.

        Returns
        -------
        list
            List of icon metadata or empty list on failure.
        """
        try:
            url = self.url_for_icon("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []

    def get_video_list(self):
        """
        Retrieve list of available videos.

        Returns
        -------
        list
            List of video metadata or empty list on failure.
        """
        try:
            url = self.url_for_video("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []


class Power(DBEntry):
    """
    Represents power control state.

    Fields
    ------
    reboot : bool
        Indicates reboot request.
    shutdown : bool
        Indicates shutdown request.
    gpio_shutdown : bool
        Indicates GPIO-triggered shutdown behavior.
    """
    prefix = "power"
    fields = {"reboot": False, "shutdown": False, "gpio_shutdown": True}


class Behaviours(DBEntry):
    """
    Represents enabled/disabled robot behaviours.

    Fields
    ------
    Various boolean flags controlling behavior modes.
    """
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
        """
        List available behaviour names.

        Returns
        -------
        dict_keys
            Keys representing behaviour names.
        """
        return self.fields.keys()


class Printer(DBEntry):
    """
    Represents printer configuration.

    Fields
    ------
    wifi : str
        Printer Wi-Fi SSID.
    connected : bool
        Connection status.
    """
    prefix = "printer"
    fields = {
        "wifi": "INSTAX-03222647",
        "connected": False,
    }


def test1():
    """
    Demonstration function for NodeManager and Node lifecycle.

    Performs node creation, status checks, shutdown, and forced shutdown.
    """
    print("listing nodes")
    manager = NodeManager()
    print(manager.list_nodes())
    print("creating node")
    node = Node("test")
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
