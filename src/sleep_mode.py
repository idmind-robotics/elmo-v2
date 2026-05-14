"""

Tool node.

Controls the robot sleep mode state machine and onboard eye transitions.

When there is no user interaction for a configurable amount of time,
the node transitions the onboard display through open, squint and dark
states while coordinating with behaviour nodes that may temporarily own
the display.

"""

import time
from threading import Event, Thread

from mode_manager import ModeManager
import middleware as mw


EYE_OPEN = 1
EYE_SQUINT = 2
EYE_DARK = 3

FIRST_TIMEOUT = 120
SECOND_TIMEOUT = 180
#FIRST_TIMEOUT = 10
#SECOND_TIMEOUT = 10

DARK_PEEK_MIN = 30
DARK_PEEK_MAX = 120

OPEN_PNG = "open.png"
SQUINT_PNG = "thinking.png"
BACKGROUND_BLACK_PNG = "background_black.png"

OPEN_SQUINT_MP4 = "open_squint.mp4"
SQUINT_DARK_MP4 = "squint_dark.mp4"
SQUINT_OPEN_MP4 = "squint_open.mp4"
DARK_OPEN_MP4 = "dark_open.mp4"
DARK_SQUINT_DARK_MP4 = "dark_squint_dark.mp4"

VIDEO_DURATIONS = {
    "OPEN_SQUINT_MP4": 1.6,
    "SQUINT_DARK_MP4": 2.0,
    "SQUINT_OPEN_MP4": 1.6,
    "DARK_OPEN_MP4": 2.0,
    "DARK_SQUINT_DARK_MP4": 7.0,
}


