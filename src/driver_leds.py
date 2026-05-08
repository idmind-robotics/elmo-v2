#! /usr/bin/env python


"""

Driver node.

This node manages the neopixel matrix.

Uses the neopixel library to control the leds.

"""

import time
import board
import neopixel


import middleware as mw


class DriverLeds:
    """
    Hardware driver for the neopixel LED matrix.

    Reads LED color state from middleware and writes it to the physical
    neopixel hardware. Also handles fade animations requested by behaviours,
    keeping all hardware access within the driver layer.

    Attributes
    ----------
    node : mw.Node
        Middleware node used for shutdown and logging.
    leds : mw.Leds
        Middleware LED state shared with behaviours.
    colors : list[list[int]]
        Local copy of the last written color state, used to detect changes.
    pixels : neopixel.NeoPixel
        Neopixel hardware interface connected to GPIO pin D18.
    """

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        Connect to neopixel.
        """
        self.node = mw.Node("driver_leds")
        self.leds = mw.Leds()
        self.colors = [[0, 0, 0]] * self.leds.number
        self.pixels = neopixel.NeoPixel(
            board.D18,
            self.leds.number,
            brightness=self.leds.brightness,
            auto_write=False,
        )
        print("brightness: %s, %s" % (self.leds.brightness, type(self.leds.brightness)))

    def execute_fade(self):
        """
        Execute a hardware fade from current colors to leds.fade_target.

        Behavior
        --------
        - Interpolates from the current pixel state to `leds.fade_target`
        in `leds.fade_steps` steps over `leds.fade_duration` seconds.
        - Writes each interpolated frame directly to the neopixel hardware.
        - Aborts early and returns if `leds.fade_active` is cleared externally
        (e.g. by the blush behaviour).
        - On completion, syncs the final state back to middleware and clears
        `leds.fade_active`.
        """
        start = [c[:] for c in self.colors]
        target = self.leds.fade_target[:]
        steps = max(1, self.leds.fade_steps)
        duration = max(0.0, self.leds.fade_duration)
        step_delay = duration / steps

        for i in range(steps + 1):
            # Check for external abort (e.g. blush behaviour cleared fade_active)
            if not self.leds.fade_active:
                return
            alpha = i / steps
            blended = [
                [
                    max(0, min(255, int(start[j][k] + (target[j][k] - start[j][k]) * alpha)))
                    for k in range(3)
                ]
                for j in range(self.leds.number)
            ]
            for idx in range(self.leds.number):
                self.pixels[idx] = blended[idx]
            self.pixels.show()
            self.colors = [c[:] for c in blended]
            time.sleep(step_delay)

        # Sync final state to middleware and clear the fade request
        self.leds.colors = [c[:] for c in target]
        self.colors = [c[:] for c in target]
        self.leds.fade_active = False

    def run(self):
        """
        Main loop.

        Behavior
        --------
        - Marks LEDs as ready in middleware.
        - On each tick, checks for a pending fade request and executes it.
        - Otherwise, detects color changes and writes them to the neopixel hardware.
        - Turns off all LEDs and shuts down node in finally block.
        """
        try:
            self.leds.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
                # Handle fade request from behaviours
                if self.leds.fade_active:
                    self.execute_fade()
                    continue
                colors = self.leds.colors[:]
                if colors != self.colors:
                    # print("writing")
                    for i in range(self.leds.number):
                        r = max(0, min(255, int(colors[i][0])))
                        g = max(0, min(255, int(colors[i][1])))
                        b = max(0, min(255, int(colors[i][2])))
                        self.pixels[i] = [r, g, b]
                    self.pixels.show()
                    self.colors = colors
        except KeyboardInterrupt:
            pass
        finally:
            for i in range(self.leds.number):
                self.pixels[i] = [0, 0, 0]
            self.pixels.show()
            self.node.shutdown()


if __name__ == "__main__":
    driver = DriverLeds()
    driver.run()
