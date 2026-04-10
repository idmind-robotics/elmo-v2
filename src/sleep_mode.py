"""

Sleep Mode.

This node is the sleep mode of elmo.

When there isn't any interaction with the robot for 2 minutes,
elmo's eyes change to sleeping-like eyes.
When there isn't any interaction with the robot for 3 minutes
more (total: 5mins), elmo's eyes fade into total darkness.

"""


import time
from threading import Event, Thread
from middleware import TouchSensors, Onboard, Server, GPIO
from mode_manager import ModeManager


class SleepMode:
    """
    Manages the onboard display sleep transitions based on inactivity.

    Attributes
    ----------
    FIRST_TIMEOUT : int
        Seconds of inactivity before showing the first sleep image.
    SECOND_TIMEOUT : int
        Additional seconds of inactivity before showing the second sleep image.
    FIRST_IMAGE : str
        Filename of the image shown at the first sleep stage.
    SECOND_IMAGE : str
        Filename of the image shown at the second sleep stage.
    NORMAL_IMAGE : str
        Filename of the image shown when the robot is active.
    touch : TouchSensors
        Middleware touch sensor state for detecting interaction.
    gpio : GPIO
        Middleware GPIO state.
    display : Onboard
        Middleware onboard display controller for images.
    server : Server
        Middleware server helper for resource URLs.
    mode_manager : ModeManager
        Mode manager used to detect active non-idle behaviours.
    last_activity : float
        Timestamp of the most recent interaction or mode change.
    current_state : str or None
        Currently displayed state ("normal", "first", "second", or None).
    last_idle_state : bool or None
        Last known idle state, used to detect mode transitions.
    wake_event : threading.Event
        Event used to interrupt the main loop sleep on activity.
    """

    FIRST_TIMEOUT = 120
    SECOND_TIMEOUT = 180
    #FIRST_TIMEOUT = 10
    #SECOND_TIMEOUT = 10
    FIRST_IMAGE = "sleep.png"
    SECOND_IMAGE = "background_black.png"
    NORMAL_IMAGE = "normal.png"

    def __init__(self):
        """
        Initialize middleware objects, image URLs, activity tracking, and monitor threads.
        """
        self.touch = TouchSensors()
        self.gpio = GPIO()
        self.display = Onboard()
        self.server = Server()
        self.mode_manager = ModeManager()

        self.first_image_url = self.server.url_for_image(self.FIRST_IMAGE)
        self.second_image_url = self.server.url_for_image(self.SECOND_IMAGE)
        self.normal_image_url = self.server.url_for_image(self.NORMAL_IMAGE)

        # timestamp of the last interaction/activity (touch or non idle mode)
        self.last_activity = time.time()
        self.current_state = None
        self.last_idle_state = None
        self.wake_event = Event()

        # Thread to monitor touch
        Thread(target=self.monitor_touch, daemon=True).start()
        # Thread to monitor modes
        Thread(target=self.monitor_mode, daemon=True).start()

    def monitor_touch(self):
        """
        Background thread that resets the activity timer on new touch events.

        Behavior
        --------
        - Polls chest and head touch sensors every 100ms.
        - On a rising edge (new touch), updates `last_activity` and sets `wake_event`.
        """
        last_touch = False

        while True:
            touched = self.touch.touch_chest or self.touch.head_touch()

            if touched and not last_touch:
                self.last_activity = time.time()
                self.wake_event.set()

            last_touch = touched
            time.sleep(0.1)

    def monitor_mode(self):
        """
        Background thread that resets the activity timer on mode transitions.

        Behavior
        --------
        - Polls active behaviour flags every 200ms.
        - On idle/non-idle transition, updates `last_activity` and sets `wake_event`.
        """
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

    def update_display(self, state, url):
        """
        Update the onboard display if the state has changed.

        Parameters
        ----------
        state : str
            New state label ("normal", "first", or "second").
        url : str
            Image URL to set on the onboard display.
        """
        if self.current_state != state:
            self.display.image = url
            self.current_state = state

    def run(self):
        """
        Main sleep mode loop.

        Behavior
        --------
        - In idle mode: shows the first sleep image after `FIRST_TIMEOUT` seconds,
        the second sleep image after an additional `SECOND_TIMEOUT` seconds,
        and restores normal eyes on touch.
        - In non-idle mode: resets the activity timer and restores normal eyes.
        - Uses `wake_event` to avoid busy-waiting between state checks.
        """
        while True:
            inactive_time = time.time() - self.last_activity

            if self.is_idle_mode():
                if self.touch.touch_chest or self.touch.head_touch():
                    self.last_activity = time.time()
                    self.update_display("normal", self.normal_image_url)
                else:
                    if inactive_time >= self.FIRST_TIMEOUT + self.SECOND_TIMEOUT:
                        self.update_display("second", self.second_image_url)
                    elif inactive_time >= self.FIRST_TIMEOUT:
                        self.update_display("first", self.first_image_url)
            else:
                # if its not idle, resets the timer and shows normal eyes
                if self.current_state != "normal":
                    self.last_activity = time.time()
                    self.update_display("normal", self.normal_image_url)

            self.wake_event.wait(timeout=1.0)
            self.wake_event.clear()


if __name__ == "__main__":
    sleep_mode = SleepMode()
    sleep_mode.run()
