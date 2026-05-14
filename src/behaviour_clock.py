"""

Behaviour node.

When the chest is touched, the behaviour displays the current time
and weather on the LED matrix using fade transitions.
Only runs when behaviours.clock is True (set by the mode manager in idle mode).

"""

import time
from datetime import datetime
import middleware as mw
import requests

CITY = None


class BehaviourClock:
    """
    Middleware behaviour that displays a clock and weather sequence on touch.

    Attributes
    ----------
    leds : mw.Leds
        Middleware LED controller for drawing and animation.
    server : mw.Server
        Middleware server helper for resource URLs.
    node : mw.Node
        Middleware node used for shutdown and logging.
    touch_sensors : mw.TouchSensors
        Middleware touch sensor state used to detect chest touches.
    behaviours : mw.Behaviours
        Middleware behaviour flags used to check if clock is enabled.
    """

    def __init__(self):
        """
        Initialize middleware objects and behaviour node.
        """
        self.leds = mw.Leds()
        self.server = mw.Server()
        self.node = mw.Node("behaviour_clock")
        self.touch_sensors = mw.TouchSensors()
        self.behaviours = mw.Behaviours()
        self.battery = mw.Battery()

        global CITY
        CITY = self.get_city()

    def get_key(self, key):
        """
        Safely retrieve a Redis key via middleware.

        Parameters
        ----------
        key : str
            Redis key name.

        Returns
        -------
        any
            Parsed value, or False if key does not exist.
        """
        if not mw.has_key(key):
            return False
        return mw.get_key(key)

    def set_key(self, key, value):
        """
        Set a Redis key via middleware.

        Parameters
        ----------
        key : str
            Redis key name.
        value : any
            Value to store.
        """
        mw.set_key(key, value)

    def is_blush_active(self):
        """
        Check whether the blush behaviour is currently active.

        Returns
        -------
        bool
            True if blush is active and LEDs are reserved.
        """
        return bool(self.get_key("behaviour_blush_active"))

    def detect_city_by_timezone(self):
        """
        Infer city from the system timezone name.

        Returns
        -------
        str
            City name, defaulting to "Lisbon" if timezone is unknown.
        """
        tz = time.tzname[0]
        tz_map = {
            "GMT": "Lisbon",
            "WET": "Lisbon",
            "CET": "Paris",
            "EST": "New York",
            "EDT": "New York",
            "PST": "Los Angeles",
            "PDT": "Los Angeles",
        }
        return tz_map.get(tz, "Lisbon")

    def get_city(self):
        """
        Retrieve city from Redis or fall back to timezone detection.

        Returns
        -------
        str
            City name used for weather queries.
        """
        if mw.has_key("city"):
            return mw.get_key("city")
        return self.detect_city_by_timezone()

    def is_night(self):
        """
        Determine whether it is currently night time.

        Returns
        -------
        bool
            True if current hour is before 07:00 or from 20:00 onwards.
        """
        h = datetime.now().hour
        return h < 7 or h >= 20

    def generate_clock_image(self):
        """
        Generate the clock display image using the half-half layout.

        Behavior
        --------
        - Top half: two hour digits and the "H" label.
        - Bottom half: two minute digits.
        - Halves are merged into a full 13x13 canvas.

        Returns
        -------
        PIL.Image.Image
            Full 13x13 image ready to be loaded into the LEDs.
        """
        now = datetime.now()
        h, m = now.strftime("%H"), now.strftime("%M")

        top = self.leds.create_top_canvas()
        self.leds.draw_digit(top, h[0], 1, 1)
        self.leds.draw_digit(top, h[1], 5, 1)
        self.leds.draw_letter(top, "H", 9, 1)

        bottom = self.leds.create_bottom_canvas()
        self.leds.draw_digit(bottom, m[0], 1, 0)
        self.leds.draw_digit(bottom, m[1], 5, 0)

        return self.leds.merge_halves(top, bottom)

    def get_weather(self):
        """
        Fetch current weather from wttr.in for the configured city.

        Behavior
        --------
        - Queries wttr.in JSON API.
        - Matches the closest hourly entry to the current hour.
        - Maps weather description to one of the display icon keys.
        - Falls back to (20, "no_internet") on any error.

        Returns
        -------
        tuple[int, str]
            Temperature in Celsius and weather icon key string.
        """
        url = f"https://wttr.in/{CITY}?format=j1"
        try:
            data = requests.get(url, timeout=5).json()
            now_hour = datetime.now().hour
            hourly = data["weather"][0]["hourly"]
            closest = min(hourly, key=lambda h: abs(int(h["time"]) // 100 - now_hour))
            temp = int(closest["tempC"])
            desc = data["current_condition"][0]["weatherDesc"][0]["value"].lower()

            if "thunder" in desc:
                icon = "storm"
            elif "rain" in desc or "drizzle" in desc:
                icon = "rain"
            elif "cloud" in desc or "overcast" in desc:
                icon = "night_partly" if self.is_night() else "cloud"
            elif "sun" in desc or "clear" in desc or "sunny" in desc:
                icon = "night_clear" if self.is_night() else "clear"
            else:
                icon = "night_partly" if self.is_night() else "partly"

            return temp, icon

        except:
            return 88, "no_internet"

    def generate_weather_image(self):
        """
        Generate the weather display image using the half-half layout.

        Behavior
        --------
        - Top half: weather condition icon.
        - Bottom half: temperature digits, degree dot, and "C" label.
        - Halves are merged into a full 13x13 canvas.

        Returns
        -------
        PIL.Image.Image
            Full 13x13 image ready to be loaded into the LEDs.
        """
        temp, icon_key = self.get_weather()

        top = self.leds.create_top_canvas()
        self.leds.draw_icon(top, "weather_icons", icon_key)

        t_str = str(abs(temp)).zfill(2)
        bottom = self.leds.create_bottom_canvas()
        self.leds.draw_digit(bottom, t_str[0], 0, 1)
        self.leds.draw_digit(bottom, t_str[1], 4, 1)
        self.leds.draw_icon(bottom, "pixels", "degrees_dot", ox=8, oy=1)
        self.leds.draw_letter(bottom, "C", 10, 1)

        return self.leds.merge_halves(top, bottom)

    def generate_battery_image(self):
        """
        Generate the battery display image using the half-half layout.

        Behavior
        --------
        - Top half: battery icon showing charge level (red/yellow/green fill).
        - Bottom half: percentage digits, centred by digit count (no % symbol).
        - 1 digit  (0–9):   single digit centred at ox=5.
        - 2 digits (10–99): left at ox=3, right at ox=7 (1-px gap at centre).
        - 3 digits (100):   digits at ox=1, ox=5, ox=9.
        - Halves are merged into a full 13x13 canvas.

        Returns
        -------
        PIL.Image.Image
            Full 13x13 image ready to be loaded into the LEDs.
        """
        pct_int = max(0, min(100, int(self.battery.percentage)))
        if pct_int <= 3:
            icon_key = "empty"
        elif pct_int <= 10:
            icon_key = "level_1"
        elif pct_int <= 20:
            icon_key = "level_2"
        elif pct_int <= 30:
            icon_key = "level_3"
        elif pct_int <= 40:
            icon_key = "level_4"
        elif pct_int <= 50:
            icon_key = "level_5"
        elif pct_int <= 60:
            icon_key = "level_6"
        elif pct_int <= 70:
            icon_key = "level_7"
        elif pct_int <= 80:
            icon_key = "level_8"
        elif pct_int <= 90:
            icon_key = "level_9"
        else:
            icon_key = "level_10"
        top = self.leds.create_top_canvas()
        self.leds.draw_icon(top, "battery_icons", icon_key)
        bottom = self.leds.create_bottom_canvas()
        p_str = str(pct_int)
        if len(p_str) == 1:
            self.leds.draw_digit(bottom, p_str[0], 5, 1)
        elif len(p_str) == 2:
            self.leds.draw_digit(bottom, p_str[0], 3, 1)
            self.leds.draw_digit(bottom, p_str[1], 7, 1)
        else:
            self.leds.draw_digit(bottom, "1", 1, 1)
            self.leds.draw_digit(bottom, "0", 5, 1)
            self.leds.draw_digit(bottom, "0", 9, 1)

        return self.leds.merge_halves(top, bottom)

    def fade_images(self, img_from, img_to, steps=10, duration=1):
        """
        Request a fade transition between two images via driver_leds.

        Behavior
        --------
        - Loads the starting image directly into the LED state.
        - Requests the fade to the target image through middleware.
        - Polls until driver_leds completes the fade.
        - Aborts and returns False if blush becomes active mid-fade.

        Parameters
        ----------
        img_from : PIL.Image.Image
            Starting image for the fade.
        img_to : PIL.Image.Image
            Target image for the fade.
        steps : int
            Number of interpolation steps.
        duration : float
            Total fade duration in seconds.

        Returns
        -------
        bool
            True if the fade completed, False if interrupted by blush.
        """
        if self.is_blush_active():
            self.leds.clear()
            return False
        self.leds.load_from_image(img_from)
        self.leds.request_fade(img_to, steps=steps, duration=duration)
        while self.leds.fade_active:
            if self.is_blush_active():
                self.leds.fade_active = False  # signal driver_leds to abort
                self.leds.clear()
                return False
            time.sleep(0.05)
        return True

    def sequence(self):
        """
        Display sequence: clock, weather and battery.

        Behavior
        --------
        - Fades in the clock image, holds for 1.5 seconds, fades out.
        - Fades in the weather image, holds for 1.5 seconds, fades out.
        - Fades in the battery image, holds for 1.5 seconds with live percentage
        updates every 100ms, fades out.
        - Aborts at any step if blush becomes active.
        """
        if self.is_blush_active():
            return
        img_black = self.leds.create_canvas()
        clock_img = self.generate_clock_image()
        weather_img = self.generate_weather_image()
        if not self.fade_images(img_black, clock_img, steps=15, duration=1):
            return
        time.sleep(1.5)
        if not self.fade_images(clock_img, img_black, steps=15, duration=1):
            return
        if not self.fade_images(img_black, weather_img, steps=20, duration=1):
            return
        time.sleep(1.5)
        if not self.fade_images(weather_img, img_black, steps=20, duration=1):
            return
        battery_img = self.generate_battery_image()
        if not self.fade_images(img_black, battery_img, steps=15, duration=1):
            return
        # Hold for 5 seconds, redrawing immediately whenever percentage changes
        last_pct = max(0, min(100, int(self.battery.percentage)))
        hold_end = time.time() + 1.5
        while time.time() < hold_end:
            if self.is_blush_active():
                self.leds.clear()
                return
            current_pct = max(0, min(100, int(self.battery.percentage)))
            if current_pct != last_pct:
                battery_img = self.generate_battery_image()
                self.leds.load_from_image(battery_img)
                last_pct = current_pct
            time.sleep(0.1)
        if not self.fade_images(battery_img, img_black, steps=15, duration=1):
            return
        self.leds.clear()

    def run(self):
        """
        Main behaviour loop.

        Behavior
        --------
        - Logs startup.
        - Polls every 100ms for chest touch.
        - Skips while blush behaviour is active or behaviours.clock is False.
        - Triggers the clock/weather sequence on chest touch.
        - Always clears LEDs and shuts down node in finally block.
        """
        self.node.loginfo("behaviour start")
        try:
            while not self.get_key(self.node.name + "is_shutdown"):
                time.sleep(0.1)
                if self.is_blush_active():
                    continue
                if not self.behaviours.clock:
                    continue
                if self.touch_sensors.touch_chest:
                    self.sequence()
        finally:
            self.leds.clear()
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourClock()
    node.run()
