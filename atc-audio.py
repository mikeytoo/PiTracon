#!/usr/bin/env python3
import time
import os
import json
import subprocess
import threading

CONFIG_FILE = "/home/pi/PiTracon/config.json"
STREAMS = {}

try:
    with open(CONFIG_FILE, 'r') as f:
        cfg = json.load(f)
        for stream in cfg.get("audio_streams", []):
            s_id = stream.get("id")
            mounts = stream.get("mounts", [])
            if s_id and mounts:
                # Construct the full LiveATC URL using the first mount point
                STREAMS[s_id] = f"http://s1-fmt2.liveatc.net/{mounts[0]}"
except Exception:
    # Failsafe fallback if config is missing
    STREAMS = {
        "app": "http://s1-fmt2.liveatc.net/ksdf_app_1",
        "twr": "http://s1-fmt2.liveatc.net/ksdf_twr",
        "sec": "http://s1-fmt2.liveatc.net/kind9_zid_125125"
    }

STATUS_FILE = "/tmp/atc_status.json"
status_lock = threading.Lock()
stream_statuses = {k: "down" for k in STREAMS}

def update_status_file():
    while True:
        with status_lock:
            try:
                with open(STATUS_FILE, "w") as f:
                    json.dump(stream_statuses, f)
            except Exception:
                pass
        time.sleep(0.5)

def stream_worker(key, url):
    sock_path = f"/tmp/mpv_{key}.sock"
    
    while True:
        # Clean up stale socket
        if os.path.exists(sock_path):
            try:
                os.unlink(sock_path)
            except Exception:
                pass

        cmd = [
            "/usr/bin/mpv",
            "--no-video",
            "--profile=low-latency",
            "--ytdl=no",
            "--demuxer=lavf",
            "--ao=pulse",
            f"--input-ipc-server={sock_path}",
            "--volume=80",
            "--msg-level=all=warn,ffmpeg=v",
            "--af=lavfi=[silencedetect=n=-15dB:d=1.0]",
            url
        ]
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            with status_lock:
                stream_statuses[key] = "idle"

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                with status_lock:
                    if "silence_start" in line:
                        stream_statuses[key] = "idle"
                    elif "silence_end" in line:
                        stream_statuses[key] = "active"

            process.wait()
        except Exception:
            pass

        with status_lock:
            stream_statuses[key] = "down"
        
        time.sleep(2.0)

if __name__ == "__main__":
    # Start status writer daemon
    threading.Thread(target=update_status_file, daemon=True).start()

    # Launch a dedicated thread for each ATC feed
    threads = []
    for k, u in STREAMS.items():
        t = threading.Thread(target=stream_worker, args=(k, u), daemon=True)
        t.start()
        threads.append(t)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
