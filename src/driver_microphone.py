#! /usr/bin/env python


"""

Driver node.

This node manages the microphone.

Stores captured audio to wave file called mic.wav, in the multimedia server's static resource folder.

"""


import os
import time

import middleware as mw


class DriverMicrophone:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.node = mw.Node("driver_microphone")
        self.microphone = mw.Microphone()
        self.server = mw.Server()
    
    def start_recording_audio(self):
        # start recording audio using arecord
        os.system("arecord -f cd %s/sounds/mic.wav &" % self.server.static_path)
        self.microphone.is_recording = True
    
    def stop_recording_audio(self):
        # stop recording audio
        os.system("killall arecord")
        self.microphone.is_recording = False
    
    def run(self):
        """
        Main loop.
        """
        try:
            self.microphone.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.microphone.record and not self.microphone.is_recording:
                    self.start_recording_audio()
                elif not self.microphone.record and self.microphone.is_recording:
                    self.stop_recording_audio()
        except KeyboardInterrupt:
            pass
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    driver = DriverMicrophone()
    driver.run()
