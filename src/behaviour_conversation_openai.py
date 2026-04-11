

import datetime
import subprocess
import time
import requests
import json

import middleware as mw


HISTORY_RESET_TIMEOUT = 60.0 * 5.0
CHAT_ICON = "chat2.png"


class OpenAIAPI:
    def __init__(self, api_key, base_url="https://api.openai.com/v1/chat/completions"):
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
        self.initial_context = [{ "role": "system", "content": message }]
        self.context = self.initial_context[:]

    def chat_completion(self, prompt):
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
        if self.context_reset:
            return
        self.context = self.initial_context[:]
        self.context_reset = True


class BehaviourConversation:
    def __init__(self):
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
        self.node.loginfo("loading chatbot global action")
        chatbot_global_action = ""
        with open("chatbot_global_action.txt") as fp:
            chatbot_global_action = fp.read()
        self.api.set_initial_context(chatbot_global_action)
        self.node.loginfo("loaded chatbot global action:")
        self.node.loginfo(chatbot_global_action)
    
    def reset_history(self):
        self.api.reset_context()

    def get_response(self, message):
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
        self.node.loginfo("thinking")
        image_url = self.server.url_for_image("thinking.png")
        self.onboard.image = image_url
    
    def not_thinking(self):
        self.node.loginfo("not thinking")
        self.onboard.image = None

    def react_to(self, prefix):
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
        if text == ".":
            return
        self.speech.say = text
        self.finish_speaking()
    
    def reply(self, user_message):
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
