

"""

Driver node.

This node manages the speakers.

Uses the aplay command to play sounds.

"""

import subprocess
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
        self.playback_process = None

    def play_sound(self, url):
        """
        Play a sound.
        """
        self.speakers.playing = url
        print(f'playing {url}')
        try:
            # Stream audio from URL and play with pw-play
            curl_process = subprocess.Popen(
                ['/usr/bin/curl', url],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            self.playback_process = subprocess.Popen(
                ['pw-play', '-'],
                stdin=curl_process.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            curl_process.stdout.close()  # Allow curl to receive SIGPIPE if pw-play exits
            self.playback_process.wait()
        except Exception as e:
            print(f"Error playing sound: {e}")
        finally:
            self.speakers.url = None
            self.speakers.playing = None
    
    def stop_sound(self):
        """
        Stop playing a sound.
        """
        print(f'stopping')
        if self.playback_process:
            self.playback_process.terminate()
            try:
                self.playback_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.playback_process.kill()
                self.playback_process.wait()
            self.playback_process = None

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
                    try:
                        # Use pw-cli to set master volume
                        result = subprocess.run([
                            'pw-cli',
                            'set-param',
                            '33',  # Master node ID (typically 33, may vary)
                            'Props',
                            '{{ volume: {} }}'.format(volume / 100.0)
                        ], capture_output=True, text=True)
                        if result.returncode == 0:
                            self.volume = volume
                    except Exception as e:
                        print(f"Error setting volume: {e}")
        finally:
            self.stop_sound()
            self.node.shutdown()


if __name__ == '__main__':
    node = DriverSpeakers()
    node.run()
