
import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer
import middleware as mw
import numpy as np

# Path to your downloaded Vosk model
MODEL_PATH = "/home/elmo/elmo-v2-idmind/src/model"  # adjust if your folder has a different name

# Load the Vosk model
print("Loading model from:", MODEL_PATH)
model = Model(MODEL_PATH)
rec = KaldiRecognizer(model, 16000)
onboard = mw.Onboard()

# Queue to hold audio data
q = queue.Queue()

def callback(indata, frames, time, status):
    """Called for each audio block from the microphone."""
    #if status:
    #    print("Status:", status)
    q.put(bytes(indata))  # Raw PCM16 bytes

print("Listening...")

# Open microphone stream
with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                       channels=1, callback=callback):

    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text:
                print(f"Heard: {text}")
                onboard.speech = text
        else:
            partial = json.loads(rec.PartialResult()).get("partial", "")
            if partial:
                print(f"Partial: {partial}")
