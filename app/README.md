## Companion App

In this repository, under `app/` is the source code for TAGI's companion app. The app was developed using PyQT5 and QTDesigner, under Ubuntu 18.04. You can run the app using the `app/dev.sh` script, or build the application using `app/build.sh`. Resolve dependencies as they appear, using pip.

Alternatively, you can request a prebuilt version by email.

The Companion App will attempt to discover any TAGIs on the network using UDP broadcast. After finding your TAGI, you can click the button to connect to it and use the application to explore and test different functionalities of the robot. 

Also, take note of the robot's IP, since you will probably want to SSH into it for development, at some time.

The App communicates with TAGI via a REST API, which is also a decent way to control the robot.