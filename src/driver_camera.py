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
    """
    Generator yielding multipart JPEG frames from the camera.

    This function captures a single JPEG frame from the Picamera2 instance,
    encodes it in multipart response format, and yields it repeatedly.
    It sleeps 0.01 seconds between frames to limit CPU usage and frame rate.

    Returns
    -------
    generator
        Yields bytes objects in MJPEG stream frame format:
        --frame\r\nContent-Type: image/jpeg\r\n\r\n<jpeg_data>\r\n
    """
    while True:
        buffer = io.BytesIO()
        picam2.capture_file(buffer, format="jpeg")
        frame = buffer.getvalue()

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.01)


@app.route("/video")
def video():
    """
    Flask route handler returning streaming MJPEG response.

    Returns
    -------
    flask.Response
        HTTP response with MIME type multipart/x-mixed-replace, streaming
        frames from `generate_frames`.
    """
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
