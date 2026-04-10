import io
import logging
import socketserver
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput


PAGE = """\
<html>
<head>
<title>Picamera2 MJPEG Streaming</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="/stream.mjpg" width="640" height="480" />
</body>
</html>
"""


class StreamingOutput(io.BufferedIOBase):
    """
    A class to handle streaming output in MJPEG format.

    Attributes:
        frame (bytes or None): Holds the current frame of the video stream.
        condition (threading.Condition): Synchronizes the frame writing process between threads.
    
    Methods:
        write(buf): Writes the frame data and notifies waiting threads.
    """
    def __init__(self):
        """
        Initializes the StreamingOutput object with no frame and a condition for synchronization.
        """
        super().__init__()
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        """
        Writes the frame data and notifies any waiting threads.

        Args:
            buf (bytes): The MJPEG frame data to be written.
        """
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    """
    HTTP request handler that serves the MJPEG stream and HTML page.

    Methods:
        do_GET(): Handles GET requests, serving the HTML page or the MJPEG stream.
    """
    def do_GET(self):
        """
        Handles the HTTP GET request. Serves the HTML page or the MJPEG stream based on the request path.
        
        If the requested path is "/stream.mjpg", an MJPEG stream is served.
        If the requested path is "/" or "/index.html", the HTML page is served.
        If the requested path is unknown, a 404 error is returned.
        """
        if self.path in ("/", "/index.html"):
            content = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)

        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=FRAME"
            )
            self.end_headers()

            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame

                    self.wfile.write(b"--FRAME\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                    )
                    self.wfile.write(b"\r\n")
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")

            except Exception as e:
                logging.warning(
                    "Client disconnected %s: %s", self.client_address, str(e)
                )

        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    """
    A custom HTTP server for streaming MJPEG video over HTTP.

    Attributes:
        allow_reuse_address (bool): Allows the reuse of the socket address.
        daemon_threads (bool): Ensures that threads exit when the server stops.
    """
    allow_reuse_address = True
    daemon_threads = True


# --- Camera configuration ---
picam2 = Picamera2()
"""
An instance of Picamera2 used for camera configuration and video recording.
"""

picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
"""
Configures the Picamera2 instance for video recording at a resolution of 640x480.
"""

output = StreamingOutput()
"""
An instance of StreamingOutput that stores the current frame for MJPEG streaming.
"""
picam2.start_recording(MJPEGEncoder(), FileOutput(output))
"""
Starts recording video with MJPEG encoding, writing output to the StreamingOutput instance.
"""


try:
    address = ("", 8080)
    httpd = StreamingServer(address, StreamingHandler)
    """
    Initializes and starts the StreamingServer, binding to address ("", 8080) for streaming.
    """
    print("Streaming on http://0.0.0.0:8080")
    httpd.serve_forever()
finally:
    picam2.stop_recording()
