"""

Driver node.

This node captures frames from the Raspberry Pi camera and streams them
over HTTP as a multipart MJPEG video feed.

"""

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
    Yield MJPEG frames from the camera as a continuous byte stream.

    Captures JPEG snapshots from the camera in a tight loop and formats
    each one as a multipart HTTP boundary frame suitable for an MJPEG
    stream. Sleeps briefly between frames to avoid saturating the CPU.

    Yields
    ------
    bytes
        A single MJPEG boundary-delimited JPEG frame, including the
        ``Content-Type`` header and trailing newline bytes.
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
    Flask route that serves the live MJPEG video stream.

    Calls ``generate_frames`` and wraps the resulting generator in a
    Flask ``Response`` with the appropriate multipart MIME type so that
    browsers and HTTP clients can decode it as a continuous video feed.

    Returns
    -------
    flask.Response
        A streaming HTTP response with MIME type
        ``multipart/x-mixed-replace; boundary=frame``.
    """
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
