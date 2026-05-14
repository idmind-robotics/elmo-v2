"""

Driver node.

This node manages the GPIO pins.

GPIO pins are used to control audio and monitor power, the stay enable pin and the power button.

"""

import lgpio
import time
import middleware as mw


class DriverGpio:
    """
    Hardware driver for the GPIO subsystem.

    Manages GPIO input and output pins via the lgpio library. Controls the
    audio and monitor power outputs, and reads the physical power button
    input. State changes are communicated to and from the rest of the
    system exclusively through the middleware GPIO object.

    > ## Attributes

    ``node : mw.Node`` : Middleware node used for shutdown signalling and logging.

    ``gpio : mw.GPIO`` : Middleware GPIO state object containing pin numbers, enable flags, and button state.
    
    ``chip : int`` : lgpio chip handle for ``/dev/gpiochip0``, used for all subsequent pin operations.

    > ## Functions
    """

    def __init__(self):
        """
        Connect to middleware.
        Initialize node.

        Opens the GPIO chip, claims the button pin as an input, and claims
        the audio and monitor pins as outputs (initialised HIGH). Logs a
        confirmation message once setup is complete.
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

        Writes a HIGH or LOW signal to the audio GPIO pin and logs the
        resulting state.

        Parameters
        ----------
        control : bool
            ``True`` to power the audio circuit on; ``False`` to power it off.
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

        Writes a HIGH or LOW signal to the monitor GPIO pin and logs the
        resulting state.

        Parameters
        ----------
        control : bool
            ``True`` to power the monitor on; ``False`` to power it off.
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

        Marks the GPIO subsystem as ready in middleware, then polls at
        10 Hz until shutdown is requested. On each tick:

        - **Audio control**: calls ``enable_audio`` and syncs
          ``gpio.audio_enabled`` whenever ``gpio.audio_enable`` diverges
          from the current enabled state.
        - **Monitor control**: calls ``enable_monitor`` and syncs
          ``gpio.monitor_enabled`` whenever ``gpio.monitor_enable`` diverges
          from the current enabled state.
        - **Button**: reads ``gpio.button_pin`` and updates
          ``gpio.button_pressed``; logs a message on the rising edge.

        On exit — whether from a ``KeyboardInterrupt`` or a middleware
        shutdown signal — audio and monitor are powered off, a brief
        settling delay is observed, the GPIO chip handle is closed, and
        the node is shut down.
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
