"""

Behaviour node.

When selected and triggered, it displays the camera on the screen, 
centers the face.

Once the face is centered, the head stays on that position, 
the countdown starts and, when it ends, it takes a picture and
sends it to be printed on an INSTAX.

"""

import os
import time
import subprocess
import cv2
import requests
import numpy as np
import threading
import middleware as mw


LOOP_RATE = 10
FRAME_W = 640
FRAME_H = 480
CONFIRM_FRAMES = 3


def take_picture(mjpeg_url):
    # Send an HTTP GET request to the MJPEG stream URL
    response = requests.get(mjpeg_url, stream=True)
    if response.status_code == 200:
        stream = response.iter_content(chunk_size=1024)
        bytes = b''
        for chunk in stream:
            bytes += chunk
            a = bytes.find(b'\xff\xd8')
            b = bytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes[a:b+2]
                bytes = bytes[b+2:]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    frame = cv2.resize(frame, (480, int(frame.shape[0] / (frame.shape[1] / 480))))
                    frame = frame[0:480, :]
                    cv2.imwrite('/tmp/captured_frame.png', frame)
                    break
    else:
        print("Failed to retrieve MJPEG stream.")
    cv2.destroyAllWindows()


def print_picture(self):
    # Temporary solution since this tool needs other environment
    result = subprocess.run(
        "source /home/idmind/instax_api/instax/.venv/bin/activate && python -m instax.print -v 3 /tmp/captured_frame.png",
        shell=True, executable="/bin/bash", capture_output=True, text=True
    )
    self.node.loginfo(f"[PHOTOGRAPHER] print_picture stdout: {result.stdout}")
    self.node.loginfo(f"[PHOTOGRAPHER] print_picture stderr: {result.stderr}")
    self.node.loginfo(f"[PHOTOGRAPHER] print_picture return code: {result.returncode}")


