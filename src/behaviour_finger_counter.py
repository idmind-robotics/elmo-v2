"""

Behaviour node.

Detects the number of fingers being held up (1 to 5)
and prints the result to the terminal in real time.

Uses MediaPipe HandLandmarker for accurate finger joint detection.

REQUIRES: Python 3.11 or 3.12, mediapipe installed.

"""

import time
import cv2
import mediapipe as mp
import threading

import middleware as mw


FRAME_W = 640
FRAME_H = 480
LOOP_RATE = 10


class BehaviourFingerCounter:
    """
    Middleware behaviour that counts raised fingers in real time using MediaPipe.

    Runs MediaPipe HandLandmarker in live stream mode with a background thread
    continuously reading camera frames. Counts fingers by comparing landmark
    positions and prints count changes to terminal.

    > ## Attributes

    ``node : mw.Node`` : Middleware node used for shutdown and logging.

    ``result : mp.tasks.vision.HandLandmarkerResult or None`` : Most recent hand landmark result from the MediaPipe callback.

    ``lock_result : threading.Lock`` : Lock protecting concurrent access to result.

    ``landmarker : mp.tasks.vision.HandLandmarker`` : MediaPipe hand landmarker running in live stream mode.

    ``stream : cv2.VideoCapture`` : MJPEG camera stream used as the video source.

    ``latest_frame : numpy.ndarray or None`` : Most recent frame captured from the camera stream.

    ``lock_frame : threading.Lock`` : Lock protecting concurrent access to latest_frame.

    ``running : bool`` : Controls the camera reader thread loop.

    > ## Functions
    """

    def __init__(self):
        """
        Initialize middleware node, MediaPipe hand landmarker, and camera stream.
        """
        self.node = mw.Node("behaviour_finger_counter")
        self.lock_frame = threading.Lock()
        self.lock_result = threading.Lock()
        self.stream = cv2.VideoCapture("http://localhost:8080/stream.mjpg")
        self.latest_frame = None
        self.result = None
        self.running = True
        t = threading.Thread(target=self.reader, daemon=True)
        t.start()
        time.sleep(2)
        self.node.loginfo("Camera ready.")

        # output_image and timestamp_ms are required by the callback of MediaPipe. If removed:
        # TypeError: update_result() missing 2 required positional arguments: 'output_image' and 'timestamp_ms'

        def update_result(result, output_image, timestamp_ms):
            with self.lock_result:
                self.result = result

        self.landmarker = mp.tasks.vision.HandLandmarker.create_from_options(
            mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path="/home/idmind/elmo-v2/src/hand_landmarker.task"
                ),
                running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
                num_hands=1,
                min_hand_detection_confidence=0.3,
                min_hand_presence_confidence=0.3,
                min_tracking_confidence=0.3,
                result_callback=update_result,
            )
        )

    def reader(self):
        """
        Background thread that continuously reads frames from the camera stream.

        Behavior
        --------
        - Reads frames from the MJPEG stream in a tight loop.
        - Stores the latest successfully decoded frame in `latest_frame`.
        - Runs until `running` is set to False.
        """
        while self.running:
            ret, frame = self.stream.read()
            if ret:
                with self.lock_frame:
                    self.latest_frame = frame

    def finger_counter(self, hand_landmarks):
        """
        Count raised fingers from a set of hand landmarks.

        Behavior
        --------
        - For the four fingers (index, middle, ring, pinky): a finger is raised
        if its tip y-coordinate is above all three joints below it.
        - For the thumb: uses x-coordinate comparison relative to palm orientation
        to detect whether the tip is extended.

        Parameters
        ----------
        hand_landmarks : list
            List of 21 normalized hand landmark objects from MediaPipe.

        Returns
        -------
        int
            Number of raised fingers (0–5).
        """
        count = 0

        # four fingers — tip is higher (smaller y) than all joints below it
        for tip_idx in [8, 12, 16, 20]:
            tip_y = hand_landmarks[tip_idx].y
            dip_y = hand_landmarks[tip_idx - 1].y
            pip_y = hand_landmarks[tip_idx - 2].y
            mcp_y = hand_landmarks[tip_idx - 3].y
            if tip_y < min(dip_y, pip_y, mcp_y):
                count += 1

        # thumb — use x position
        tip_x = hand_landmarks[4].x
        dip_x = hand_landmarks[3].x
        pip_x = hand_landmarks[2].x
        mcp_x = hand_landmarks[1].x
        palm_x = hand_landmarks[0].x
        if mcp_x > palm_x:
            if tip_x > max(dip_x, pip_x, mcp_x):
                count += 1
        else:
            if tip_x < min(dip_x, pip_x, mcp_x):
                count += 1

        return count

    def run(self):
        """
        Main behaviour loop.

        Behavior
        --------
        - Logs startup.
        - Polls at `LOOP_RATE` for new camera frames.
        - Sends each frame asynchronously to the MediaPipe landmarker.
        - Reads the latest landmark result and counts raised fingers.
        - Prints the finger count to the terminal only when it changes.
        - Prints "No hand detected." when no hand is visible.
        - Stops the camera reader, releases resources, and shuts down the node
        in the finally block.
        """
        self.node.loginfo("Behaviour started.")
        last_count = None

        try:
            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)

                with self.lock_frame:
                    frame = self.latest_frame
                if frame is None:
                    continue

                # send frame to mediapipe
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                self.landmarker.detect_async(mp_image, int(time.time() * 1000))

                # read latest result
                with self.lock_result:
                    result = self.result

                if result is None or not result.hand_landmarks:
                    if last_count is not None:
                        self.node.loginfo("No hand detected.")
                        last_count = None
                    continue

                count = self.finger_counter(result.hand_landmarks[0])

                if count != last_count:
                    self.node.loginfo(f"Fingers lifted: {count}")
                    last_count = count

        finally:
            self.running = False
            self.stream.release()
            self.landmarker.close()
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourFingerCounter()
    node.run()
