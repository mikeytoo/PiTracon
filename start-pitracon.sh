#!/bin/bash
# Clean up any lingering sockets
rm -f /tmp/mpv_*.sock /tmp/atc_status.json*

# Launch audio engine and radar scope from repo directory
python3 /home/pi/PiTracon/atc-audio.py &
exec python3 /home/pi/PiTracon/pitracon.py
