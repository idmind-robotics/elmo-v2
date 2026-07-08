"""

Behaviour node.

When a head touch is detected, the behaviour updates the onboard video,
plays a sound and changes the leds.

"""

import time

import middleware as mw


LOOP_RATE = 10
TOUCH_COUNTER_THRESHOLD = 3
COOLDOWN = 2 * LOOP_RATE

EYES_OPENED = 1
EYES_CLOSED = 3

VIDEO_MAP = {
    EYES_OPENED: ("open_blush_open.mp4", 5.3),
    EYES_CLOSED: ("dark_blush_open.mp4", 5.8),
}


class BehaviourBlush:
    """
    Middleware behaviour that triggers a "blush" animation on touch.

    Reads sleep_mode_eye_state (1/3) to select the correct video,
    then owns the display, LEDs, and speaker for the full animation.
    sleep_mode yields the display while behaviour_blush_active is True.

    > ## Attributes

    ``touch_sensors : mw.TouchSensors`` : Middleware touch sensor state used to detect head touches.

    ``leds : mw.Leds`` : Middleware LED controller for icon/animation display.

    ``onboard : mw.Onboard`` : Middleware onboard display controller for images and videos.

    ``speakers : mw.Speakers`` : Middleware speaker controller for playing sounds.

    ``behaviours : mw.Behaviours`` : Middleware behaviour configuration flags.

    ``server : mw.Server`` : Middleware server helper for resource URLs.

    ``node : mw.Node`` : Middleware node used for shutdown and logging.

    ``url_open : str`` : Pre-resolved URL for the open eyes static image.

    ``video_urls : dict`` : Pre-resolved URLs for each blush transition video, keyed by eye state.

    ``video_durations : dict`` : Fallback durations in seconds for each video, keyed by eye state.

    > ## Functions
    """

    def __init__(self):
        """
        Initialize middleware objects and behaviour node.
        """
        self.touch_sensors = mw.TouchSensors()
        self.leds = mw.Leds()
        self.onboard = mw.Onboard()
        self.speakers = mw.Speakers()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.node = mw.Node("behaviour_blush")

        self.url_open = self.server.url_for_image("normal.png")

        # Pre-resolve video URLs keyed by eye state integer
        self.video_urls = {}
        self.video_durations = {}
        for eye_state, (filename, duration) in VIDEO_MAP.items():
            self.video_urls[eye_state] = self.server.url_for_video(filename)
            self.video_durations[eye_state] = duration

    def sleep_mode_state(self):
        """
        Read the current eye state from sleep_mode's Redis semaphore.

        Returns
        -------
        int
            EYES_OPENED (1) or EYES_CLOSED (3).
            Defaults to EYES_OPENED if the key is missing or unreadable.
        """
        try:
            return int(mw.get_key("sleep_mode_eye_state"))
        except (TypeError, ValueError):
            return EYES_OPENED

    def blush(self):
        """
        Execute the full blush animation.

        Behavior
        --------
        - Reads sleep_mode_eye_state to pick the correct transition video.
        - Sets "behaviour_blush_active" so sleep_mode yields the display
          and other behaviours pause.
        - Plays the transition video on the onboard display.
        - Simultaneously plays "love.wav" via speakers and loads
          "heartbeat.gif" into the LED matrix.
        - Waits for the video to finish, then restores normal.png.
        - Restores the previous LED icon (skipping clock temporary PNGs).
        - Clears "behaviour_blush_active" so sleep_mode resumes.
        """
        eye_state = self.sleep_mode_state()
        video_url = self.video_urls[eye_state]
        duration = self.video_durations[eye_state]
        mw.set_key("behaviour_blush_active", True)
        self.node.loginfo("blushing")
        previous_icon_url = self.leds.url
        self.onboard.video = video_url
        self.speakers.url = self.server.url_for_sound("love.wav")
        self.leds.load_from_url(self.server.url_for_icon("heartbeat.gif"))
        time.sleep(duration)
        self.onboard.image = self.url_open
        # Restore LEDs to previous state
        try:
            # Avoid restoring temporary PNG files created by the clock behaviour
            if previous_icon_url and ".png" not in previous_icon_url:
                self.leds.load_from_url(previous_icon_url)
            else:
                self.leds.clear()
        except Exception:
            self.leds.clear()
        mw.set_key("behaviour_blush_active", False)
        mw.set_key("sleep_mode_last_interaction", time.time())

    def run(self):
        """
        Main behaviour loop.

        Behavior
        --------
        - Logs startup.
        - Polls at LOOP_RATE (10 Hz).
        - Checks behaviours.blush and head touch events.
        - Uses touch count threshold and cooldown to avoid repeated triggers.
        - Calls blush() when conditions are met.
        - Always clears "behaviour_blush_active" and shuts down in finally block.
        """
        try:
            self.node.loginfo("starting behaviour")
            touch_counter = 0
            cooldown_counter = 0
            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)
                if cooldown_counter > 0:
                    cooldown_counter -= 1
                if (
                    self.behaviours.blush
                    and self.touch_sensors.head_touch()
                    and not self.behaviours.photographer
                ):
                    if touch_counter < TOUCH_COUNTER_THRESHOLD:
                        touch_counter += 1
                    if touch_counter == TOUCH_COUNTER_THRESHOLD:
                        if cooldown_counter == 0:
                            self.blush()
                            touch_counter = 0
                            cooldown_counter = COOLDOWN
        finally:
            mw.set_key("behaviour_blush_active", False)
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourBlush()
    node.run()
