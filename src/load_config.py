"""

Load initial middleware keys and values into redis.

This module loads JSON configuration files into a Redis instance for use by
the middleware system. It first loads the default configuration from
`../cfg/initial.json`, then optionally loads user-specific overrides from
`/home/idmind/elmo.json` if present.

Module Behavior
---------------
- Connects to local Redis server.
- Loads initial configuration JSON and stores each key-value pair in Redis.
- Loads custom per-robot configuration if available, overriding defaults.
- All values are JSON-serialized before storage.

Requirements
------------
- Redis server running on localhost.
- Configuration files in JSON format with flat key-value structure.
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
if "elmo.json" in os.listdir("/home/idmind/"):
    with open("/home/idmind/elmo.json") as f:
        config = json.load(f)

    for key, value in config.items():
        client.set(key, json.dumps(value))
