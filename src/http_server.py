#! /usr/bin/env python3


"""

This module implements the robot's HTTP server.

It serves the static resources (images, icons, sounds, videos) and provides an API to control the onboard screen.

The onboard webpage also performs speech recognition, which is published to this server.

"""


import os
import time
import json
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import threading

from werkzeug.utils import secure_filename

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


import middleware as mw


app = Flask(__name__, static_url_path='')
CORS(app)


server = mw.Server()
onboard = mw.Onboard()
node = mw.Node("http_server")


@app.route("/")
def index():
    return send_from_directory(server.static_path, "index.html")


@app.route("/api/onboard", methods=["GET", "POST"])
def onboard_handle():
    if request.method == "GET":
        return jsonify({
            "image": onboard.image,
            "text": onboard.text,
            "url": onboard.url,
            "video": onboard.video,
        })
    elif request.method == "POST":
        request_data = request.json
        if "image" in request_data:
            onboard.image = request_data["image"]
        if "text" in request_data:
            onboard.text = request_data["text"]
        if "url" in request_data:
            onboard.url = request_data["url"]
        if "video" in request_data:
            onboard.video = request_data["video"]        
        return jsonify({
            "image": onboard.image,
            "text": onboard.text,
            "url": onboard.url,
            "video": onboard.video,
        })


@app.route("/api/onboard/speech", methods=["POST"])
def onboard_speech():
    r = request.json["result"]
    print("speech: " + r)
    onboard.speech = r
    return jsonify({})


@app.route("/api/onboard/log", methods=["POST"])
def onboard_log():
    if "info" in request.json:
        log = "Onboard " + request.json["info"]
        node.loginfo(log)
    if "warn" in request.json:
        log = "Onboard " + request.json["warn"]
        node.logwarn(log)
    if "error" in request.json:
        log = "Onboard " + request.json["error"]
        node.logerror(log)
    return jsonify({})


@app.route("/icons", methods=["GET", "POST"])
def icons():
    if request.method == "GET":
        icon_list = os.listdir(server.static_path + "/icons")
        return jsonify(icon_list)
    elif request.method == "POST":
        print("[POST] icons")
        file = request.files['file']
        filename = secure_filename(file.filename)
        path = server.static_path + "/icons/"
        file.save(path + filename)
        print("file saved to " + path + filename)
        return jsonify("OK")


@app.route("/icons/<name>", methods=["DELETE"])
def delete_icon(name):
    if request.method == "DELETE":
        full_name = server.static_path + "/icons/" + name
        print("deleting " + full_name)
        os.remove(full_name)
        return jsonify("OK")


@app.route("/images", methods=["GET", "POST"])
def images():
    if request.method == "GET":
        image_list = os.listdir(server.static_path + "/images")
        return jsonify(image_list)
    elif request.method == "POST":
        file = request.files['file']
        filename = secure_filename(file.filename)
        path = server.static_path + "/images/"
        file.save(path + filename)
        return jsonify("OK")


@app.route("/images/<name>", methods=["DELETE"])
def delete_image(name):
    if request.method == "DELETE":
        full_name = server.static_path + "/images/" + name
        print("deleting " + full_name)
        os.remove(full_name)
        return jsonify("OK")


@app.route("/sounds", methods=["GET", "POST"])
def sounds():
    if request.method == "GET":
        sound_list = os.listdir(server.static_path + "/sounds")
        return jsonify(sound_list)
    elif request.method == "POST":
        file = request.files['file']
        filename = secure_filename(file.filename)
        path = server.static_path + "/sounds/"
        file.save(path + filename)
        return jsonify("OK")
    

@app.route("/sounds/<name>", methods=["DELETE"])
def delete_sound(name):
    if request.method == "DELETE":
        full_name = server.static_path + "/sounds/" + name
        print("deleting " + full_name)
        os.remove(full_name)
        return jsonify("OK")


@app.route("/videos", methods=["GET", "POST"])
def videos():
    if request.method == "GET":
        video_list = os.listdir(server.static_path + "/videos")
        return jsonify(video_list)
    elif request.method == "POST":
        file = request.files['file']
        filename = secure_filename(file.filename)
        path = server.static_path + "/videos/"
        file.save(path + filename)
        return jsonify("OK")


@app.route("/videos/<name>", methods=["DELETE"])
def delete_video(name):
    if request.method == "DELETE":
        full_name = server.static_path + "/videos/" + name
        print("deleting " + full_name)
        os.remove(full_name)
        return jsonify("OK")



if __name__ == "__main__":
    server_port = server.http_port
    server_thread = threading.Thread(target=lambda: app.run(debug=False, port=server_port, host="0.0.0.0"))
    server_thread.setDaemon(True)
    server_thread.start()
    node.loginfo("server running on port " + str(server_port))
    server.ready = True
    while not node.is_shutdown():
        time.sleep(0.1)
    print("server shutting down")


