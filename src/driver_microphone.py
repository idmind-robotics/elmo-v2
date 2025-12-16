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

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.node = mw.Node("driver_microphone")
        self.microphone = mw.Microphone()
        self.server = mw.Server()
        self.recording_process = None
        # Get microphone target from environment or config, use None for default device
        self.microphone_target = os.environ.get("MICROPHONE_TARGET")
    
    def start_recording_audio(self):
        # start recording audio using pw-record (PipeWire native)
        output_file = f"{self.server.static_path}/sounds/mic.wav"
        cmd = [
            "pw-record",
            "--format=s16",
            "--channels=1",
            "--rate=44100",
            output_file
        ]
        # Add target only if specified (uses system default if not)
        if self.microphone_target:
            cmd.insert(1, "--target")
            cmd.insert(2, self.microphone_target)
        
        self.recording_process = subprocess.Popen(cmd)
        self.microphone.is_recording = True
    
    def stop_recording_audio(self):
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


if __name__ == '__main__':
    driver = DriverMicrophone()
    driver.run()
