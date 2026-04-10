#! /usr/bin/env python


"""

Driver node.

This node manages the microphone.

Stores captured audio to wave file called mic.wav, in the multimedia server's static resource folder.

"""

import subprocess
import time
import os

import middleware as mw


class DriverMicrophone:
    """
    Middleware driver node for microphone recording control.

    Attributes
    ----------
    node : mw.Node
        Middleware node used for status, shutdown, and logging.
    microphone : mw.Microphone
        Middleware microphone state object with recording flags.
    server : mw.Server
        Middleware server object, used for static path resolution.
    recording_process : subprocess.Popen | None
        Process handle for active audio recording command.
    microphone_target : str | None
        Optional audio capture target from `MICROPHONE_TARGET` environment variable.
    """
    def __init__(self):
        """
        Create driver middleware objects and initialize recording target.

        Side effects
        ------------
        - Connect to middleware Node, Microphone, and Server.
        - Reads the `MICROPHONE_TARGET` environment variable.
        """
        self.node = mw.Node("driver_microphone")
        self.microphone = mw.Microphone()
        self.server = mw.Server()
        self.recording_process = None
        # Get microphone target from environment or config, use None for default device
        self.microphone_target = os.environ.get("MICROPHONE_TARGET")

    def start_recording_audio(self):
        """
        Start recording audio to a file using pw-record.

        The output file is `{server.static_path}/sounds/mic.wav`.
        If `microphone_target` is set, records from that target.
        Sets `microphone.is_recording` to True.

        Returns
        -------
        None
        """
        # start recording audio using pw-record (PipeWire native)
        output_file = f"{self.server.static_path}/sounds/mic.wav"
        cmd = ["pw-record", "--format=s16", "--channels=1", "--rate=44100", output_file]
        # Add target only if specified (uses system default if not)
        if self.microphone_target:
            cmd.insert(1, "--target")
            cmd.insert(2, self.microphone_target)

        self.recording_process = subprocess.Popen(cmd)
        self.microphone.is_recording = True

    def stop_recording_audio(self):
        """
        Stop the current recording process, gracefully if possible.

        Terminates the process and waits up to 5 seconds; kills if timeout.
        Resets `microphone.is_recording` to False.

        Returns
        -------
        None
        """
        # stop recording audio #TODO Validate and handle errors, logging
        if self.recording_process:
            self.recording_process.terminate()
            try:
                self.recording_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.recording_process.kill()
                self.recording_process.wait()
            self.recording_process = None
        self.microphone.is_recording = False

    def run(self):
        """
        Main loop syncing middleware recording flags with actual recorder process.

        Behavior
        --------
        - Sets `microphone.ready` True.
        - Polls the middleware state every 0.1 second.
        - Starts/stops recording based on `microphone.record` and `microphone.is_recording`.
        - Handles KeyboardInterrupt gracefully and shuts down the middleware node in finally.
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


if __name__ == "__main__":
    driver = DriverMicrophone()
    driver.run()
