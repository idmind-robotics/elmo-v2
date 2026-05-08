#! /bin/bash

./rebuild_ui.sh
source /home/luckin/Documents/elmo-v2-idmind/app/.venv/bin/activate
uv run src/uv app.py