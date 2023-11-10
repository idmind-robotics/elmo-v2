#! /bin/bash


pyrcc5 resource.qrc -o resource_rc.py
for file in *.ui
do
  pyuic5 -o ${file:0:-3}_ui.py $file
done

