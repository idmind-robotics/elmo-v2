## stay enable

in order to set the stay_enable pin (4) to HIGH after boot, add the following lines to /etc/rc.local:


gpio -g mode 4 out
gpio -g write 4 1


in order to set the stay_enable pin (4) to LOW after shutdown, add the following lines to /boot/config.txt:


dtoverlay=gpio-poweroff,gpiopin=4,active_low=1

## autostart

add the following lines to cron

@reboot /bin/bash /home/idmind/elmo-v2/scripts/start.sh > /home/idmind/latest.log 2>&1
@reboot /bin/bash /home/idmind/elmo-v2/scripts/start_webapp.sh
@reboot /home/idmind/elmo-v2/scripts/fix_monitor.sh >> /home/idmind/fix_monitor.log 2>&1

## sudo without password

add the following line to /etc/sudoers
idmind ALL=(ALL) NOPASSWD: /sbin/poweroff, /sbin/reboot, /sbin/shutdown

## monitor config

add the following lines to /boot/config.txt

max_framebuffer_height=1920
config_hdmi_boost=10
hdmi_group=2
hdmi_force_hotplug=1
hdmi_mode=87
hdmi_timings=1080 1 26 4 50 1920 1 8 2 6 0 0 0 60 0 135580000 3

## silent boot

add the following lines to /boot/config.txt

disable_splash=1

run the following command

sudo systemctl mask plymouth-start.service

add the following line to /boot/cmdline.txt

logo.nologo vt.global_cursor_default=0

edit that line from console=tty1 to console=tty3, this will redirect boot log messages to the third console.

set a black wallpaper

pcmanfm --set-wallpaper /home/idmind/elmo-v2/src/static/images/background_black.png

hide desktop toolbar by editing /etc/xdf/lxsession/LXDE-pi/autostart and commenting out the lxpanel --profile LXDE-pi line



