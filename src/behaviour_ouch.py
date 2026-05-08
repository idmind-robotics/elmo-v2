"""

Behaviour node.

When a screen touch is detected, the robot plays the ouch_tears_open
animation: eyes go to ouch expression, then tears, then back to open.

Touch detection is handled via the browser (touchstart event in main.js)
which POSTs to /api/touch, setting onboard.touch = True in Redis.
This node reads that flag and resets it after detection.

The single video ouch_tears_open.mp4 is used regardless of the current
eye state — sleep_mode yields the display while behaviour_ouch_active
is True.

Only runs when behaviours.ouch is True (set by the mode manager in idle mode).

"""

import time

import middleware as mw


OPEN_PNG = "open.png"
OUCH_TEARS_OPEN_MP4 = "ouch_tears_open.mp4"
VIDEO_DURATION = 5.5
COOLDOWN = 2.0


class BehaviourOuch:
    """
    Middleware behaviour that triggers an ouch/tears animation on screen touch.

    Reads onboard.touch from Redis (set by /api/touch via main.js touchstart).
    sleep_mode yields the display while behaviour_ouch_active is True.

    Attributes
    ----------
    onboard : mw.Onboard
        Middleware onboard display controller.
    behaviours : mw.Behaviours
        Middleware behaviour configuration flags.
    server : mw.Server
        Middleware server helper for resource URLs.
    node : mw.Node
        Middleware node used for shutdown and logging.
    url_open : str
        Pre-resolved URL for the open eyes static image.
    video_url : str
        Pre-resolved URL for the ouch_tears_open video.
    """

    def __init__(self):
        """
        Initialize middleware objects and pre-resolve URLs.
        """
        self.onboard = mw.Onboard()
        self.behaviours = mw.Behaviours()
        self.server= mw.Server()
        self.node = mw.Node("behaviour_ouch")
        self.url_open  = self.server.url_for_image(OPEN_PNG)
        self.video_url = self.server.url_for_video(OUCH_TEARS_OPEN_MP4)

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

    def is_touch_detected(self):
        """
        Check and consume a pending touch event from Redis.

        Returns
        -------
        bool
            True if onboard.touch was True, resets it to False after reading.
        """
        touched = bool(self.onboard.touch)
        if touched:
            self.onboard.touch = False
        return touched

    def ouch(self):
        """
        Execute the ouch animation.

        Behavior
        --------
        - Sets behaviour_ouch_active so sleep_mode yields the display.
        - Plays ouch_tears_open.mp4 on the onboard display.
        - Waits for the video to finish.
        - Restores open.png and releases display back to sleep_mode.
        - Signals sleep_mode to reset its inactivity timer.
        """
        self.set_key("behaviour_ouch_active", True)
        self.node.loginfo("ouch")
        self.onboard.video = self.video_url
        time.sleep(VIDEO_DURATION)
        self.onboard.video = None
        self.onboard.image = self.url_open
        self.set_key("sleep_mode_last_interaction", time.time())
        self.set_key("behaviour_ouch_active", False)

    def run(self):
        """
        Main behaviour loop.

        Behavior
        --------
        - Polls Redis for touch events at ~20 Hz.
        - Skips if behaviours.ouch is False.
        - Triggers ouch() on touch, then enforces a cooldown before next trigger.
        - Clears behaviour_ouch_active and shuts down node in finally block.
        """
        try:
            self.node.loginfo("starting behaviour")
            last_ouch = 0.0
            while not self.node.is_shutdown():
                time.sleep(0.05)
                if not self.behaviours.ouch:
                    self.onboard.touch = False
                    continue
                if time.time() - last_ouch < COOLDOWN:
                    self.onboard.touch = False
                    continue
                if self.is_touch_detected():
                    self.ouch()
                    last_ouch = time.time()
        finally:
            self.set_key("behaviour_ouch_active", False)
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourOuch()
    node.run()