class SleepMode:
    """
    Manages the onboard display sleep transitions based on inactivity.

    Owns the onboard display during idle mode. Yields it to behaviours
    when they raise their active flag, and resumes when the flag clears.

    Publishes sleep_mode_eye_state (EYE_OPEN=1, EYE_SQUINT=2, EYE_DARK=3)
    to Redis so behaviours can choose the correct transition animation
    without any dependency on sleep_mode internals.

    > ## Attributes

    ``touch : mw.TouchSensors`` : Middleware touch sensor state.

    ``gpio : mw.GPIO`` : Middleware GPIO state.

    ``display : mw.Onboard`` : Middleware onboard display controller.

    ``server : mw.Server`` : Middleware server helper for resource URLs.

    ``mode_manager : ModeManager`` : Mode manager used to determine idle and active states.

    ``url_open : str`` : Pre-resolved URL for the open eyes image.

    ``url_squint : str`` : Pre-resolved URL for the squint eyes image.

    ``url_dark : str`` : Pre-resolved URL for the dark background image.

    ``video_urls : dict`` : Mapping between transition identifiers and video URLs.

    ``last_activity : float`` : Timestamp of the latest detected interaction.

    ``current_state : str | None`` : Current eye state label.

    ``last_idle_state : bool | None`` : Last detected idle state.

    ``playing_video : bool`` : True while a transition video is active.

    ``wake_event : threading.Event`` : Synchronisation event used to wake the main loop.

    ``next_peek_time : float`` : Timestamp for the next dark-mode peek animation.

    > ## Functions
    """

    def __init__(self):
        """
        Initialise middleware objects, pre-resolve URLs, and start monitor threads.
        """
        self.touch = mw.TouchSensors()
        self.gpio = mw.GPIO()
        self.display = mw.Onboard()
        self.server = mw.Server()
        self.mode_manager = ModeManager()

        self.url_open = self.server.url_for_image(OPEN_PNG)
        self.url_squint = self.server.url_for_image(SQUINT_PNG)
        self.url_dark = self.server.url_for_image(BACKGROUND_BLACK_PNG)
        self.video_urls = {
            key: self.server.url_for_video(globals()[key])
            for key in VIDEO_DURATIONS
        }

        self.last_activity = time.time()
        self.current_state = None
        self.last_idle_state = None
        self.playing_video = False
        self.wake_event = Event()

        # Thread to monitor touch
        self.set_key("sleep_mode_eye_state", EYE_OPEN)
        Thread(target=self.monitor_touch, daemon=True).start()
        # Thread to monitor modes
        Thread(target=self.monitor_mode, daemon=True).start()

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
        mw.connection.set(key, mw.json.dumps(value))

    def monitor_touch(self):
        """
        Background thread: resets the activity timer on a new chest touch
        and wakes the main loop immediately.

        Only chest touches are handled here. Head touches are exclusively
        used by behaviour_blush — reacting to them here would cause
        sleep_mode to call wake_to_open() at the same time blush fires,
        creating a display race condition.
        """
        last_touch = False
        while True:
            touched = self.touch.touch_chest
            if touched and not last_touch:
                self.last_activity = time.time()
                self.wake_event.set()
            last_touch = touched
            time.sleep(0.1)

    def monitor_mode(self):
        """
        Background thread: resets the activity timer on idle/non-idle
        transitions caused by other behaviours becoming active or inactive,
        and when a behaviour explicitly signals interaction via
        sleep_mode_last_interaction.
        """
        last_interaction = 0.0
        while True:
            idle = not (
                self.mode_manager.behaviours.conversation
                or self.mode_manager.behaviours.photographer
                or self.mode_manager.behaviours.akinator
                or self.mode_manager.behaviours.wifi_connect
                )
            if idle != self.last_idle_state:
                self.last_idle_state = idle
                self.last_activity = time.time()
                self.wake_event.set()
            if mw.has_key("sleep_mode_last_interaction"):
                t = mw.get_key("sleep_mode_last_interaction")
                if t and float(t) > last_interaction:
                    last_interaction = float(t)
                    self.last_activity = last_interaction
                    self.wake_event.set()
            time.sleep(0.2)

    def get_flag(self, key):
        """
        Safely read a boolean Redis flag via middleware.

        Parameters
        ----------
        key : str
            Redis key name.

        Returns
        -------
        bool
            True if the key exists and is truthy, False otherwise.
        """
        if not mw.has_key(key):
            return False
        return bool(mw.get_key(key))

    def is_idle_mode(self):
        """
        Check whether the robot is currently in idle mode.

        Returns
        -------
        bool
            True if no active non-idle behaviour is running.
        """
        b = self.mode_manager.behaviours
        return not (b.conversation or b.photographer or b.akinator or b.wifi_connect)

    def is_behaviour_active(self):
        """
        Check whether any behaviour currently owns the display.

        Returns
        -------
        bool
        """
        return (
            self.get_flag("behaviour_blush_active")
            or self.get_flag("behaviour_hello_active")
        )

    def set_image(self, url, state, eye_state):
        """
        Show a static image and publish the new eye state semaphore.

        Only writes to the display and Redis when state actually changes.

        Parameters
        ----------
        url : str
            Image URL to display.
        state : str
            New state label ("open", "squint", or "dark").
        eye_state : int
            Semaphore value to publish (EYE_OPEN, EYE_SQUINT, or EYE_DARK).
        """
        if self.current_state != state:
            self.display.image = url
            self.current_state = state
            self.set_key("sleep_mode_eye_state", eye_state)

    def play_video(self, video_key, then_image_url=None, restore=True):
        """
        Play a transition video and wait for it to finish.

        Uses known clip duration as timing fallback since Onboard does not
        expose a video_playing flag.

        Parameters
        ----------
        video_key : str
            Key into VIDEO_DURATIONS (e.g. "SQUINT_OPEN_MP4").
        then_image_url : str, optional
            Static image URL to restore after playback. Defaults to open.png.
            Only used when restore=True.
        restore : bool, optional
            If True (default), sets a static image after the video ends.
            Set to False when the video already ends on the correct frame —
            forcing an image while the video is still playing would interrupt
            it mid-frame and cause a visual double-play artifact.
        """
        self.playing_video = True
        url = self.video_urls.get(video_key)
        if url:
            self.display.video = url
            if hasattr(self.display, "video_playing"):
                while self.display.video_playing:
                    time.sleep(0.05)
            else:
                time.sleep(VIDEO_DURATIONS.get(video_key, 3.0))
        if restore:
            restore_url = then_image_url if then_image_url is not None else self.url_open
            self.display.image = restore_url
        self.playing_video = False

    def transition_to_squint(self):
        """
        Transition from open eyes to squinted/sleepy eyes.

        Plays open_squint.mp4 for a smooth animation. restore=False because
        the video already ends on the squint frame — forcing display.image
        mid-playback would interrupt the video and cause a visual artifact.
        Publishes EYE_SQUINT to the semaphore.
        No-op if already in squint state.
        """
        if self.current_state == "squint":
            return
        self.play_video("OPEN_SQUINT_MP4", restore=False)
        self.current_state = "squint"
        self.set_key("sleep_mode_eye_state", EYE_SQUINT)

    def transition_to_dark(self):
        """
        Transition from squint eyes to fully dark screen.

        Plays squint_dark.mp4 for a smooth animation. restore=False because
        the video already ends on the dark frame — forcing display.image
        mid-playback would interrupt the video and cause a visual artifact.
        Publishes EYE_DARK to the semaphore.
        No-op if already in dark state.
        """
        if self.current_state == "dark":
            return
        self.play_video("SQUINT_DARK_MP4", restore=False)
        self.current_state = "dark"
        self.set_key("sleep_mode_eye_state", EYE_DARK)

    def wake_to_open(self):
        """
        Wake from squint or dark to open eyes.

        Plays the correct transition video based on the current display state:
        - squint → squint_open.mp4 (eyelids open gradually)
        - dark   → dark_open.mp4  (direct black-to-open, no squint intermediate)

        Publishes EYE_OPEN and resets the activity timer.
        """
        if self.current_state == "dark":
            self.play_video("DARK_OPEN_MP4", then_image_url=self.url_open)
        else:
            self.play_video("SQUINT_OPEN_MP4", then_image_url=self.url_open)
        self.current_state = "open"
        self.set_key("sleep_mode_eye_state", EYE_OPEN)
        self.last_activity = time.time()

    def looking_around(self):
        """
        While in the dark state, play a spontaneous squint-peek animation at
        a 5 minute interval, then return to the dark static image.

        Does nothing if a behaviour owns the display, or if it is too soon.
        If a behaviour becomes active mid-playback, the dark restore is skipped
        so it does not clobber the behaviour's animation.
        """
        if time.time() < self.next_peek_time:
            return
        if self.is_behaviour_active():
            return
        self.playing_video = True
        self.display.video = self.video_urls["DARK_SQUINT_DARK_MP4"]
        if hasattr(self.display, "video_playing"):
            while self.display.video_playing:
                time.sleep(0.05)
        else:
            time.sleep(VIDEO_DURATIONS["DARK_SQUINT_DARK_MP4"])
        if not self.is_behaviour_active():
            self.display.image = self.url_dark
        self.playing_video = False
        self.next_peek_time = time.time() + 300

    def run(self):
        """
        Main loop.

        Priority order each iteration:
        1. Yield the display while any behaviour is active.
        2. Yield while a transition video is playing.
        3. Idle path:
            - Touch while asleep  → wake_to_open (plays squint_open).
            - Inactive >= 5 min   → dark screen; spontaneous peeks.
            - Inactive >= 2 min   → squinted eyes (static PNG).
            - Otherwise           → open eyes (static PNG).
        4. Non-idle path: restore open eyes and reset timer.

        Uses wake_event to avoid busy-waiting; timeout is 1 second.
        """
        while True:
            # yield display to any behaviour that has taken over
            if self.is_behaviour_active():
                self.wake_event.wait(timeout=0.1)
                self.wake_event.clear()
                continue
            if self.playing_video:
                self.wake_event.wait(timeout=0.1)
                self.wake_event.clear()
                continue
            inactive_time = time.time() - self.last_activity

            if self.is_idle_mode():
                chest_touched = self.touch.touch_chest
                if chest_touched and self.current_state in ("squint", "dark"):
                    self.wake_to_open()
                elif inactive_time >= FIRST_TIMEOUT + SECOND_TIMEOUT:
                    if self.current_state != "dark":
                        self.transition_to_dark()
                        self.next_peek_time = time.time() + 300
                    else:
                        self.looking_around()
                elif inactive_time >= FIRST_TIMEOUT:
                    self.transition_to_squint()
                else:
                    self.set_image(self.url_open, "open", EYE_OPEN)
            else:
                # if its not idle, resets the timer and shows open eyes
                if self.current_state != "open":
                    if self.current_state in ("squint", "dark"):
                        self.wake_to_open()
                    else:
                        self.display.image = self.url_open
                        self.current_state = "open"
                        self.set_key("sleep_mode_eye_state", EYE_OPEN)
                    self.last_activity = time.time()

            self.wake_event.wait(timeout=1.0)
            self.wake_event.clear()


if __name__ == "__main__":
    node = SleepMode()
    node.run()
