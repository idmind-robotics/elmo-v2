"""

Driver node.

This node manages the speakers.

Uses the aplay command to play sounds.

"""

import subprocess
import threading
import time
import middleware as mw


class DriverSpeakers:
    """
    Middleware driver that plays audio through speakers using aplay and sox.

    > ## Attributes

    ``speakers : mw.Speakers`` : Middleware speaker state holder.

    ``volume : int`` : Local volume cache updated from middleware.

    ``node : mw.Node`` : Middleware node used for shutdown and logging.

    ``playback_thread : threading.Thread or None`` : Background thread for audio playback.

    ``playback_process : subprocess.Popen or None`` : aplay subprocess handle.

    ``curl_process : subprocess.Popen or None`` : curl subprocess handle for fetching audio.

    ``sox_process : subprocess.Popen or None`` : sox subprocess handle for volume control.

    > ## Functions
    """

    def __init__(self):
        """
        Initialize middleware objects and driver node.

        Behavior
        --------
        - Initializes all subprocess handles to None.
        - Sets initial local volume to 0.
        """
        self.speakers = mw.Speakers()
        self.volume = 0
        self.node = mw.Node("driver_speakers")
        self.playback_thread = None
        self.playback_process = None
        self.curl_process = None
        self.sox_process = None

    def play_sound(self, url):
        """
        Play audio from a URL through the speakers.

        Behavior
        --------
        - Fetches audio file via curl.
        - Applies volume control via sox (converts 0-99 to 0.0-1.0 scale).
        - Plays through aplay targeting hardware device plughw:2,0.
        - Logs any stderr output from subprocess commands.
        - Clears middleware URL and playing fields when complete.

        Parameters
        ----------
        url : str
            HTTP URL of the audio file to play.
        """
        self.speakers.playing = url
        self.node.loginfo(f"Playing {url}")
        try:
            # convert volume 0-99 to 0.0-1.0 for sox
            vol = max(0.0, min(1.0, self.speakers.volume / 99.0))
            self.curl_process = subprocess.Popen(
                ["/usr/bin/curl", "-s", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.sox_process = subprocess.Popen(
                ["sox", "-t", "wav", "-", "-t", "wav", "-", "vol", str(vol)],
                stdin=self.curl_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.playback_process = subprocess.Popen(
                ["aplay", "-D", "plughw:2,0"],
                stdin=self.sox_process.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.curl_process.stdout.close()
            self.sox_process.stdout.close()
            self.playback_process.wait()

            if stderr := self.playback_process.stderr.read():
                self.node.logerror(f"aplay: {stderr.decode().strip()}")
            if stderr := self.curl_process.stderr.read():
                self.node.logerror(f"curl: {stderr.decode().strip()}")
        except OSError as e:
            self.node.logerror(f"Error playing sound: {e}")
        finally:
            self.speakers.url = None
            self.speakers.playing = None

    def stop_sound(self):
        """
        Stop audio playback immediately.

        Behavior
        --------
        - Terminates all active subprocesses (aplay, sox, curl).
        - Kills any remaining aplay or curl processes via pkill.
        - Clears middleware playing field.
        """
        print("stopping")
        if self.playback_process and self.playback_process.poll() is None:
            self.playback_process.terminate()
        if self.sox_process and self.sox_process.poll() is None:
            self.sox_process.terminate()
        if self.curl_process and self.curl_process.poll() is None:
            self.curl_process.terminate()
        subprocess.run(["pkill", "-f", "aplay.*Lite"], capture_output=True)
        subprocess.run(["pkill", "-f", "curl.*sounds"], capture_output=True)
        self.speakers.playing = None

    def run(self):
        """
        Main driver loop.

        Behavior
        --------
        - Marks speaker driver as ready in middleware.
        - Polls every 100ms for URL changes in middleware.
        - Starts new playback thread when URL changes from current playing state.
        - Stops playback when URL is cleared while audio is playing.
        - Updates local volume cache from middleware.
        - Always stops playback and shuts down node in finally block.
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
                    self.playback_thread = threading.Thread(
                        target=self.play_sound, args=(url,), daemon=True
                    )
                    self.playback_thread.start()
                # stop sound
                if playing and url is None:
                    self.stop_sound()
                    self.speakers.playing = None
                # update local volume (applied per play via sox)
                if self.volume != volume:
                    self.volume = volume
        finally:
            self.stop_sound()
            self.node.shutdown()


if __name__ == "__main__":
    node = DriverSpeakers()
    node.run()
