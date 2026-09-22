#!/bin/bash
# Clean up any stale sockets or status files from prior runs
rm -f /tmp/mpv_*.sock /tmp/atc_status.json*

# Launch audio daemon in background
python3 /home/pi/atc-audio.py &

# Brief pause to let audio sockets initialize
sleep 1

# Launch radar display engine in foreground
exec python3 /home/pi/radar-live.py
