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
    """
    Middleware behaviour that greets detected faces and tracks them with the robot's head.
    Captures frames from an MJPEG stream, runs YuNet face detection, plays a greeting
    sound on first detection (with a cooldown), and servo-tracks the face using pan/tilt.
    Pauses automatically when the photographer behaviour is active.

    > ## Attributes

    ``speakers : mw.Speakers`` : Middleware speaker controller for playing greeting sounds.

    ``behaviours : mw.Behaviours`` : Middleware behaviour configuration flags, used to check photographer state.

    ``server : mw.Server`` : Middleware server helper for resolving image and sound resource URLs.

    ``node : mw.Node`` : Middleware node used for logging and shutdown signalling.

    ``pan : mw.Pan`` : Middleware pan servo controller for horizontal head movement.

    ``tilt : mw.Tilt`` : Middleware tilt servo controller for vertical head movement.

    ``detector : cv2.FaceDetectorYN`` : YuNet ONNX face detector configured for FRAME_W x FRAME_H input.

    ``stream : cv2.VideoCapture`` : MJPEG video capture connected to the local camera stream.

    ``latest_frame : numpy.ndarray or None`` : Most recent frame captured by the reader thread; None until first frame arrives.

    ``onboard : mw.Onboard`` : Middleware onboard display controller for showing reaction images.

    ``lock : threading.Lock`` : Mutex protecting access to latest_frame between the reader thread and main loop.

    ``running : bool`` : Flag used to signal the reader thread to stop when the behaviour shuts down.

    ``smooth_cx : float`` : Exponentially smoothed horizontal face centre position (set on first track call).

    ``smooth_cy : float`` : Exponentially smoothed vertical face centre position (set on first track call).

    > ## Functions
    """

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
        """
        Background thread target that continuously reads frames from the MJPEG stream
        and stores the latest one for use by the detection loop.

        Runs until ``self.running`` is set to False. Failed reads are silently skipped.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        while self.running:
            ret, frame = self.stream.read()
            if ret:
                with self.lock:
                    self.latest_frame = frame


    def detect_face(self):
        """
        Grab the latest frame and run YuNet face detection on it.

        Only the highest-confidence (first) detected face is considered.
        Returns the pixel coordinates of its centre.

        Parameters
        ----------
        None

        Returns
        -------
        detected : bool
            True if at least one face was found in the latest frame, False otherwise.
        cx : float or None
            Horizontal pixel position of the face centre; None when no face is detected.
        cy : float or None
            Vertical pixel position of the face centre; None when no face is detected.
        """
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
        """
        Update pan and tilt servo targets to keep the detected face centred in frame.

        Applies exponential smoothing (alpha=0.4) to the raw face position before
        computing the tracking error. A dead-band of ±8 % of frame width/height
        suppresses small jitter. The resulting angle adjustments are clamped to each
        servo's hardware limits before being written.

        Parameters
        ----------
        cx : float
            Horizontal pixel position of the face centre in the current frame.
        cy : float
            Vertical pixel position of the face centre in the current frame.

        Returns
        -------
        None
        """
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
        """
        Main behaviour loop.

        Enables pan and tilt servos, then polls the camera at ~10 Hz. On each tick:
        - Skips processing if the photographer behaviour is active.
        - Accumulates consecutive detection frames; after CONFIRM_FRAMES a face is
          considered present and a greeting sound is played (subject to COOLDOWN).
        - Calls track_face() every tick while a face is confirmed present.
        - After ABSENT_FRAMES consecutive misses the face is considered gone.

        Releases the video stream and shuts down the middleware node on exit (including
        on KeyboardInterrupt or any other exception).

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
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
