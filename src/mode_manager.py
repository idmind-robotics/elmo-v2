import time

import middleware as mw


LOOP_RATE = 10


MODE_IDLE = 0
MODE_CONVERSATION = 1
MODE_PHOTOGRAPHER = 2
MODE_AKINATOR = 3
MODE_WIFI_CONNECT = 4


class ModeManager:
    def __init__(self):
        self.leds = mw.Leds()
        self.server = mw.Server()
        self.touch_sensors = mw.TouchSensors()
        self.behaviours = mw.Behaviours()
        self.gpio = mw.GPIO()
        self.node = mw.Node("mode_manager")
        self.modes = [
            MODE_IDLE,
            MODE_CONVERSATION,
            MODE_PHOTOGRAPHER,
            MODE_AKINATOR,
            MODE_WIFI_CONNECT,
        ]
        self.icons = {
            MODE_IDLE: "elmo_idm.png",
            MODE_CONVERSATION: "chat2.png",
            MODE_PHOTOGRAPHER: "photograph.png",
            MODE_AKINATOR: "lamp_genie3.png",
            MODE_WIFI_CONNECT: "wifi.png",
        }

    def idle_mode(self):
        self.node.loginfo("idle mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = False
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = False
        self.behaviours.clock = True
        self.behaviours.blush = True

    def conversation_mode(self):
        self.node.loginfo("conversation mode")
        self.behaviours.conversation = True
        self.behaviours.photographer = False
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = False
        self.behaviours.clock = False
        self.behaviours.blush = False

    def photographer_mode(self):
        self.node.loginfo("photographer mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = True
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = False
        self.behaviours.clock = False
        self.behaviours.blush = False

    def akinator_mode(self):
        self.node.loginfo("akinator mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = False
        self.behaviours.akinator = True
        self.behaviours.wifi_connect = False
        self.behaviours.clock = False
        self.behaviours.blush = False

    def wifi_connect_mode(self):
        self.node.loginfo("wifi connect mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = False
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = True
        self.behaviours.clock = False
        self.behaviours.blush = False

    def highlight_mode(self, mode):
        url = self.server.url_for_icon(self.icons[mode])
        self.leds.load_from_url(url)

    def select_mode(self, mode):
        if mode == MODE_CONVERSATION:
            self.conversation_mode()
        elif mode == MODE_PHOTOGRAPHER:
            self.photographer_mode()
        elif mode == MODE_AKINATOR:
            self.akinator_mode()
        elif mode == MODE_WIFI_CONNECT:
            self.wifi_connect_mode()
        elif mode == MODE_IDLE:
            self.idle_mode()
        # hide icon
        self.leds.clear()

    def run(self):
        try:
            self.node.loginfo("starting behaviour")
            current_mode_idx = -1
            next_mode_idx = 0
            last_click_at = time.time()
            was_pressed = False
            n_modes = len(self.modes)
            while not self.node.is_shutdown():
                time.sleep(1.0 / LOOP_RATE)
                # if user clicked the button, show next mode
                is_pressed = self.gpio.button_pressed
                if is_pressed and not was_pressed:
                    last_click_at = time.time()
                    next_mode_idx = (next_mode_idx + 1) % n_modes
                was_pressed = is_pressed
                # if 1 second passed since last click, select mode
                if last_click_at and time.time() - last_click_at > 2.0:
                    print("selecting %d" % next_mode_idx)
                    self.select_mode(self.modes[current_mode_idx])
                    last_click_at = None
                # highlight mode
                if next_mode_idx != current_mode_idx:
                    print("highlighting %d" % next_mode_idx)
                    self.highlight_mode(self.modes[next_mode_idx])
                    current_mode_idx = next_mode_idx
        finally:
            self.node.shutdown()


if __name__ == "__main__":
    node = ModeManager()
    node.run()
