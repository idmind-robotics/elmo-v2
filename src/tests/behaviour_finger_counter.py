"""

Behaviour node.

Detects the number of fingers being held up (1 to 5)
and prints the result to the terminal in real time.

Uses MediaPipe HandLandmarker for accurate finger joint detection.

REQUIRES: Python 3.11 or 3.12, mediapipe installed.

"""

import time
import cv2
import numpy as np
import mediapipe as mp
import middleware as mw
import threading


FRAME_W = 640
FRAME_H = 480
LOOP_RATE = 10


class BehaviourFingerNumbers:

    def __init__(self):
        self.node = mw.Node("behaviour_finger_numbers")

        # mediapipe hand landmarker setup
        self.result = None
        self.lock_result = threading.Lock()

        def update_result(result, output_image, timestamp_ms):
            with self.lock_result:
                self.result = result

        options = mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path='/home/idmind/elmo-v2/src/hand_landmarker.task'),
            running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
            num_hands=1,
            min_hand_detection_confidence=0.3,
            min_hand_presence_confidence=0.3,
            min_tracking_confidence=0.3,
            result_callback=update_result
        )
        self.landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

        # camera stream setup
        self.stream = cv2.VideoCapture("http://localhost:8080/stream.mjpg")
        self.latest_frame = None
        self.lock_frame = threading.Lock()
        self.running = True
        t = threading.Thread(target=self.reader, daemon=True)
        t.start()
        time.sleep(2)
        self.node.loginfo("Camera ready.")

    def reader(self):
        while self.running:
            ret, frame = self.stream.read()
            if ret:
                with self.lock_frame:
                    self.latest_frame = frame

    def count_fingers(self, hand_landmarks):
        """
        Count raised fingers using landmark y positions.
        Fingers: index=8, middle=12, ring=16, pinky=20
        Thumb: uses x position comparison
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
                        print("No hand detected.")
                        last_count = None
                    continue

                count = self.count_fingers(result.hand_landmarks[0])

                if count != last_count:
                    print(f"Fingers lifted: {count}")
                    last_count = count

        finally:
            self.running = False
            self.stream.release()
            self.landmarker.close()
            self.node.shutdown()


if __name__ == "__main__":
    node = BehaviourFingerNumbers()
    node.run()