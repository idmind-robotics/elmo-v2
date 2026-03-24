"""

Behaviour node.

When a face shows up on the camera, the robot says "Hello" through a .wav file.

Also, when the face moves, the robot's head turns and follows it.

"""


import time
import cv2
import middleware as mw
import threading


COOLDOWN = 8.0
CONFIRM_FRAMES = 3
ABSENT_FRAMES = 3
FRAME_W = 640
FRAME_H = 480


class BehaviourHello:

    def __init__(self):
        self.speakers = mw.Speakers()
        self.behaviours = mw.Behaviours()
        self.server = mw.Server()
        self.node = mw.Node("behaviour_hello")
        self.pan = mw.Pan()
        self.tilt = mw.Tilt()
        self.detector = cv2.FaceDetectorYN.create('/home/idmind/elmo-v2/src/yunet.onnx', '', (FRAME_W, FRAME_H))
        self.stream = cv2.VideoCapture("http://localhost:8080/stream.mjpg")
        self.latest_frame = None
        self.onboard = mw.Onboard()
        self.lock = threading.Lock()
        self.running = True
        t = threading.Thread(target=self.reader, daemon=True)
        t.start()
        time.sleep(2)
        self.node.loginfo("Camera ready.")


    def reader(self):
        while self.running:
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


    def run(self):
        self.node.loginfo("Behaviour started.")
        face_detected = False
        last_greeted = 0
        consecutive = 0
        absent = 0

        # enable motors on startup
        self.pan.enable = True
        self.tilt.enable = True

        try:
            while not self.node.is_shutdown():
                time.sleep(0.1)
                now = time.time()

                # pause when photographer is active
                if self.behaviours.photographer:
                    face_detected = False
                    consecutive = 0
                    time.sleep(0.5)
                    continue

                detected, cx, cy = self.detect_face()

                if detected:
                    consecutive += 1
                    absent = 0
                    if consecutive >= CONFIRM_FRAMES and not face_detected:
                        face_detected = True
                        if now - last_greeted > COOLDOWN:
                            self.node.loginfo("Face detected.")
                            image_url = self.server.url_for_image("happy.png")
                            self.onboard.image = image_url
                            # selects one of the three files and plays that sound.
                            sounds = ['hello.wav', 'hello2.wav', 'hello3.wav']
                            chosen = sounds[int(time.time()) % len(sounds)]
                            self.node.loginfo(f"Face detected - playing {chosen}")
                            self.speakers.url = self.server.url_for_sound(chosen)
                            time.sleep(3.0)
                            image_url = self.server.url_for_image("normal.png")
                            self.onboard.image = image_url
                            last_greeted = now
                    if face_detected:
                        self.track_face(cx, cy)
                else:
                    absent += 1
                    consecutive = 0
                    if absent >= ABSENT_FRAMES and face_detected:
                        self.node.loginfo("Face gone.")
                        face_detected = False
        finally:
            self.running = False
            self.stream.release()
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourHello()
    node.run()