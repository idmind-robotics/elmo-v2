#!/bin/bash


ALREADY_APPLIED=true
LOG_FILE="/tmp/kiosk_settings.log"
log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }


mkdir -p ~/.config/labwc



# Hide the taskbar
if [ -f /etc/xdg/labwc/autostart ] && [ ! -f /etc/xdg/labwc/autostart.bak ]; then
    log "Hiding taskbar..."
    sudo mv /etc/xdg/labwc/autostart /etc/xdg/labwc/autostart.bak
    ALREADY_APPLIED=false
fi
if [ ! -f ~/.config/labwc/autostart ]; then
    cp /etc/xdg/labwc/autostart.bak ~/.config/labwc/autostart
    sed -i '/wf-panel-pi/d' ~/.config/labwc/autostart
    ALREADY_APPLIED=false
    log "Taskbar hidden."
fi



# Set black desktop background, remove wallpaper and hide desktop icons
# Applies to both monitors (desktop-items-0 and desktop-items-1)
for i in 0 1; do
    CONF="$HOME/.config/pcmanfm/default/desktop-items-$i.conf"
    SRC="/etc/xdg/pcmanfm/default/desktop-items-$i.conf"
    if [ -f "$SRC" ] && [ ! -f "$CONF" ]; then
        log "Changing background to black $i..."
        mkdir -p ~/.config/pcmanfm/default
        cp "$SRC" "$CONF"
        sed -i 's/wallpaper_mode=.*/wallpaper_mode=0/' "$CONF"
        sed -i 's|wallpaper=.*|wallpaper=|' "$CONF"
        sed -i 's/desktop_bg=.*/desktop_bg=#000000/' "$CONF"
        log "Background changed $i."
        log "Hiding desktop icons for desktop $i..."
        sed -i 's/show_trash=.*/show_trash=0/' "$CONF"
        sed -i 's/show_mounts=.*/show_mounts=0/' "$CONF"
        sed -i 's/show_documents=.*/show_documents=0/' "$CONF"
        grep -q '^show_documents' "$CONF" || echo 'show_documents=0' >> "$CONF"
        grep -q '^show_trash' "$CONF" || echo 'show_trash=0' >> "$CONF"
        grep -q '^show_mounts' "$CONF" || echo 'show_mounts=0' >> "$CONF"
        ALREADY_APPLIED=false
        log "Desktop icons hidden $i."
    fi
done



# Hide the mouse cursor using wtype to trigger labwc's HideCursor action on startup
if ! grep -q 'HideCursor' ~/.config/labwc/rc.xml 2>/dev/null; then
    log "Hiding mouse cursor..."
    sed -i 's|</openbox_config>|  <keyboard>\n    <keybind key="A-W-h">\n      <action name="HideCursor"/>\n    </keybind>\n  </keyboard>\n</openbox_config>|' ~/.config/labwc/rc.xml
    grep -q 'wtype' ~/.config/labwc/autostart || echo "wtype -M alt -M logo -P h &" >> ~/.config/labwc/autostart
    ALREADY_APPLIED=false
    log "Cursor hidden."
fi



if [ "$ALREADY_APPLIED" = true ]; then
    log "The settings were already applied."
    exit 0
fi



# Apply changes immediately without rebooting
pkill -f '/usr/bin/wf-panel-pi'
pkill -f 'pcmanfm --desktop'

log "Changes applied. Please reboot."


