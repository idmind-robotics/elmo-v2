"""

Behaviour node.

When a head touch is detected, the behaviour updates the onboard image,
plays a sound and changes the leds.

"""

import time

import middleware as mw


LOOP_RATE = 10
TOUCH_COUNTER_THRESHOLD = 3
COOLDOWN = 2 * LOOP_RATE


class BehaviourBlush:
    """
    Middleware behaviour that triggers a "blush" animation on touch.

    Attributes
    ----------
    touch_sensors : mw.TouchSensors
        Middleware touch sensor state used to detect head touches.
    leds : mw.Leds
        Middleware LED controller for icon/animation display.
    onboard : mw.Onboard
        Middleware onboard display controller for images.
    speakers : mw.Speakers
        Middleware speaker controller for playing sounds.
    behaviours : mw.Behaviours
        Middleware behaviour configuration flags.
    server : mw.Server
        Middleware server helper for resource URLs.
    node : mw.Node
        Middleware node used for shutdown and logging.
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

    def blush(self):
        """
        Execute blush behaviour routine.

        Behavior
        --------
        - Logs blushing activity.
        - Stores previous LED icon URL.
        - Sets onboard image to "love.png".
        - Plays "love.wav" via speakers.
        - Loads "heartbeat.gif" into LEDs.
        - Waits 5 seconds.
        - Restores onboard image and previous LEDs icon URL.
        - Assumes middleware fields are set and available.
        """
        self.node.loginfo("blushing")
        previous_icon_url = self.leds.url
        image_url = self.server.url_for_image("love.png")
        self.onboard.image = image_url
        sound_url = self.server.url_for_sound("love.wav")
        self.speakers.url = sound_url
        icon_url = self.server.url_for_icon("heartbeat.gif")
        self.leds.load_from_url(icon_url)
        time.sleep(5.0)
        image_url = self.server.url_for_image("normal.png")
        self.onboard.image = image_url
        self.leds.load_from_url(previous_icon_url)
        # icon_url = self.server.url_for_icon("elmo_idm.png")
        # self.leds.load_from_url(icon_url)

    def run(self):
        """
        Main behaviour loop.

        Behavior
        --------
        - Logs startup.
        - Polls at `LOOP_RATE`.
        - Checks `behaviours.blush` and head touch events.
        - Uses touch count threshold (`TOUCH_COUNTER_THRESHOLD`) and cooldown
          (`COOLDOWN`) to avoid repeated trigger.
        - Calls `blush()` when conditions are met.
        - Always shuts down node in finally block.

        Returns
        -------
        None
        """
        try:
            self.node.loginfo("starting behaviour")
            touch_counter = 0
            cooldown_counter = 0
            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)
                if cooldown_counter > 0:
                    cooldown_counter -= 1
                if self.behaviours.blush and self.touch_sensors.head_touch():
                    if touch_counter < TOUCH_COUNTER_THRESHOLD:
                        touch_counter += 1
                    if touch_counter == TOUCH_COUNTER_THRESHOLD:
                        if cooldown_counter == 0:
                            self.blush()
                            cooldown_counter = COOLDOWN
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourBlush()
    node.run()
