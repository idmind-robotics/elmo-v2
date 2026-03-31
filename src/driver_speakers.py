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
    """
    Middleware driver node for audio playback control.

    Attributes
    ----------
    speakers : mw.Speakers
        Middleware speakers state object with `url`, `playing`, `volume`, `ready`.
    volume : int
        Last applied volume level (0-100).
    node : mw.Node
        Middleware node for shutdown and logging.
    process : multiprocessing.Process | None
        Worker process created to run `play_sound`.
    playback_process : subprocess.Popen | None
        Child process for streaming and playback (`pw-play`).
    """
    def __init__(self):
        """
        Initialize middleware speaker state and node.
        """
        self.speakers = mw.Speakers()
        self.volume = 0
        self.node = mw.Node("driver_speakers")
        self.process = None
        self.playback_process = None

    def play_sound(self, url):
        """
        Stream and play an audio URL using pw-play.

        Parameters
        ----------
        url : str
            Remote media URL to play.

        Returns
        -------
        None

        Side effects
        ------------
        - Sets `self.speakers.playing` to url.
        - Runs `curl` piped into `pw-play`.
        - Resets `self.speakers.url` and `self.speakers.playing` to None on completion.
        """
        self.speakers.playing = url
        print(f"playing {url}")
        try:
            # Stream audio from URL and play with pw-play
            curl_process = subprocess.Popen(
                ["/usr/bin/curl", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self.playback_process = subprocess.Popen(
                ["pw-play", "-"],
                stdin=curl_process.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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
        Stop the current playback process if running.

        Returns
        -------
        None

        Side effects
        ------------
        - Attempts graceful termination of `pw-play` process.
        - Kills it if it does not exit within 2 seconds.
        """
        print(f"stopping")
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
        Main loop that syncs middleware sound state to playback/volume.

        Behavior
        --------
        - Sets `speakers.ready` True.
        - Checks `speakers.url` and `speakers.playing` every 0.1 second.
        - Starts new playback process when URL changes.
        - Stops audio when `speakers.url` becomes None.
        - Adjusts PipeWire master volume when `speakers.volume` changes.
        - Ensures sound is stopped and node is shutdown in finally.
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
                    self.process = multiprocessing.Process(
                        target=self.play_sound, args=(url,)
                    )
                    self.process.start()
                # stop sound
                if playing and url is None:
                    self.stop_sound()
                    self.speakers.playing = None
                # change volume
                if self.volume != volume:
                    try:
                        # Use pw-cli to set master volume
                        result = subprocess.run(
                            [
                                "pw-cli",
                                "set-param",
                                "33",  # Master node ID (typically 33, may vary)
                                "Props",
                                "{{ volume: {} }}".format(volume / 100.0),
                            ],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            self.volume = volume
                    except Exception as e:
                        print(f"Error setting volume: {e}")
        finally:
            self.stop_sound()
            self.node.shutdown()


if __name__ == "__main__":
    node = DriverSpeakers()
    node.run()
