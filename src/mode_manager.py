import time

import middleware as mw


LOOP_RATE = 10


MODE_IDLE = 0
MODE_CONVERSATION = 1
MODE_PHOTOGRAPHER = 2
MODE_AKINATOR = 3
MODE_WIFI_CONNECT = 4


class ModeManager:
    """
    A class to manage different operating modes of the system.

    The ModeManager controls various behaviors associated with different modes, 
    including idle, conversation, photographer, akinator, and Wi-Fi connection modes.
    It handles mode transitions, behavior activation, and updates to the LED display.
    
    Attributes:
        leds (Leds): An instance of the Leds class for controlling the LED display.
        server (Server): An instance of the Server class to manage server requests.
        touch_sensors (TouchSensors): An instance of the TouchSensors class for touch input.
        behaviours (Behaviours): An instance of the Behaviours class to manage active behaviors.
        gpio (GPIO): An instance of the GPIO class for button and input handling.
        node (Node): An instance of the Node class for logging and shutdown operations.
        modes (list[int]): A list of mode constants representing available modes.
        icons (dict[int, str]): A dictionary mapping mode constants to icon file names.
    """
    def __init__(self):
        """
        Initializes the ModeManager instance, setting up hardware interfaces and 
        default mode behaviors.

        This constructor initializes necessary components such as LEDs, server, touch sensors, 
        behaviors, GPIO, and Node objects. It also defines the list of available modes 
        and corresponding icons for the LED display.
        """
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
        """
        Activates the idle mode, disabling all behaviors and setting the system to an idle state.

        This mode deactivates conversation, photographer, akinator, and Wi-Fi connect behaviors.
        """
        self.node.loginfo("idle mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = False
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = False

    def conversation_mode(self):
        """
        Activates the conversation mode, enabling the conversation behavior and disabling other behaviors.

        This mode enables the conversation behavior and disables photographer, akinator, and Wi-Fi connect behaviors.
        """
        self.node.loginfo("conversation mode")
        self.behaviours.conversation = True
        self.behaviours.photographer = False
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = False

    def photographer_mode(self):
        """
        Activates the photographer mode, enabling the photographer behavior and disabling other behaviors.

        This mode enables the photographer behavior and disables conversation, akinator, and Wi-Fi connect behaviors.
        """
        self.node.loginfo("photographer mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = True
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = False

    def akinator_mode(self):
        """
        Activates the akinator mode, enabling the akinator behavior and disabling other behaviors.

        This mode enables the akinator behavior and disables conversation, photographer, and Wi-Fi connect behaviors.
        """
        self.node.loginfo("akinator mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = False
        self.behaviours.akinator = True
        self.behaviours.wifi_connect = False

    def wifi_connect_mode(self):
        """
        Activates the Wi-Fi connect mode, enabling the Wi-Fi connect behavior and disabling other behaviors.

        This mode enables the Wi-Fi connect behavior and disables conversation, photographer, and akinator behaviors.
        """
        self.node.loginfo("wifi connect mode")
        self.behaviours.conversation = False
        self.behaviours.photographer = False
        self.behaviours.akinator = False
        self.behaviours.wifi_connect = True

    def highlight_mode(self, mode):
        """
        Highlights the selected mode by updating the LED display with the corresponding icon.

        Args:
            mode (int): The mode to highlight, represented by one of the mode constants.
        """
        url = self.server.url_for_icon(self.icons[mode])
        self.leds.load_from_url(url)

    def select_mode(self, mode):
        """
        Selects and activates the specified mode by calling the appropriate mode function.

        Args:
            mode (int): The mode to select, represented by one of the mode constants.
        """
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
        """
        Runs the main loop of the ModeManager, handling mode selection and transitions.

        This function monitors the button state, updates the current mode based on user input, 
        highlights the active mode on the LED display, and performs the necessary behavior 
        changes based on the selected mode. It runs until the system is shut down.

        It assumes that the user can cycle through modes by pressing a button, and 
        it will automatically switch to the selected mode after 2 seconds of inactivity.
        """
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
