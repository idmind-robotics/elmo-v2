import os
import time
import cv2
import requests
import re
import numpy as np
import subprocess
from pyzbar.pyzbar import decode


import middleware as mw


LOOP_RATE = 10


class BehaviourWifiConnect:
    def __init__(self):
        self.onboard = mw.Onboard()
        self.camera = mw.Camera()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.leds = mw.Leds()
        self.node = mw.Node("behaviour_wifi_connect")
        self.look_around_was_enabled = False
        self.conversation_was_enabled = False

    def show_stream(self):
        self.look_around_was_enabled = self.behaviours.look_around
        self.behaviours.look_around = False
        self.conversation_was_enabled = self.behaviours.conversation
        time.sleep(2.0)
        self.onboard.image = self.camera.url

    def hide_stream(self):
        self.onboard.image = None
        time.sleep(1.0)
        if self.look_around_was_enabled:
            self.behaviours.look_around = True
        if self.conversation_was_enabled:
            self.behaviours.conversation = True

    def parse_wifi_qr(self, qr_string):
        # Ensure it follows the WIFI QR code format
        if not qr_string.startswith("WIFI:") or not qr_string.endswith(";;"):
            raise ValueError("Invalid WiFi QR code format")

        # Remove leading "WIFI:" and trailing ";;"
        qr_string = qr_string[5:-2]

        # Regex to capture fields (handling escaped characters)
        pattern = r"(S|T|P|H):((?:\\.|[^;])*);?"
        matches = re.findall(pattern, qr_string)

        wifi_details = {"S": "", "T": "nopass", "P": "", "H": "false"}  # Defaults

        for key, value in matches:
            wifi_details[key] = value.replace("\\;", ";").replace(
                "\\:", ":"
            )  # Unescaping

        return wifi_details["S"], wifi_details["P"]

    def try_connect_to_wifi(self, ssid, password):
        print("Connecting to WiFi network %s. Password: %s" % (ssid, password))
        try:
            result = subprocess.run(
                ["sudo", "nmcli", "dev", "wifi", "rescan"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, result.stderr
            time.sleep(5.0)
            result = subprocess.run(
                ["sudo", "nmcli", "dev", "wifi", "connect", ssid, "password", password],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, result.stderr
            result = subprocess.run(
                ["sudo", "nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.splitlines():
                if line.startswith("yes:"):
                    return True, line.split(":")[1]
            return False, "Failed to connect to WiFi network"
        except subprocess.CalledProcessError as e:
            error_message = "Failed to connect to WiFi network: %s" % e
            return False, error_message

    def run(self):
        try:
            self.node.loginfo("starting behaviour")
            was_enabled = False
            behaviour_test_motors_was_enabled = False
            behaviour_look_around_was_enabled = False
            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)
                if self.behaviours.wifi_connect and not was_enabled:
                    behaviour_test_motors_was_enabled = self.behaviours.test_motors
                    behaviour_look_around_was_enabled = self.behaviours.look_around
                    self.behaviours.test_motors = False
                    self.show_stream()
                    was_enabled = True
                elif not self.behaviours.wifi_connect and was_enabled:
                    if behaviour_test_motors_was_enabled:
                        self.behaviours.test_motors = True
                    if behaviour_look_around_was_enabled:
                        self.behaviours.look_around = True
                    self.hide_stream()
                    was_enabled = False
                if self.behaviours.wifi_connect:
                    stream_url = self.camera.url
                    cap = cv2.VideoCapture(stream_url)
                    ret, frame = cap.read()
                    if ret:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        qr_codes = decode(gray)
                        if len(qr_codes) == 0:
                            print("No QR codes detected")
                        for qr_code in qr_codes:
                            decoded = qr_code.data.decode("utf-8")
                            print(f"QR Code data: {decoded}")
                            if "WIFI" in decoded:
                                self.onboard.image = None
                                self.onboard.text = "Connecting to WiFi network..."
                                ssid, password = self.parse_wifi_qr(decoded)
                                success, message = self.try_connect_to_wifi(
                                    ssid, password
                                )
                                if success:
                                    self.onboard.image = None
                                    self.onboard.text = f"Connected to {message}"
                                    time.sleep(3.0)
                                    self.onboard.text = None
                                    self.behaviours.wifi_connect = False
                                    break
                                else:
                                    self.onboard.image = None
                                    self.onboard.text = message
                                    time.sleep(3.0)
                                    self.onboard.text = None
                                    self.show_stream()
                                    break

                    cap.release()

        finally:
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourWifiConnect()
    node.run()
