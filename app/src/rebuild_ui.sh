#! /bin/bash

source /home/luckin/Documents/elmo-v2-idmind/app/.venv/bin/activate

#After resource additions, run this script to update the app
#pyrcc5 resource.qrc -o resource_rc.py  # This is just a template, the resources in resources.qrc are unavailable

#After changes in main_window.ui, run this script to update the app
for file in *.ui
do
  pyuic5 -o ${file:0:-3}_ui.py $file
done

