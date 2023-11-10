#! /usr/bin/env python


"""

Driver node.

Leverages libcamera to capture frames from the camera.

Server the frames as a MJPEG stream.

"""


from flask import Flask, Response
import libcamera


app = Flask(__name__)


# Create a Camera instance using libcamera
with libcamera.Camera() as camera:
    camera.configure()
    camera.start()

    # Define a generator function to capture frames
    def generate_frames():
        while True:
            # Capture a frame from the camera
            frame = camera.capture()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    @app.route('/video')
    def video():
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
