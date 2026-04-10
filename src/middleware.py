"""

Middleware.

Central Redis-backed state layer shared between all driver and behaviour nodes.

Provides key/value helpers, node lifecycle management, and DBEntry classes
that map Python properties directly to Redis keys. Also contains drawing
primitives and layout utilities used by the LED display.

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
    Create and return a Redis connection on localhost.

    Returns
    -------
    redis.Redis
        Connected Redis client.
    """
    return redis.Redis()


connection = get_connection()


def set_key(key, value):
    """
    Serialize and store a value in Redis.

    Parameters
    ----------
    key : str
        Redis key name.
    value : any
        JSON-serializable value to store.
    """
    connection.set(key, json.dumps(value))


def get_key(key):
    """
    Retrieve and deserialize a value from Redis.

    Parameters
    ----------
    key : str
        Redis key name.

    Returns
    -------
    any
        Deserialized value.
    """
    return json.loads(connection.get(key))


def has_key(key):
    """
    Check whether a key exists in Redis.

    Parameters
    ----------
    key : str
        Redis key name.

    Returns
    -------
    bool
        True if the key exists.
    """
    return connection.exists(key) != 0


def has_any_key(prefix):
    """
    Check whether any key with the given prefix exists in Redis.

    Parameters
    ----------
    prefix : str
        Key prefix to search for.

    Returns
    -------
    bool
        True if at least one matching key exists.
    """
    return len(connection.keys(prefix + "*")) > 0


def delete_all():
    """
    Flush all keys from the Redis database.
    """
    connection.flushall()


def get_all(*prefixes):
    """
    Print all Redis keys and their values, optionally filtered by prefix.

    Parameters
    ----------
    *prefixes : str
        Optional list of prefixes to filter keys. If empty, prints all keys.
    """
    for k in connection.keys():
        if len(prefixes) == 0 or any([k.decode().startswith(p) for p in prefixes]):
            print(f"{k.decode()}:\t{get_key(k.decode())}")


def has_any(key):
    """
    Check whether any key matches the given pattern.

    Parameters
    ----------
    key : str
        Redis key pattern.

    Returns
    -------
    bool
        True if at least one matching key exists.
    """
    return len(connection.keys(key)) > 0


# Display assets for LED drawing (digits, letters, icons).
# Loaded once at import time and shared across all Leds instances.
try:
    with open("/home/idmind/elmo-v2/src/static/icons/display_assets.json") as _display_f:
        _DISPLAY_ASSETS = json.load(_display_f)
except Exception:
    _DISPLAY_ASSETS = {"digits": {}, "letters": {}, "weather_icons": {}}


class Node:
    """
    Middleware node lifecycle and logging helper.

    Registers the process PID in Redis on init and cleans up on shutdown.
    Other nodes and the NodeManager can use this to track running processes.

    Attributes
    ----------
    name : str
        Unique node name used as the Redis key prefix.
    log_level : int
        Minimum log level for output (INFO=0, WARN=1, ERROR=2).
    """

    INFO = 0
    WARN = 1
    ERROR = 2

    def __init__(self, name, log_level=INFO):
        """
        Register the node in Redis and set its initial shutdown flag.

        Parameters
        ----------
        name : str
            Unique node name.
        log_level : int
            Minimum log level for output.
        """
        self.name = name
        set_key("node_" + name, os.getpid())
        set_key(name + "_is_shutdown", False)
        print(f"{name}: running")
        self.log_level = log_level

    def loginfo(self, message):
        """
        Log an informational message if log level allows.

        Parameters
        ----------
        message : str
            Message to print.
        """
        if self.log_level <= Node.INFO:
            print(f"[INFO]\t/{self.name}: {message}")

    def logerror(self, message):
        """
        Log a warning message if log level allows.

        Parameters
        ----------
        message : str
            Message to print.
        """
        if self.log_level <= Node.WARN:
            print(f"[WARN]\t/{self.name}: {message}")

    def logwarn(self, message):
        """
        Log an error message if log level allows.

        Parameters
        ----------
        message : str
            Message to print.
        """
        if self.log_level <= Node.ERROR:
            print(f"[ERROR]\t/{self.name}: {message}")

    def set_log_level(self, level):
        """
        Update the active log level.

        Parameters
        ----------
        level : int
            New log level (Node.INFO, Node.WARN, or Node.ERROR).
        """
        self.log_level = level

    def is_shutdown(self):
        """
        Check whether a shutdown has been requested for this node.

        Returns
        -------
        bool
            True if the shutdown flag is set in Redis.
        """
        return get_key(self.name + "_is_shutdown")

    def shutdown(self):
        """
        Remove this node's entries from Redis.
        """
        connection.delete("node_" + self.name)
        connection.delete(self.name + "_is_shutdown")
        print(f"{self.name}: shutdown")


