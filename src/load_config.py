#! /usr/bin/env python


"""

Load initial middleware keys and values into redis.

"""


import json
import redis


with open("../cfg/initial.json") as f:
    config = json.load(f)

client = redis.Redis()

for key, value in config.items():
    client.set(key, json.dumps(value))