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

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        Connect to neopixel.
        """
        self.node = mw.Node("driver_leds")
        self.leds = mw.Leds()
        self.colors = [[0, 0, 0]] * self.leds.number
        self.pixels = neopixel.NeoPixel(board.D18, self.leds.number, brightness=self.leds.brightness, auto_write=False)
        print("brightness: %s, %s" % (self.leds.brightness, type(self.leds.brightness)))
    
    def run(self):
        """
        Main loop.
        """
        try:
            self.leds.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
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


if __name__ == '__main__':
    driver = DriverLeds()
    driver.run()
