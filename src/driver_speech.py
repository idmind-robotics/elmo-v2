#!/usr/bin/env python


"""

Driver node.

This node manages speech.

Uses the gtts-cli command to generate speech and the aplay command to play it.

gtts-cli is a command line interface to the Google Text-to-Speech API.

Internet connection is required.

"""


import os
import time

import middleware as mw


class DriverSpeech:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.speech = mw.Speech()
        self.node = mw.Node("driver_speech")
    
    def speak(self, language, text):
        """
        Speak a text.
        """
        command = '/usr/bin/rm -f /tmp/f.mp3 /tmp/f.wav && /home/idmind/.local/bin/gtts-cli -l %s "%s" --output /tmp/f.mp3 && /usr/bin/ffmpeg -i /tmp/f.mp3 /tmp/f.wav && /usr/bin/aplay /tmp/f.wav && /usr/bin/rm -f /tmp/f.mp3 /tmp/f.wav' % (language, text)
        os.system(command)
        self.speech.saying = ""
        self.speech.say = ""    

    def run(self):
        """
        Main loop.
        """
        try:
            self.speech.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.speech.saying != self.speech.say:
                    self.speech.saying = self.speech.say
                    self.speak(self.speech.language, self.speech.say)
        except KeyboardInterrupt:
            pass
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverSpeech()
    node.run()