

"""

Load initial middleware keys and values into redis.

"""


import json
import os
import redis


client = redis.Redis()


# Load initial config.
with open("../cfg/initial.json") as f:
    config = json.load(f)

for key, value in config.items():
    client.set(key, json.dumps(value))

# Load custom robot config.
if "elmo.json" in os.listdir("/home/elmo"):
    with open("/home/elmo/elmo.json") as f:
        config = json.load(f)

    for key, value in config.items():
        client.set(key, json.dumps(value))
