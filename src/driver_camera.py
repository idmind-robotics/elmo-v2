

from flask import Flask, Response
from picamera2 import Picamera2
import io
import time

app = Flask(__name__)

# Initialize camera
picam2 = Picamera2()
config = picam2.create_video_configuration({"size": (1280, 720)})
picam2.configure(config)
picam2.start()

def generate_frames():
    while True:
        buffer = io.BytesIO()
        picam2.capture_file(buffer, format="jpeg")
        frame = buffer.getvalue()

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.01)

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, threaded=True)
