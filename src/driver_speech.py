"""

Driver node.

This node manages speech.

Uses the gtts-cli command to generate speech and the aplay command to play it.

gtts-cli is a command line interface to the Google Text-to-Speech API.

Internet connection is required.

"""

import subprocess
import time
import os
import tempfile

import middleware as mw


class DriverSpeech:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.speech = mw.Speech()
        self.node = mw.Node("driver_speech")
        self.temp_dir = tempfile.gettempdir()
        self.playback_process = None

    def speak(self, language, text):
        """
        Speak a text.
        """
        mp3_file = os.path.join(self.temp_dir, "speech.mp3")
        wav_file = os.path.join(self.temp_dir, "speech.wav")

        try:
            # Generate speech using gtts-cli
            subprocess.run(
                [
                    "/home/idmind/.local/bin/gtts-cli",
                    "-l",
                    language,
                    text,
                    "--output",
                    mp3_file,
                ],
                check=True,
                capture_output=True,
            )

            # Convert MP3 to WAV using ffmpeg
            subprocess.run(
                [
                    "/usr/bin/ffmpeg",
                    "-i",
                    mp3_file,
                    "-y",  # Overwrite output file
                    wav_file,
                ],
                check=True,
                capture_output=True,
            )

            # Play using pw-play (PipeWire native)
            self.playback_process = subprocess.Popen(["pw-play", wav_file])
            self.playback_process.wait()

        except subprocess.CalledProcessError as e:
            print(f"Error during speech playback: {e}")
        finally:
            # Clean up temp files
            for file in [mp3_file, wav_file]:
                try:
                    os.remove(file)
                except FileNotFoundError:
                    pass

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


if __name__ == "__main__":
    node = DriverSpeech()
    node.run()
