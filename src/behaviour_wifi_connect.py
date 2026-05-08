import time
import re
import socket
import logging
import subprocess
import numpy as np
import cv2
from pyzbar.pyzbar import decode


import middleware as mw


# suppress warnings from this process (e.g. from imported libraries)
logging.disable(logging.WARNING)

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

    def read_frame(self):
        """Read a single frame from the MJPEG server using a raw socket + Content-Length."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("127.0.0.1", 8080))
            sock.sendall(b"GET /stream.mjpg HTTP/1.0\r\nHost: 127.0.0.1:8080\r\nConnection: close\r\n\r\n")
            buf = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                cl_idx = buf.find(b"Content-Length:")
                if cl_idx == -1:
                    continue
                end = buf.find(b"\r\n", cl_idx)
                if end == -1:
                    continue
                length = int(buf[cl_idx + 15:end].strip())
                sep = buf.find(b"\r\n\r\n", cl_idx)
                if sep == -1:
                    continue
                data_start = sep + 4
                if len(buf) < data_start + length:
                    continue
                jpg = buf[data_start:data_start + length]
                sock.close()
                return cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            sock.close()
        except Exception:
            pass
        return None

    def detect_qr(self, frame):
        """Try WeChat QR detector (handles circular/stylized dots) then fall back to pyzbar."""
        # WeChat detector — handles fancy QR codes with circular dots
        try:
            detector = cv2.wechat_qrcode_WeChatQRCode()
            texts, _ = detector.detectAndDecode(frame)
            if texts:
                class QR:
                    def __init__(self, text):
                        self.data = text.encode("utf-8")
                return [QR(t) for t in texts if t]
        except Exception:
            pass

        # fallback: pyzbar with multiple preprocessings
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray2x = cv2.resize(gray, None, fx=2, fy=2)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])

        candidates = [
            gray, gray2x,
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            cv2.threshold(gray2x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            clahe.apply(gray), clahe.apply(gray2x),
            cv2.filter2D(gray, -1, kernel), cv2.filter2D(gray2x, -1, kernel),
            cv2.bitwise_not(gray),
            cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
            cv2.adaptiveThreshold(gray2x, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
        ]
        for img in candidates:
            result = decode(img)
            if result:
                return result
        return []

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
        if not qr_string.startswith("WIFI:"):
            raise ValueError("Invalid WiFi QR code format")

        # Remove leading "WIFI:" and any trailing semicolons
        qr_string = qr_string[5:].rstrip(";")

        # Regex to capture fields (handling escaped characters)
        pattern = r"(S|T|P|H):((?:\\.|[^;])*);?"
        matches = re.findall(pattern, qr_string)

        wifi_details = {"S": "", "T": "nopass", "P": "", "H": "false"}  # Defaults

        for key, value in matches:
            wifi_details[key] = value.replace("\\;", ";").replace(
                "\\:", ":"
            )  # Unescaping

        return wifi_details["S"], wifi_details["P"], wifi_details["T"]

    def try_connect_to_wifi(self, ssid, password, security_type):
        print("Connecting to WiFi network %s" % ssid)
        try:
            # if already connected to this SSID, return success immediately
            result = subprocess.run(
                ["sudo", "nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True,
            )
            for line in result.stdout.splitlines():
                if line.startswith("yes:") and line.split(":")[1] == ssid:
                    return True, ssid

            result = subprocess.run(
                ["sudo", "nmcli", "dev", "wifi", "rescan"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                return False, result.stderr
            time.sleep(5.0)

            # open networks don't use a password
            if security_type in ("nopass", ""):
                cmd = ["sudo", "nmcli", "dev", "wifi", "connect", ssid]
            else:
                cmd = ["sudo", "nmcli", "dev", "wifi", "connect", ssid, "password", password]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False, result.stderr

            result = subprocess.run(
                ["sudo", "nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True,
            )
            for line in result.stdout.splitlines():
                if line.startswith("yes:"):
                    connected_ssid = line.split(":")[1]
                    # delete the saved profile immediately so it doesn't persist
                    subprocess.run(
                        ["sudo", "nmcli", "connection", "delete", ssid],
                        capture_output=True, text=True,
                    )
                    return True, connected_ssid
            return False, "Failed to connect to WiFi network"
        except subprocess.CalledProcessError as e:
            return False, "Failed to connect to WiFi network: %s" % e

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
                    frame = self.read_frame()
                    if frame is None:
                        print("codigo QR nao detetado")
                        continue
                    qr_codes = self.detect_qr(frame)
                    if not qr_codes:
                        print("codigo QR nao detetado")
                        continue
                    print("codigo QR detetado")
                    for qr_code in qr_codes:
                        decoded = qr_code.data.decode("utf-8")
                        if "WIFI" in decoded:
                            self.onboard.image = None
                            self.onboard.text = "Connecting to WiFi network..."
                            ssid, password, security_type = self.parse_wifi_qr(decoded)
                            success, message = self.try_connect_to_wifi(ssid, password, security_type)
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
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourWifiConnect()
    node.run()
