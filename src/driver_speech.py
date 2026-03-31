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
    """
    Middleware driver node for text-to-speech playback.

    Attributes
    ----------
    speech : mw.Speech
        Middleware speech state object with `say`, `saying`, `language`, `ready`.
    node : mw.Node
        Middleware node for shutdown and logging.
    temp_dir : str
        Temporary directory for generated audio files.
    playback_process : subprocess.Popen | None
        Active playback process for `pw-play`.
    """
    def __init__(self):
        """
        Initialize middleware objects and_temp directory.
        """
        self.speech = mw.Speech()
        self.node = mw.Node("driver_speech")
        self.temp_dir = tempfile.gettempdir()
        self.playback_process = None

    def speak(self, language, text):
        """
        Convert text to speech and play it.

        Parameters
        ----------
        language : str
            Language code (e.g., "en") passed to gtts-cli.
        text : str
            Text to speak.

        Returns
        -------
        None

        Side effects
        ------------
        - Writes temporary files `speech.mp3` and `speech.wav` in `temp_dir`.
        - Calls `gtts-cli` to synthesize speech and `ffmpeg` to transcode MP3 to WAV.
        - Plays audio via `pw-play`.
        - Deletes temporary files after playback.
        - Resets `speech.saying` and `speech.say` to "".
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
        Main loop that triggers speech when requested.

        Behavior
        --------
        - Sets `speech.ready` True.
        - Polls every 0.1 seconds.
        - If `speech.say` differs from `speech.saying`, updates `speech.saying`
          and calls `speak`.
        - Stops cleanly on KeyboardInterrupt and shuts down middleware node.

        Returns
        -------
        None
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
