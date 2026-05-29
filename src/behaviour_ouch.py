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


class BehaviourOuch:
    """
    Middleware behaviour that triggers an ouch/tears animation on screen touch.

    Reads onboard.touch from Redis (set by /api/touch via main.js touchstart).
    sleep_mode yields the display while behaviour_ouch_active is True.

    > ## Attributes

    ``onboard : mw.Onboard`` : Middleware onboard display controller for images and videos.

    ``behaviours : mw.Behaviours`` : Middleware behaviour configuration flags, used to check the ouch toggle.

    ``server : mw.Server`` : Middleware server helper for resolving image and video resource URLs.

    ``node : mw.Node`` : Middleware node used for shutdown and logging.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware, initialise the node, and pre-resolve resource URLs.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.onboard = mw.Onboard()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.node = mw.Node("behaviour_ouch")

    def ouch(self):
        """
        Execute the full ouch animation sequence.

        Sets behaviour_ouch_active so that sleep_mode yields the display,
        plays ouch_tears_open.mp4, waits for the video to finish, then
        restores open.png and signals sleep_mode to reset its inactivity
        timer before clearing the active flag.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        mw.set_key("behaviour_ouch_active", True)
        self.node.loginfo("ouch")
        self.onboard.video = self.server.url_for_video("ouch_tears_open.mp4")
        time.sleep(5.5)
        self.onboard.video = None
        self.onboard.image = self.server.url_for_image("normal.png")
        mw.set_key("sleep_mode_last_interaction", time.time())
        mw.set_key("behaviour_ouch_active", False)

    def run(self):
        """
        Main behaviour loop.

        Polls Redis for touch events at ~20 Hz. On each tick:
        - Clears any pending touch and skips if behaviours.ouch is False.
        - Clears any pending touch and skips if the cooldown period has not
          elapsed since the last ouch animation.
        - Calls ouch() when a touch event is detected, then records the
          timestamp for cooldown enforcement.

        Clears behaviour_ouch_active and shuts down the middleware node on
        exit (including on KeyboardInterrupt or any other exception).

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        try:
            self.node.loginfo("starting behaviour")
            last_ouch = 0.0
            while not self.node.is_shutdown():
                time.sleep(0.05)
                if not self.behaviours.ouch:
                    self.onboard.touch = False
                    continue
                if time.time() - last_ouch < 2.0:
                    self.onboard.touch = False
                    continue
                if self.onboard.touch:
                    self.onboard.touch = False
                    self.ouch()
                    last_ouch = time.time()
        finally:
            mw.set_key("behaviour_ouch_active", False)
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourOuch()
    node.run()