class NodeManager:
    """
    Utility for inspecting and managing running middleware nodes.
    """

    def list_nodes(self):
        """
        List all currently registered node names.

        Returns
        -------
        list[str]
            Node names derived from Redis "node_*" keys.
        """
        return [k.decode()[5:] for k in connection.keys("node_*")]

    def get_pid(self, name):
        """
        Retrieve the PID of a registered node.

        Parameters
        ----------
        name : str
            Node name.

        Returns
        -------
        int
            Process ID.
        """
        return get_key("node_" + name)

    def is_running(self, name):
        """
        Check whether the node's process is still alive.

        Parameters
        ----------
        name : str
            Node name.

        Returns
        -------
        bool
            True if the PID exists in the process table.
        """
        pid = self.get_pid(name)
        return psutil.pid_exists(pid)

    def is_alive(self, name):
        """
        Check whether a node is registered and its process is running.

        Parameters
        ----------
        name : str
            Node name.

        Returns
        -------
        bool
            True if the node is both registered and running.
        """
        return name in self.list_nodes() and self.is_running(name)

    def shutdown(self, name):
        """
        Request a graceful shutdown by setting the node's shutdown flag.

        Parameters
        ----------
        name : str
            Node name.
        """
        if self.is_alive(name):
            set_key(name + "_is_shutdown", True)

    def force_shutdown(self, name):
        """
        Kill the node's process and remove its Redis entries.

        Parameters
        ----------
        name : str
            Node name.
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
    Base class for Redis-backed state objects.

    Subclasses declare a `prefix` and a `fields` dict of default values.
    On init, each field is exposed as a Python property that reads from
    and writes to Redis automatically.

    Attributes
    ----------
    prefix : str
        Redis key prefix used for all fields (e.g. "leds", "touch_sensors").
    fields : dict
        Map of field name to default value.
    """

    prefix = ""
    fields = {}

    def __init__(self):
        """
        Register all declared fields as Redis-backed properties.
        """
        for k in self.fields:
            setattr(self.__class__, k, property(self.getter(k), self.setter(k)))

    def getter(self, key):
        """
        Return a property getter that reads the field value from Redis.

        Parameters
        ----------
        key : str
            Field name.

        Returns
        -------
        callable
            Getter function for use as a property.
        """
        def do_get(self):
            if not has_key(f"{self.prefix}_{key}"):
                set_key(f"{self.prefix}_{key}", self.fields[key])
            return get_key(f"{self.prefix}_{key}")

        return do_get

    def setter(self, key):
        """
        Return a property setter that writes the field value to Redis.

        Parameters
        ----------
        key : str
            Field name.

        Returns
        -------
        callable
            Setter function for use as a property.
        """
        def do_set(self, value):
            set_key(f"{self.prefix}_{key}", value)

        return do_set


class Robot(DBEntry):
    """
    Redis-backed state for robot identity fields.
    """

    prefix = "robot"
    fields = {
        "name": "Elmo V2",
    }


class Camera(DBEntry):
    """
    Redis-backed state for the camera driver.
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
    Redis-backed state for the microphone driver.
    """

    prefix = "microphone"
    fields = {"is_recording": False, "record": False}


