"""

Behaviour node.

Listens for speech input from the onboard display and drives a multi-turn
conversation with the OpenAI API. Supports emotional reactions, task
execution (photo, game, video), and automatic history reset on inactivity.

"""

import datetime
import subprocess
import time
import requests
import json

import middleware as mw


HISTORY_RESET_TIMEOUT = 60.0 * 5.0
CHAT_ICON = "chat2.png"


class OpenAIAPI:
    """
    Thin wrapper around the OpenAI chat completions endpoint.

    Manages conversation history, initial system context, and context resets.

    Attributes
    ----------
    api_key : str
        OpenAI API key used for authorization.
    base_url : str
        Full URL of the chat completions endpoint.
    headers : dict
        HTTP headers sent with every request.
    initial_context : list[dict]
        System message(s) prepended to every conversation.
    context : list[dict]
        Full conversation history including system, user, and assistant turns.
    context_reset : bool
        True if the context has been reset and no new user message has been sent.
    """

    def __init__(self, api_key, base_url="https://api.openai.com/v1/chat/completions"):
        """
        Initialize the API client with credentials and an empty context.

        Parameters
        ----------
        api_key : str
            OpenAI API key.
        base_url : str, optional
            Chat completions endpoint URL.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.initial_context = []
        self.context = []
        self.context_reset = True

    def set_initial_context(self, message):
        """
        Set the system prompt and reset the conversation history.

        Parameters
        ----------
        message : str
            System prompt text sent as the first message in every conversation.
        """
        self.initial_context = [{ "role": "system", "content": message }]
        self.context = self.initial_context[:]

    def chat_completion(self, prompt):
        """
        Send a user message and return the assistant reply.

        Behavior
        --------
        - Appends the user message to the conversation history.
        - Posts the full context to the OpenAI API using gpt-4o-mini.
        - Appends the assistant reply to the conversation history.
        - Returns a fallback error string on request failure.

        Parameters
        ----------
        prompt : str
            User message to send.

        Returns
        -------
        str
            Assistant reply text, or an error message on failure.
        """
        self.context_reset = False
        self.context.append({ "role": "user", "content": prompt })
        payload = {
            "model": "gpt-4o-mini",
            "store": True,
            "messages": self.context
        }
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            result = response.json()
            print("---")
            print(json.dumps(result, indent=2))
            print("===")
            reply = result["choices"][0]["message"]["content"]
            self.context.append({ "role": "assistant", "content": reply })
            return reply
        except requests.exceptions.RequestException as e:
            return f"An error occurred: {e}"

    def reset_context(self):
        """
        Reset the conversation history to the initial system context.

        Behavior
        --------
        - Only resets if at least one user message has been sent since the
        last reset, to avoid redundant resets.
        """
        if self.context_reset:
            return
        self.context = self.initial_context[:]
        self.context_reset = True


class BehaviourConversation:
    """
    Middleware behaviour that drives a spoken conversation via the OpenAI API.

    Listens for speech transcribed onto `onboard.speech`, sends it to the
    OpenAI API, and delivers the reply through the speech driver. Supports
    emotional display reactions and task execution triggered by response prefixes.

    Attributes
    ----------
    behaviours : mw.Behaviours
        Middleware behaviour flags used to check if conversation mode is active.
    conversation : mw.Conversation
        Middleware conversation state (API key, model config).
    onboard : mw.Onboard
        Middleware onboard display controller for images and speech input.
    speech : mw.Speech
        Middleware speech synthesis driver for text-to-speech output.
    server : mw.Server
        Middleware server helper for resource URLs.
    leds : mw.Leds
        Middleware LED controller.
    camera : mw.Camera
        Middleware camera state used for photo tasks.
    akinator : mw.Akinator
        Middleware Akinator game state used for game tasks.
    node : mw.Node
        Middleware node used for shutdown and logging.
    last_prompt_at : datetime.datetime
        Timestamp of the most recent user prompt, used for history timeout.
    processing_task : bool
        True while an async task (photo, game, video) is in progress.
    api : OpenAIAPI
        OpenAI API client instance.
    """

    def __init__(self):
        """
        Initialize middleware objects, API client, and load the system prompt.
        """
        self.behaviours = mw.Behaviours()
        self.conversation = mw.Conversation()
        self.onboard = mw.Onboard()
        self.speech = mw.Speech()
        self.server = mw.Server()
        self.leds = mw.Leds()
        self.camera = mw.Camera()
        self.akinator = mw.Akinator()
        self.node = mw.Node("behaviour_conversation")
        self.last_prompt_at = datetime.datetime.now()
        self.processing_task = False
        api_key = self.conversation.api_key
        self.api = OpenAIAPI(api_key)
        self.load_chatbot_global_action()
        self.conversation.ready = True
    
    def load_chatbot_global_action(self):
        """
        Load the system prompt from file and set it as the API initial context.

        Behavior
        --------
        - Reads "chatbot_global_action.txt" from the working directory.
        - Passes the contents to `api.set_initial_context`.
        - Logs the loaded prompt.
        """
        self.node.loginfo("loading chatbot global action")
        chatbot_global_action = ""
        with open("chatbot_global_action.txt") as fp:
            chatbot_global_action = fp.read()
        self.api.set_initial_context(chatbot_global_action)
        self.node.loginfo("loaded chatbot global action:")
        self.node.loginfo(chatbot_global_action)

    def reset_history(self):
        """
        Reset the OpenAI conversation history to the initial system context.
        """
        self.api.reset_context()

    def get_response(self, message):
        """
        Send a message to the OpenAI API and return the reply.

        Behavior
        --------
        - Shows the thinking image on the onboard display while waiting.
        - Retries up to 3 times on failure before returning a fallback message.
        - Hides the thinking image after the response is received.

        Parameters
        ----------
        message : str
            User message to send.

        Returns
        -------
        str
            Assistant reply, or a fallback error message after 3 failures.
        """
        self.thinking()
        error_count = 0
        while not self.node.is_shutdown():
            if error_count > 3:
                break
            try:
                reply = self.api.chat_completion(message)
                break
            except Exception as e:
                self.node.logwarn("failed to connect to get response: %s" % e)
                time.sleep(1.0)
                error_count += 1
            finally:
                self.not_thinking()
        if error_count > 3:
            return "Sorry, I can't talk right now."
        return reply

    def thinking(self):
        """
        Show the thinking image on the onboard display.
        """
        self.node.loginfo("thinking")
        image_url = self.server.url_for_image("thinking.png")
        self.onboard.image = image_url
    
    def not_thinking(self):
        """
        Clear the thinking image from the onboard display.
        """
        self.node.loginfo("not thinking")
        self.onboard.image = None

    def react_to(self, prefix):
        """
        Update the onboard display image in response to an emotion prefix.

        Behavior
        --------
        - **SAD   : shows "tears.png".
        - **HAPPY : shows "normal.png".
        - **NORMAL: shows "normal.png".

        Parameters
        ----------
        prefix : str
            Emotion prefix parsed from the assistant reply (e.g. "**SAD").
        """
        if prefix == "**SAD":
            self.node.loginfo(prefix)
            url = self.server.url_for_image("tears.png")
            self.onboard.image = url
        elif prefix == "**HAPPY":
            self.node.loginfo(prefix)
            url = self.server.url_for_image("normal.png")
            self.onboard.image = url
        elif prefix == "**NORMAL":
            self.node.loginfo(prefix)
            url = self.server.url_for_image("normal.png")
            self.onboard.image = url

    def perform_task(self, prefix):
        """
        Execute a task triggered by a task prefix in the assistant reply.

        Behavior
        --------
        - **VIDEO      : streams a video via SSH to an external display using VLC.
        - **TASK_PICTURE: triggers the camera driver to take a photo, waits for
        completion, then replies with the outcome.
        - **TASK_GAME  : starts the Akinator game, waits for it to finish,
        then replies with win/loss outcome.

        Parameters
        ----------
        prefix : str
            Task prefix parsed from the assistant reply (e.g. "**TASK_PICTURE").
        """

        if prefix == "**VIDEO":
            #TODO organize video playing better, maybe a video player class that handles the state and subprocess and everything
            print("video player start")
            self.node.loginfo(prefix)
            self.processing_task = True
            #Run and forget - test PARAMIKO

            linux = True
            if linux:
                try:
                    ssh_command = ["ssh", "idmind@computer.local", "DISPLAY=:0", "vlc", "--fullscreen", "--play-and-exit", "/home/idmind/elmo-v2/src/static/videos/eyes_green_all.mp4"]
                except Exception as e:
                    self.node.logwarn("failed to run video: %s" % e)
                finally:
                    subprocess.run(ssh_command, check=False)
                self.processing_task = False
                self.reply("**TASK_PICTURE finished")
            if not linux:
                try:
                    # transforming a string into a list
                    vlc_command = 'echo "ABRIR_VLC" | nc -w 1 192.168.2.86 5000 && ffmpeg -re -i /home/idmind/elmo-v2/src/static/videos/eyes_green_all.mp4 -c:v libx264 -preset ultrafast -f mpegts -listen 1 http://0.0.0.0:8080'
                    
                    # runnable with shell=True
                    subprocess.run(vlc_command, shell=True, check=False)
                except Exception as e:
                    self.node.logwarn("failed to run video: %s" % e)
                self.processing_task = False
                self.reply("**TASK_PICTURE finished")

        if prefix == "**TASK_PICTURE":
            print("task picture")
            self.node.loginfo(prefix)
            self.processing_task = True
            self.camera.take_picture = True
            self.camera.error = None
            # wait for take picture to start
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.camera.taking_picture:
                    break
            # wait for take picture to end
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if not self.camera.taking_picture:
                    break
            # check for errors
            if self.camera.error:
                self.processing_task = False
                self.reply("**TASK_PICTURE failed because (%s)" % self.camera.error)
                return
            self.processing_task = False
            self.reply("**TASK_PICTURE finished")
        if prefix == "**TASK_GAME":
            print("task game")
            self.node.loginfo(prefix)
            self.processing_task = True
            self.behaviours.akinator = True
            # wait for game to start
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if self.akinator.running:
                    break
            # wait for game to finish
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if not self.akinator.running:
                    break
            if self.akinator.error is not None:
                self.processing_task = False
                self.reply("**TASK_GAME failed due to error")
            elif self.akinator.guessed:
                self.processing_task = False
                self.reply("**TASK_GAME finished, robot won")
            else:
                self.processing_task = False
                self.reply("**TASK_GAME finished, robot lost")
    
    def finish_speaking(self):
        """
        Block until the speech driver finishes speaking the current utterance.

        Behavior
        --------
        - Waits for `speech.saying` to become True (speech started).
        - Waits for `speech.saying` to become False (speech finished).
        - Waits an additional second before clearing `onboard.speech`.
        """
        # return
        # wait for speech to start
        while not self.node.is_shutdown():
            time.sleep(0.1)
            if self.speech.saying:
                break
        # wait for speech to finish
        while not self.node.is_shutdown():
            time.sleep(0.1)
            if not self.speech.saying:
                break
        # wait a bit before resetting
        time.sleep(1.0)
        self.onboard.speech = None

    def say(self, text):
        """
        Send text to the speech driver and wait for it to finish.

        Behavior
        --------
        - Skips empty or placeholder messages (".").
        - Sets `speech.say` and blocks until speaking is complete.

        Parameters
        ----------
        text : str
            Text to synthesize and speak aloud.
        """
        if text == ".":
            return
        self.speech.say = text
        self.finish_speaking()

    def reply(self, user_message):
        """
        Send a user message to the API, parse the reply, and act on it.

        Behavior
        --------
        - Updates `last_prompt_at` to prevent premature history reset.
        - Stores the user message in middleware.
        - Parses a "**PREFIX message" format from the assistant reply.
        - Calls `react_to` for emotion prefixes.
        - Speaks the message text via `say`.
        - Calls `perform_task` for task prefixes.

        Parameters
        ----------
        user_message : str
            User message or task result string to send to the API.
        """
        self.last_prompt_at = datetime.datetime.now()
        self.conversation.user = user_message
        response = self.get_response(user_message)
        print(response)
        if response.startswith("**"):
            prefix = response.split(" ")[0]
            message = " ".join(response.split(" ")[1:])
        else:
            prefix = None
            message = response
        if prefix:
            print("reacting to %s" % prefix)
            self.react_to(prefix)
        if message:
            self.say(message)
            self.conversation.assistant = message
        if prefix:
            print("performing task %s" % prefix)
            self.perform_task(prefix)

    def run(self):
        """
        Main behaviour loop.

        Behavior
        --------
        - Logs startup and clears any stale speech input.
        - Polls every 100ms.
        - Skips processing while `behaviours.conversation` is False.
        - On enable: clears speech input and resets conversation history.
        - Resets history after `HISTORY_RESET_TIMEOUT` seconds of inactivity.
        - On new speech input (and no active task): calls `reply` and clears input.
        - Always shuts down node in finally block.
        """
        try:
            self.node.loginfo("starting behaviour")
            self.onboard.speech = None
            was_enabled = False
            while not self.node.is_shutdown():
                time.sleep(0.1)
                if not self.behaviours.conversation:
                    if was_enabled:
                        was_enabled = False
                    continue
                if not was_enabled:
                    self.onboard.speech = None
                    self.reset_history()
                    was_enabled = True
                    self.node.loginfo("enabled")
                if (datetime.datetime.now() - self.last_prompt_at).seconds > HISTORY_RESET_TIMEOUT:
                        self.node.loginfo("resetting history")
                        self.reset_history()
                if self.onboard.speech and not self.processing_task:
                    print(f"heard {self.onboard.speech}")
                    try:
                        self.reply(self.onboard.speech)
                        # wait a bit before prompting again
                        time.sleep(1.0)
                    finally:
                        self.onboard.speech = None
        finally:
            self.node.shutdown()


if __name__ == '__main__':
    node = BehaviourConversation()
    node.run()
