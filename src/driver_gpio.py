"""

Driver node.

This node manages the GPIO pins.

GPIO pins are used to control audio and monitor power, the stay enable pin and the power button.

"""

import lgpio
import time
import middleware as mw


class DriverGpio:
    def __init__(self):
        """
        Connect to middleware.
        Initialize node.
        """
        self.node = mw.Node("driver_gpio")
        self.gpio = mw.GPIO()

        # open chip (0 = /dev/gpiochip0 on Pi5)
        self.chip = lgpio.gpiochip_open(0)

        # --- INPUTS ---
        lgpio.gpio_claim_input(self.chip, self.gpio.button_pin)
        # lgpio.gpio_claim_input(self.chip, self.gpio.shutdown_pin)

        # --- OUTPUTS (start HIGH like original code) ---
        # lgpio.gpio_claim_output(self.chip, self.gpio.stay_enable_pin, 1)
        lgpio.gpio_claim_output(self.chip, self.gpio.audio_pin, 1)
        lgpio.gpio_claim_output(self.chip, self.gpio.monitor_pin, 1)

        self.node.loginfo("driver_gpio: initialized using lgpio")

    def enable_audio(self, control):
        """
        Enable or disable the audio power.
        """
        if control:
            self.node.loginfo("gpio: audio ON")
            lgpio.gpio_write(self.chip, self.gpio.audio_pin, 1)
        else:
            self.node.loginfo("gpio: audio OFF")
            lgpio.gpio_write(self.chip, self.gpio.audio_pin, 0)

    def enable_monitor(self, control):
        """
        Enable or disable the monitor power.
        """
        if control:
            self.node.loginfo("gpio: monitor ON")
            lgpio.gpio_write(self.chip, self.gpio.monitor_pin, 1)
        else:
            self.node.loginfo("gpio: monitor OFF")
            lgpio.gpio_write(self.chip, self.gpio.monitor_pin, 0)

    def run(self):
        """
        Main loop.
        """
        try:
            self.gpio.ready = True

            while not self.node.is_shutdown():
                time.sleep(0.1)

                # AUDIO CONTROL
                if self.gpio.audio_enable and not self.gpio.audio_enabled:
                    self.enable_audio(True)
                    self.gpio.audio_enabled = True
                elif not self.gpio.audio_enable and self.gpio.audio_enabled:
                    self.enable_audio(False)
                    self.gpio.audio_enabled = False

                # MONITOR CONTROL
                if self.gpio.monitor_enable and not self.gpio.monitor_enabled:
                    self.enable_monitor(True)
                    self.gpio.monitor_enabled = True
                elif not self.gpio.monitor_enable and self.gpio.monitor_enabled:
                    self.enable_monitor(False)
                    self.gpio.monitor_enabled = False

                # BUTTON
                if lgpio.gpio_read(self.chip, self.gpio.button_pin):
                    if not self.gpio.button_pressed:
                        self.node.loginfo("gpio: button pressed")
                    self.gpio.button_pressed = True
                else:
                    self.gpio.button_pressed = False

                # SHUTDOWN PIN
                # if lgpio.gpio_read(self.chip, self.gpio.shutdown_pin):
                #    if not self.gpio.robot_shutdown:
                #        self.node.loginfo("gpio: shutdown signal detected")
                #    self.gpio.robot_shutdown = True
                # else:
                #    self.gpio.robot_shutdown = False

        except KeyboardInterrupt:
            pass

        finally:
            self.enable_audio(False)
            self.enable_monitor(False)
            time.sleep(0.1)

            lgpio.gpiochip_close(self.chip)
            self.node.shutdown()


if __name__ == "__main__":
    node = DriverGpio()
    node.run()
