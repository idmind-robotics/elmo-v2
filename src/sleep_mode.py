"""

Tool node.

Controls the robot sleep mode state machine and onboard eye transitions.

When there is no user interaction for a configurable amount of time,
the node transitions the onboard display through open and dark
states while coordinating with behaviour nodes that may temporarily own
the display.

"""

import time
from threading import Event, Thread

from mode_manager import ModeManager
import middleware as mw


EYES_OPENED = 1
EYES_CLOSED = 2

VIDEO_DURATIONS = {
    "open_dark.webm": 2.0,
    "dark_open.webm": 2.0,
    "dark_squint_dark.webm": 7.0,
}


class SleepMode:
    """
    Manages the onboard display sleep transitions based on inactivity.

    Owns the onboard display during idle mode. Yields it to behaviours
    when they raise their active flag, and resumes when the flag clears.

    Publishes eye state through mw.Sleep().eye_state (EYES_OPENED=1, EYES_CLOSED=2)
    so behaviours can choose the correct transition animation without depending on
    sleep_mode internals.

    > ## Attributes

    ``touch : mw.TouchSensors`` : Middleware touch sensor state.

    ``gpio : mw.GPIO`` : Middleware GPIO state.

    ``display : mw.Onboard`` : Middleware onboard display controller.

    ``server : mw.Server`` : Middleware server helper for resource URLs.

    ``mode_manager : ModeManager`` : Mode manager used to determine idle and active states.

    ``video_urls : dict`` : Mapping between filenames and resolved video URLs.

    ``last_activity : float`` : Timestamp of the latest detected interaction.

    ``current_state : str | None`` : Current eye state label.

    ``last_idle_state : bool | None`` : Last detected idle state.

    ``playing_video : bool`` : True while a transition video is active.

    ``wake_event : threading.Event`` : Synchronisation event used to wake the main loop.

    ``next_state : float`` : Timestamp for the next dark-mode peek animation.

    > ## Functions
    """

    def __init__(self):
        """
        Initialise middleware objects, pre-resolve URLs, and start monitor threads.
        """
        self.touch = mw.TouchSensors()
        self.display = mw.Onboard()
        self.server = mw.Server()
        self.mode_manager = ModeManager()
        self.sleep = mw.Sleep()

        self.video_urls = {
            f: self.server.url_for_video(f)
            for f in ["open_dark.webm", "dark_open.webm", "dark_squint_dark.webm"]
        }

        self.sleep.last_activity = time.time()
        self.current_state = None
        self.last_idle_state = None
        self.playing_video = False
        self.was_behaviour_active = False
        self.next_state = time.time() + self.sleep.timeout
        self.wake_event = Event()

        self.sleep.eye_state = EYES_OPENED
        Thread(target=self.monitor_touch, daemon=True).start()
        Thread(target=self.monitor_mode, daemon=True).start()

    def monitor_touch(self):
        """
        Background thread: resets the activity timer on a new chest touch
        and wakes the main loop immediately.

        Only chest touches are handled here. Head touches are exclusively
        used by behaviour_blush — reacting to them here would cause
        sleep_mode to call eyes_opening() at the same time blush fires,
        creating a display race condition.
        """
        last_touch = False
        while True:
            touched = self.touch.touch_chest
            if touched and not last_touch:
                self.sleep.last_activity = time.time()
                self.wake_event.set()
            last_touch = touched
            time.sleep(0.1)

    def monitor_mode(self):
        """
        Background thread: resets the activity timer on idle/non-idle
        transitions caused by other behaviours becoming active or inactive,
        and when a behaviour explicitly signals interaction via
        mw.Sleep().last_interaction.
        """
        last_interaction = 0.0
        while True:
            idle = self.is_idle_mode()
            if idle != self.last_idle_state:
                self.last_idle_state = idle
                self.sleep.last_activity = time.time()
                self.wake_event.set()
            try:
                t = self.sleep.last_interaction
                if t > last_interaction:
                    last_interaction = t
                    self.sleep.last_activity = t
                    self.wake_event.set()
            except TypeError:
                pass
            time.sleep(0.2)

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
        try:
            return mw.get_key("behaviour_blush_active") or mw.get_key(
                "behaviour_hello_active"
            )
        except TypeError:
            return False

    def set_image(self, url, state, eye_state):
        """
        Show a static image and publish the new eye state.
        Only updates the display and middleware state when
        the state actually changes.

        Parameters
        ----------
        url : str
            Image URL to display.
        state : str
            New state label ("open" or "dark").
        eye_state : int
            Semaphore value to publish (EYES_OPENED or EYES_CLOSED).
        """
        if self.current_state != state:
            self.display.image = url
            self.current_state = state
            self.sleep.eye_state = eye_state

    def play_video(self, filename, then_image_url=None, restore=True):
        """
        Play a transition video and wait for it to finish.

        Uses known clip duration as timing fallback since Onboard does not
        expose a video_playing flag.

        Parameters
        ----------
        filename : str
            Video filename (e.g. "dark_open.webm").
        then_image_url : str, optional
            Static image URL to restore after playback. Defaults to normal.png.
            Only used when restore=True.
        restore : bool, optional
            If True (default), sets a static image after the video ends.
            Set to False when the video already ends on the correct frame —
            forcing an image while the video is still playing would interrupt
            it mid-frame and cause a visual double-play artifact.
        """
        self.playing_video = True
        self.display.video = self.video_urls[filename]
        if hasattr(self.display, "video_playing"):
            while self.display.video_playing:
                time.sleep(0.05)
        else:
            time.sleep(VIDEO_DURATIONS.get(filename, 3.0))
        if restore:
            self.display.image = (
                then_image_url
                if then_image_url is not None
                else self.server.url_for_image("normal.png")
            )
        self.playing_video = False

    def eyes_closing(self):
        """
        Transition from open eyes to fully dark screen.

        Plays open_dark.webm for a smooth animation. restore=False because
        the video already ends on the dark frame — forcing display.image
        mid-playback would interrupt the video and cause a visual artifact.
        Publishes EYES_CLOSED to the semaphore.
        No-op if already in dark state.
        """
        if self.sleep.sleeping:
            return
        self.play_video("open_dark.webm", restore=False)
        self.sleep.sleeping = True
        self.current_state = "dark"
        self.sleep.eye_state = EYES_CLOSED

    def eyes_opening(self):
        """
        Wake from dark to open eyes.

        Plays dark_open.webm then restores the open static image.
        Publishes EYES_OPENED and resets the activity timer.
        """
        self.play_video(
            "dark_open.webm", then_image_url=self.server.url_for_image("normal.png")
        )
        self.sleep.sleeping = False
        self.current_state = "open"
        self.sleep.eye_state = EYES_OPENED
        self.sleep.last_activity = time.time()

    def eyes_look_around(self):
        """
        While in the dark state, play a spontaneous peek animation
        at the configured sleep interval, then return to the dark
        static image.

        Does nothing if a behaviour owns the display, or if it is too soon.
        If a behaviour becomes active mid-playback, the dark restore is skipped
        so it does not clobber the behaviour's animation.
        """
        if time.time() < self.next_state:
            return
        if self.is_behaviour_active():
            return
        self.playing_video = True
        self.display.video = self.video_urls["dark_squint_dark.webm"]
        if hasattr(self.display, "video_playing"):
            while self.display.video_playing:
                time.sleep(0.05)
        else:
            time.sleep(VIDEO_DURATIONS["dark_squint_dark.webm"])
        if not self.is_behaviour_active():
            self.display.image = self.server.url_for_image("background_black.png")
        self.playing_video = False
        self.next_state = time.time() + self.sleep.timeout

    def run(self):
        """
        Main loop.

        Priority order each iteration:
        1. Yield the display while any behaviour is active.
        2. Yield while a transition video is playing.
        3. Idle path:
            - Touch while dark → eyes_opening.
            - Inactive >= configured timeout → dark screen; spontaneous peeks.
            - Otherwise → open eyes (static PNG).
        4. Non-idle path: restore open eyes and reset timer.

        Uses wake_event to avoid busy-waiting; timeout is 1 second.
        """
        while True:
            behaviour_active = self.is_behaviour_active()
            if not self.sleep.enabled:
                if self.sleep.sleeping:
                    self.eyes_opening()

                self.wake_event.wait(timeout=1.0)
                self.wake_event.clear()
                continue
            if behaviour_active:
                self.was_behaviour_active = True
                self.wake_event.wait(timeout=0.1)
                self.wake_event.clear()
                continue
            if self.was_behaviour_active:
                self.was_behaviour_active = False
                self.current_state = None
            if self.playing_video:
                self.wake_event.wait(timeout=0.1)
                self.wake_event.clear()
                continue
            inactive_time = time.time() - self.sleep.last_activity

            if self.is_idle_mode():
                touched = self.touch.touch_chest
                if touched and self.sleep.sleeping:
                    self.eyes_opening()
                elif inactive_time >= self.sleep.timeout:
                    if not self.sleep.sleeping:
                        self.eyes_closing()
                        self.next_state = time.time() + self.sleep.timeout
                    else:
                        self.eyes_look_around()
                else:
                    self.set_image(
                        self.server.url_for_image("normal.png"), "open", EYES_OPENED
                    )
            else:
                if self.current_state != "open":
                    if self.sleep.sleeping:
                        self.eyes_opening()
                    else:
                        self.display.image = self.server.url_for_image("normal.png")
                        self.current_state = "open"
                        self.sleep.eye_state = EYES_OPENED
                    self.sleep.last_activity = time.time()

            self.wake_event.wait(timeout=1.0)
            self.wake_event.clear()


if __name__ == "__main__":
    node = SleepMode()
    node.run()