class Battery(DBEntry):
    """
    Redis-backed state for the battery driver.
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
    Redis-backed state for the LED matrix driver.

    Extends DBEntry with drawing primitives, a half-half display layout model,
    direct image loading, and a fade animation request mechanism. Hardware
    writes are always delegated to driver_leds via the shared Redis state.

    Layout model
    ------------
    The 13x13 matrix is divided into two halves for behaviours that follow
    a top/bottom content split:

    - Top half  (rows 0–6,  13x7): primary content, e.g. icon or hours.
    - Bottom half (rows 7–12, 13x6): secondary content, e.g. temperature or minutes.

    Behaviours draw on each half independently using local coordinates,
    then call merge_halves() to produce the final display image.

    Attributes
    ----------
    WIDTH : int
        Full matrix width in pixels (13).
    HEIGHT : int
        Full matrix height in pixels (13).
    TOP_HEIGHT : int
        Height of the top display half in pixels (7).
    BOTTOM_HEIGHT : int
        Height of the bottom display half in pixels (6).
    COLOR_OFF : tuple
        RGB color for an off pixel (0, 0, 0).
    COLOR_DEFAULT : tuple
        Default RGB color for digits and letters (120, 160, 255).
    """

    prefix = "leds"

    # --- Display layout constants ---
    WIDTH = 13
    HEIGHT = 13
    TOP_HEIGHT = 7       # rows 0-6: top display half
    BOTTOM_HEIGHT = 6    # rows 7-12: bottom display half
    COLOR_OFF = (0, 0, 0)
    COLOR_DEFAULT = (120, 160, 255)

    fields = {
        "ready": False,
        "number": 169,
        "colors": [[0, 0, 0]] * 169,
        "brightness": 0.3,
        "url": None,
        "fade_target": None,   # list of 169 [r,g,b] colors, set by request_fade
        "fade_steps": 10,      # number of interpolation steps for the fade
        "fade_duration": 1.0,  # total fade duration in seconds
        "fade_active": False,  # set True to trigger fade execution in driver_leds
    }

    def set_colors(self, colors):
        """
        Validate and set the full LED color array in Redis.

        Parameters
        ----------
        colors : list[list[int]]
            List of 169 [R, G, B] values in range 0–255.
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
        Load LED colors from an image or GIF URL into Redis.

        Behavior
        --------
        - For GIFs: schedules each frame as a timed color update, then clears
        the LEDs after the last frame.
        - For static images: reads pixel colors and writes them to `colors`.
        - Pixels are read in column-reversed order to match the physical matrix layout.

        Parameters
        ----------
        url : str
            HTTP URL of a PNG or GIF image hosted by the local server.
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
        """
        Turn off all LEDs and clear the active URL in Redis.
        """
        self.colors = [[0, 0, 0]] * self.number
        self.url = None

    # --- Canvas creation (half-half layout model) ---

    def create_canvas(self):
        """
        Create a blank full 13x13 PIL Image canvas.

        Returns
        -------
        PIL.Image.Image
            Black 13x13 RGB image.
        """
        return Image.new("RGB", (self.WIDTH, self.HEIGHT), self.COLOR_OFF)

    def create_top_canvas(self):
        """
        Create a blank canvas for the top display half (13x7, rows 0–6).

        Returns
        -------
        PIL.Image.Image
            Black 13x7 RGB image.
        """
        return Image.new("RGB", (self.WIDTH, self.TOP_HEIGHT), self.COLOR_OFF)

    def create_bottom_canvas(self):
        """
        Create a blank canvas for the bottom display half (13x6, rows 7–12).

        Returns
        -------
        PIL.Image.Image
            Black 13x6 RGB image.
        """
        return Image.new("RGB", (self.WIDTH, self.BOTTOM_HEIGHT), self.COLOR_OFF)

    def merge_halves(self, top_img, bottom_img):
        """
        Merge a top (13x7) and bottom (13x6) canvas into a full 13x13 canvas.

        Behavior
        --------
        - Top canvas occupies rows 0–6.
        - Bottom canvas occupies rows 7–12.
        - Each half uses local y-coordinates starting at 0.

        Parameters
        ----------
        top_img : PIL.Image.Image
            Canvas for the top half (13x7).
        bottom_img : PIL.Image.Image
            Canvas for the bottom half (13x6).

        Returns
        -------
        PIL.Image.Image
            Merged full 13x13 canvas.
        """
        canvas = self.create_canvas()
        for row in range(self.TOP_HEIGHT):
            for col in range(self.WIDTH):
                canvas.putpixel((col, row), top_img.getpixel((col, row)))
        for row in range(self.BOTTOM_HEIGHT):
            for col in range(self.WIDTH):
                canvas.putpixel((col, self.TOP_HEIGHT + row), bottom_img.getpixel((col, row)))
        return canvas

    # --- Drawing primitives ---

    @staticmethod
    def draw_pattern(img, pattern, ox, oy, color):
        """
        Draw a pattern from display_assets onto a PIL Image canvas.

        Behavior
        --------
        - Iterates over the pattern rows and columns.
        - Skips pixels with value "0".
        - Applies the given color for "1", or a fixed color for named codes.
        - Out-of-bounds pixels are safely ignored.

        Supported color codes
        ---------------------
        1 : default color (passed as argument)
        Y : yellow  (255, 255, 0)
        W : white   (255, 255, 255)
        R : red     (255, 0, 0)
        G : green   (0, 255, 0)
        B : blue    (0, 0, 255)
        P : purple  (255, 0, 255)

        Parameters
        ----------
        img : PIL.Image.Image
            Target canvas to draw on.
        pattern : list[str]
            List of strings where each character is a pixel code.
        ox : int
            X offset for drawing origin.
        oy : int
            Y offset for drawing origin.
        color : tuple
            RGB color used for "1" pixels.
        """
        color_map = {
            "Y": (255, 255, 0),
            "W": (255, 255, 255),
            "R": (255, 0, 0),
            "G": (0, 255, 0),
            "B": (0, 0, 255),
            "P": (255, 0, 255),
        }
        w, h = img.size
        for y, row in enumerate(pattern):
            for x, p in enumerate(row):
                if p != "0":
                    px, py = ox + x, oy + y
                    if 0 <= px < w and 0 <= py < h:
                        c = color if p == "1" else color_map.get(p, color)
                        img.putpixel((px, py), c)

    def draw_digit(self, img, digit, ox, oy, color=None):
        """
        Draw a digit (0–9) onto a PIL Image canvas.

        Parameters
        ----------
        img : PIL.Image.Image
            Target canvas.
        digit : str
            Single character "0"–"9".
        ox : int
            X offset.
        oy : int
            Y offset.
        color : tuple, optional
            RGB color. Defaults to COLOR_DEFAULT.
        """
        self.draw_pattern(img, _DISPLAY_ASSETS["digits"][digit], ox, oy, color or self.COLOR_DEFAULT)

    def draw_letter(self, img, letter, ox, oy, color=None):
        """
        Draw a letter onto a PIL Image canvas.

        Parameters
        ----------
        img : PIL.Image.Image
            Target canvas.
        letter : str
            Single character key present in display_assets["letters"].
        ox : int
            X offset.
        oy : int
            Y offset.
        color : tuple, optional
            RGB color. Defaults to COLOR_DEFAULT.
        """
        self.draw_pattern(img, _DISPLAY_ASSETS["letters"][letter], ox, oy, color or self.COLOR_DEFAULT)

    def draw_icon(self, img, category, key, ox=0, oy=0, color=None):
        """
        Draw an icon from a display_assets category onto a PIL Image canvas.

        Parameters
        ----------
        img : PIL.Image.Image
            Target canvas.
        category : str
            Top-level key in display_assets (e.g. "weather_icons", "pixels").
        key : str
            Icon key within the category (e.g. "rain", "degrees_dot").
        ox : int, optional
            X offset. Defaults to 0.
        oy : int, optional
            Y offset. Defaults to 0.
        color : tuple, optional
            RGB color used for "1" pixels. Defaults to COLOR_DEFAULT.
        """
        self.draw_pattern(img, _DISPLAY_ASSETS[category][key], ox, oy, color or self.COLOR_DEFAULT)

    # --- Direct image loading (no URL or temp files needed) ---

    def load_from_image(self, img):
        """
        Set LED colors directly from a PIL Image, bypassing URL and temp files.

        Behavior
        --------
        - Reads pixels in column-reversed order to match the physical matrix layout.
        - Writes the resulting color list directly to `colors` in Redis.

        Parameters
        ----------
        img : PIL.Image.Image
            Full 13x13 RGB image.
        """
        colors = []
        for row in range(self.HEIGHT):
            for col in range(self.WIDTH):
                color = img.getpixel((12 - col, row))
                colors.append(list(color[:3]))
        self.colors = colors

    # --- Fade request (animation executed by driver_leds) ---

    def request_fade(self, target_img, steps=10, duration=1.0):
        """
        Request a fade from the current LED state to a target PIL Image.

        Behavior
        --------
        - Converts the target image to a color list and stores it in Redis.
        - Sets `fade_active` to True, signalling driver_leds to begin the fade.
        - The actual pixel interpolation and hardware write is performed by
        driver_leds, keeping hardware access within the driver layer.
        - Set `fade_active` to False externally to abort mid-fade.

        Parameters
        ----------
        target_img : PIL.Image.Image
            Full 13x13 image to fade to.
        steps : int
            Number of interpolation steps.
        duration : float
            Total fade duration in seconds.
        """
        target_colors = []
        for row in range(self.HEIGHT):
            for col in range(self.WIDTH):
                color = target_img.getpixel((12 - col, row))
                target_colors.append(list(color[:3]))
        self.fade_target = target_colors
        self.fade_steps = int(steps)
        self.fade_duration = float(duration)
        self.fade_active = True


class GPIO(DBEntry):
    """
    Redis-backed state for the GPIO driver.
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
    Redis-backed state for the speaker driver.
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
    Redis-backed state for the touch sensor driver.
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
        """
        Check whether any head touch sensor is currently active.

        Returns
        -------
        bool
            True if at least one head sensor reports a touch.
        """
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
    Redis-backed state for the pan motor driver.
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
    Redis-backed state for the tilt motor driver.
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
    Redis-backed state for the onboard display driver.
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
    Redis-backed state for the speech synthesis driver.
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
    Redis-backed state for the conversation (LLM) behaviour.
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
    Redis-backed state for the Akinator behaviour.
    """

    prefix = "akinator"
    fields = {"running": False, "guessed": False, "error": None}


class Server(DBEntry):
    """
    Redis-backed state and URL helpers for the HTTP server.

    Attributes
    ----------
    ready : bool
        True once the server is up and serving static files.
    http_port : int
        Port for the HTTP server.
    udp_port : int
        Port for the UDP server.
    api_port : int
        Port for the API server.
    static_path : str
        Relative path to the static assets directory.
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
        Return the full URL for an image asset, waiting for the server if needed.

        Parameters
        ----------
        name : str
            Image filename.

        Returns
        -------
        str
            Full HTTP URL.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/images/" + name

    def url_for_sound(self, name):
        """
        Return the full URL for a sound asset, waiting for the server if needed.

        Parameters
        ----------
        name : str
            Sound filename.

        Returns
        -------
        str
            Full HTTP URL.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/sounds/" + name

    def url_for_icon(self, name):
        """
        Return the full URL for an icon asset, waiting for the server if needed.

        Parameters
        ----------
        name : str
            Icon filename.

        Returns
        -------
        str
            Full HTTP URL.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/icons/" + name

    def url_for_video(self, name):
        """
        Return the full URL for a video asset, waiting for the server if needed.

        Parameters
        ----------
        name : str
            Video filename.

        Returns
        -------
        str
            Full HTTP URL.
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return "http://elmo:8000/videos/" + name

    def url_for_camera(self):
        """
        Return the camera stream URL, waiting for the server if needed.

        Returns
        -------
        str
            Camera stream URL (currently empty).
        """
        # wait for server to be ready
        while not self.ready:
            time.sleep(0.1)
        return ""

    def get_image_list(self):
        """
        Fetch the list of available image assets from the server.

        Returns
        -------
        list
            List of image filenames, or empty list on error.
        """
        try:
            url = self.url_for_image("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []

    def get_sound_list(self):
        """
        Fetch the list of available sound assets from the server.

        Returns
        -------
        list
            List of sound filenames, or empty list on error.
        """
        try:
            url = self.url_for_sound("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []

    def get_icon_list(self):
        """
        Fetch the list of available icon assets from the server.

        Returns
        -------
        list
            List of icon filenames, or empty list on error.
        """
        try:
            url = self.url_for_icon("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []

    def get_video_list(self):
        """
        Fetch the list of available video assets from the server.

        Returns
        -------
        list
            List of video filenames, or empty list on error.
        """
        try:
            url = self.url_for_video("")[:-1]
            response = requests.get(url)
            return response.json()
        except:
            return []


class Power(DBEntry):
    """
    Redis-backed state for the power management driver.
    """

    prefix = "power"
    fields = {"reboot": False, "shutdown": False, "gpio_shutdown": True}


class Behaviours(DBEntry):
    """
    Redis-backed feature flags for enabling or disabling behaviours.
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
        Return the names of all declared behaviour flags.

        Returns
        -------
        dict_keys
            Keys from the fields dict.
        """
        return self.fields.keys()


class Printer(DBEntry):
    """
    Redis-backed state for the Instax printer integration.
    """

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
