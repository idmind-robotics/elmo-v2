#! /bin/bash

./rebuild_ui.sh
python3 -m PyInstaller --onefile app.py 
mv dist/app .
rm -r build/ dist/ __pycache__/  app.spec
