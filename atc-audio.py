#!/usr/bin/env python3
import subprocess, time, threading, json, os, urllib.request

# Define your desired mounts. Add as many as you want and assign their spatial role.
FEEDS = [
    {"role": "left",   "mount": "ksdf_app_1"}, # SDF Approach
    {"role": "center", "mount": "ksdf_twr"},   # SDF Tower
    {"role": "right",  "mount": "kind9_zid_125125"}, # Indy Center High
#    {"role": "right",  "mount": "INSERT_ZID_MOUNT_2"}, # Indy Center Low
]

STATE_FILE = "/tmp/atc_status.json"
status_lock = threading.Lock()

def resolve_stream_url(mount):
    pls_url = f"https://www.liveatc.net/play/{mount}.pls"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        req = urllib.request.Request(pls_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            for line in resp.read().decode('utf-8', errors='ignore').splitlines():
                if line.strip().startswith("File1="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return f"https://s1-fmt2.liveatc.net/{mount}"

def write_status(state):
    # Hardcoded to keep your Pygame UI buttons happy regardless of feed count
    with status_lock:
        feed_statuses = {"app": state, "twr": state, "sec": state}
        try:
            with open(STATE_FILE + ".tmp", "w") as sf:
                json.dump(feed_statuses, sf)
            os.replace(STATE_FILE + ".tmp", STATE_FILE)
        except Exception:
            pass

def audio_worker():
    while True:
        write_status("down")
        
        # Resolve all URLs
        urls = [resolve_stream_url(f["mount"]) for f in FEEDS]
        
        # Dynamically build the ffmpeg command and filter graph
        ffmpeg_cmd = ["ffmpeg", "-nostats", "-hide_banner"]
        filter_parts = []
        amix_inputs = []
        
        for idx, f in enumerate(FEEDS):
            ffmpeg_cmd.extend(["-i", urls[idx]])
            
            if f["role"] == "left":
                pan = "c0=c0"
            elif f["role"] == "right":
                pan = "c1=c0"
            else: # center
                pan = "c0=0.7*c0|c1=0.7*c0"
                
            filter_parts.append(f"[{idx}:a]pan=stereo|{pan}[a{idx}]")
            amix_inputs.append(f"[a{idx}]")
            
        amix_str = "".join(amix_inputs) + f"amix=inputs={len(FEEDS)}:duration=longest:dropout_transition=0,volume=4.0[out]"
        filter_complex = "; ".join(filter_parts) + "; " + amix_str
        
        ffmpeg_cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-f", "alsa", "default"
        ])
        
        try:
            proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2.0)
            
            while proc.poll() is None:
                write_status("idle")
                time.sleep(1.0)
                
        except Exception:
            pass
            
        time.sleep(3.0)

t = threading.Thread(target=audio_worker, daemon=True)
t.start()

while True:
    time.sleep(1.0)