class BehaviourPhotographer:
    def __init__(self):
        self.touch_sensors = mw.TouchSensors()
        self.onboard = mw.Onboard()
        self.camera = mw.Camera()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.leds = mw.Leds()
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()
        self.printer = mw.Printer()
        self.node = mw.Node("behaviour_photographer")

        # face detection setup, same structure as behaviour_hello.py
        self.detector = cv2.FaceDetectorYN.create('/home/idmind/elmo-v2/src/yunet.onnx', '', (FRAME_W, FRAME_H))
        self.latest_frame = None
        self.lock = threading.Lock()
        self.stream = None
        self.reader_running = False


    def start_stream(self):
        """Open the MJPEG stream and start the reader thread."""
        self.stream = cv2.VideoCapture("http://localhost:8080/stream.mjpg")
        self.reader_running = True
        t = threading.Thread(target=self.reader, daemon=True)
        t.start()
        time.sleep(1.0)
        self.node.loginfo("Stream started.")

    def stop_stream(self):
        """Stop the reader thread and release the stream."""
        self.reader_running = False
        time.sleep(0.3)
        if self.stream:
            self.stream.release()
            self.stream = None
        self.latest_frame = None
        self.node.loginfo("Stream stopped.")

    ####### 
    # these functions are the same of behaviour_hello.py 

    def reader(self):
        while self.reader_running:
            if self.stream:
                ret, frame = self.stream.read()
                if ret:
                    with self.lock:
                        self.latest_frame = frame

    def detect_face(self):
        with self.lock:
            frame = self.latest_frame
        if frame is None:
            return False, None, None
        _, faces = self.detector.detect(frame)
        if faces is None or len(faces) == 0:
            return False, None, None
        x, y, w, h = faces[0][:4]
        cx = x + w / 2
        cy = y + h / 2
        return True, cx, cy

    def track_face(self, cx, cy):
        alpha = 0.4
        if not hasattr(self, 'smooth_cx'):
            self.smooth_cx = float(cx)
            self.smooth_cy = float(cy)
        self.smooth_cx = alpha * float(cx) + (1 - alpha) * self.smooth_cx
        self.smooth_cy = alpha * float(cy) + (1 - alpha) * self.smooth_cy

        error_x = (self.smooth_cx - FRAME_W / 2) / FRAME_W
        error_y = (self.smooth_cy - FRAME_H / 2) / FRAME_H

        if abs(error_x) < 0.08:
            error_x = 0
        if abs(error_y) < 0.08:
            error_y = 0

        pan_adjust = -error_x * 80
        tilt_adjust = error_y * 60

        new_pan = float(self.pan.current_angle) + pan_adjust
        new_tilt = float(self.tilt.current_angle) + tilt_adjust

        new_pan = max(self.pan.min_angle, min(self.pan.max_angle, new_pan))
        new_tilt = max(self.tilt.min_angle, min(self.tilt.max_angle, new_tilt))

        self.pan.angle = new_pan
        self.tilt.angle = new_tilt

    #######

    # all the center face function does is basically it tracks the face until its centered
    # and returns a boolean (true or false) to if its centered or not centered, respectivelly.

    def center_face(self):
        """Track face until centered or timeout. Returns True if centered."""
        self.node.loginfo("Centering face...")
        self.pan.enable = True
        self.tilt.enable = True
        # deadline of 5 seconds, so if the face isn't centered by then, give up
        deadline = time.time() + 5.0
        consecutive = 0 # Counts how many frames in a row the face has been "close enough" to center
        while time.time() < deadline:
            # grabs a frame and attempts to detect a face and returns its center coords if found
            detected, cx, cy = self.detect_face()
            if detected:
                self.track_face(cx, cy)
                error_x = (float(cx) - FRAME_W / 2) / FRAME_W # normalize the offset from frame center to a -0.5 … +0.5 range
                error_y = (float(cy) - FRAME_H / 2) / FRAME_H
                if abs(error_x) < 0.08 and abs(error_y) < 0.08: # face is within the ±8% "centered" zone on both axes
                    consecutive += 1
                    if consecutive >= CONFIRM_FRAMES: # only declare success after CONFIRM_FRAMES stable frames in a row
                        self.node.loginfo("Face centered.")
                        return True
                else:
                    # face drifted outside the zone, reset the stability counter
                    consecutive = 0
            time.sleep(0.1)
        # deadline elapsed without achieving a stable center lock
        self.node.loginfo("Timed out centering face.")
        return False


    def countdown(self):
        """Show countdown on LEDs."""
        old_colors = self.leds.colors
        for i in range(10, -1, -1):
            icon_name = "%d.png" % i
            url = self.server.url_for_icon(icon_name)
            self.leds.load_from_url(url)
            time.sleep(1.0)
        self.leds.colors = old_colors


    def disconnect_from_printer_wifi(self):
        wifi = self.printer.wifi
        success = 0 == os.system("sudo nmcli con down id %s" % wifi)
        if success:
            self.printer.connected = False
            self.node.loginfo("Printer Disconnected")
        return success


    def connect_to_printer_wifi(self):
        wifi = self.printer.wifi
        success = 0 == os.system("sudo nmcli con up id %s" % wifi)
        if success:
            self.printer.connected = True
            self.node.loginfo("Printer Connected")
        return success

    # this is also a new function, what it does is that it calls the functions in
    # a defined sequence:
    # show stream -> center face -> countdown -> take picture -> print -> restore

    def take_photo_flow(self):
        self.node.loginfo("Photo flow started.")

        # start stream and show camera on screen
        self.start_stream()
        self.onboard.image = self.camera.url
        self.node.loginfo("Camera stream shown on screen.")
        time.sleep(1.0)

        # center face using servos
        self.center_face()

        # countdown
        self.countdown()

        # stop stream so take_picture can connect
        self.stop_stream()
        time.sleep(0.5)

        # take picture
        take_picture("http://localhost:8080/stream.mjpg")
        self.node.loginfo("Picture taken.")

        # hide camera from screen and restore normal mode
        self.onboard.image = None
        self.node.loginfo("Screen restored to normal.")

        # print
        if self.connect_to_printer_wifi():
            self.node.loginfo("Connected to printer wifi, printing picture.")
            print_picture(self)
            self.disconnect_from_printer_wifi()
        else:
            self.node.logwarn("Failed to connect to printer wifi.")
            self.camera.error = "failed to connect to printer wifi"

        # exit photographer mode
        self.behaviours.photographer = False
        self.node.loginfo("Photo flow finished. Returning to normal mode.")


    def run(self):
        try:
            self.node.loginfo("Starting behaviour.")
            touch_counter = 0
            self.disconnect_from_printer_wifi()

            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)

                if not self.behaviours.photographer:
                    touch_counter = 0
                    continue

                # photographer mode is active, wait for sensor trigger
                if self.touch_sensors.touch_chest:
                    touch_counter += 1
                    if touch_counter >= 10:
                        touch_counter = 0
                        self.camera.take_picture = False
                        self.camera.taking_picture = True
                        self.camera.error = None
                        self.take_photo_flow()
                        self.camera.taking_picture = False
                else:
                    touch_counter = 0

        finally:
            self.node.loginfo("Shutting down.")
            self.stop_stream()
            self.node.shutdown()


if __name__ == '__main__':
    node = BehaviourPhotographer()
    node.run()