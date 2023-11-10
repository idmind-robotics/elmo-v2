import socket
import netifaces
import requests
import threading


CONTEXT = {
    "scanning_robots": False,
    "robot_model": ""
}



def set_robot_model(model):
    CONTEXT["robot_model"] = model


def scan_robots(cb, models=[]):
    def scan_robots_runnable():
        while CONTEXT["scanning_robots"]:
            try:
                interfaces = netifaces.interfaces()
                allips = []
                for i in interfaces:
                    try:
                        allips.append(netifaces.ifaddresses(i)[netifaces.AF_INET][0]["addr"])
                    except:
                        pass
                msg = b'ruarobot'
                for ip in allips:
                    if "127.0.0" in ip:
                        continue
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # UDP
                    sock.settimeout(1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.bind((ip,0))
                    sock.sendto(msg, ("255.255.255.255", 5000))
                    try:
                        while True:
                            data, address = sock.recvfrom(1024)
                            print(data)
                            if b"iamarobot" in data:
                                _, robot_model, robot_name, server_port = data.decode("utf-8").split(";")
                                if CONTEXT["robot_model"]:
                                    if robot_model == CONTEXT["robot_model"]:
                                        cb(robot_name, "http://%s:%s" % (address[0], server_port))
                                else:
                                    cb(robot_name, "http://%s:%s" % (address[0], server_port))
                    except socket.timeout:
                        sock.close()
            except:
                pass
    CONTEXT["scanning_robots"] = True
    t = threading.Thread(target=scan_robots_runnable)
    t.start()

def stop_scan():
    CONTEXT["scanning_robots"] = False


def connect(address):
    try:
        return True, "OK", Robot(address)
    except Exception as e:
        return False, e, None        


MAX_ERROR_COUNT = 5


class Robot:
    error_count = 0

    def __init__(self, address):
        self.address = address
        self.ip = address.split(":")[1][2:]

    def update_status(self):
        try:
            url = self.address + "/status"
            new_status = requests.get(url, timeout=1).json()
            for k in new_status:
                setattr(self, k, new_status[k])
            self.error_count = 0
        except Exception as e:
            if self.error_count > MAX_ERROR_COUNT:
                self.on_disconnect()
            else:
                self.error_count += 1
            print(e)

    def send_command(self, command, **kwargs):
        try:
            url = self.address + "/command"
            kwargs["op"] = command
            res = requests.post(url, json=kwargs, timeout=1).json()
            if not res["success"]:
                self.on_error(res["message"])
        except Exception as e:
            print(e)

    def on_error(self, message):
        print("Error: " + message)

    def on_disconnect(self):
        print("Connection to robot lost.")
