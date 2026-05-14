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
    Hardware driver for the microphone.

    Manages audio capture via the PipeWire native ``pw-record`` utility.
    Monitors the middleware recording flag and starts or stops the
    recording subprocess accordingly. Captured audio is written as a
    16-bit mono 44100 Hz WAV file to the multimedia server's static
    sounds folder.

    > ## Attributes
    ``node : mw.Node`` : Middleware node used for shutdown signalling and logging.
    ``microphone : mw.Microphone`` : Middleware microphone state object containing the ``record`` request flag and the ``is_recording`` status flag.
    ``server : mw.Server`` : Middleware server object used to resolve the static resource path for the output WAV file.
    ``recording_process : subprocess.Popen or None`` : Handle to the active ``pw-record`` subprocess, or ``None`` when not recording.
    ``microphone_target : str or None`` : PipeWire target device name read from the ``MICROPHONE_TARGET`` environment variable; ``None`` causes ``pw-record`` to use the system default device.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.

        Instantiates the middleware node, microphone, and server objects.
        Reads the optional ``MICROPHONE_TARGET`` environment variable to
        allow overriding the PipeWire capture device at runtime.
        """
        self.node = mw.Node("driver_microphone")
        self.microphone = mw.Microphone()
        self.server = mw.Server()
        self.recording_process = None
        # Get microphone target from environment or config, use None for default device
        self.microphone_target = os.environ.get("MICROPHONE_TARGET")

    def start_recording_audio(self):
        """
        Start recording audio using the PipeWire native ``pw-record`` utility.

        Constructs the output path as ``<server.static_path>/sounds/mic.wav``
        and launches ``pw-record`` as a background subprocess configured for
        16-bit signed PCM, mono, at 44100 Hz. If ``microphone_target`` is set,
        it is passed as the ``--target`` argument so that a specific PipeWire
        source device is used. Sets ``microphone.is_recording`` to ``True``
        once the process is started.
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
        Stop the active audio recording subprocess.

        Sends ``SIGTERM`` to the ``pw-record`` process and waits up to 5
        seconds for it to exit cleanly. If the process does not terminate
        within the timeout it is forcibly killed with ``SIGKILL``. Clears
        ``recording_process`` and sets ``microphone.is_recording`` to
        ``False`` once the process has stopped.
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
        Main loop.

        Marks the microphone subsystem as ready in middleware, then polls
        at 10 Hz until shutdown is requested. On each tick:

        - If ``microphone.record`` is set and no recording is active,
          calls ``start_recording_audio()``.
        - If ``microphone.record`` is cleared and a recording is active,
          calls ``stop_recording_audio()``.

        The node is shut down cleanly in the ``finally`` block regardless
        of the exit path.
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
