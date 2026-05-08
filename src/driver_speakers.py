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
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
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
        Play a sound.
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
        Stop playing a sound immediately.
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
