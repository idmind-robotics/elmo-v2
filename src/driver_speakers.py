#! /usr/bin/env python


"""

Driver node.

This node manages the speakers.

Uses the aplay command to play sounds.

"""

import os
import multiprocessing
import time
import middleware as mw



class DriverSpeakers:

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.speakers = mw.Speakers()
        self.volume = 0
        self.node = mw.Node("driver_speakers")
        self.process = None

    def play_sound(self, url):
        """
        Play a sound.
        """
        self.speakers.playing = url
        print(f'playing {url}')
        os.system(f'/usr/bin/curl {url} | /usr/bin/aplay')
        self.speakers.url = None
        self.speakers.playing = None
    
    def stop_sound(self):
        """
        Stop playing a sound, by killing the aplay process.
        """
        print(f'stopping')
        os.system("/usr/bin/killall aplay")

    def run(self):
        """
        Main loop.
        """
        try:
            self.speakers.ready = True
            while not self.node.is_shutdown():
                time.sleep(0.1)
                url = self.speakers.url
                playing = self.speakers.playing
                volume = self.speakers.volume
                # play sound
                if url != playing:
                    self.stop_sound()
                    self.process = multiprocessing.Process(target=self.play_sound, args=(url,))
                    self.process.start()
                # stop sound
                if playing and url is None:
                    self.stop_sound()
                    self.speakers.playing = None
                # change volume
                if self.volume != volume:
                    if 0 == os.system(f'/usr/bin/amixer sset "Master" {volume}%'):
                        self.volume = volume
        finally:
            self.stop_sound()
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverSpeakers()
    node.run()
