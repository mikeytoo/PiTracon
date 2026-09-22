#!/usr/bin/env python3
import subprocess, time, threading, socket, json, os, urllib.request

FEEDS = [
    {"id": "app", "sock": "/tmp/mpv_app.sock", "mount": "ksdf_app_1", "pan": "lavfi=[pan=stereo|c0=c0|c1=0]"},
    {"id": "twr", "sock": "/tmp/mpv_twr.sock", "mount": "ksdf_twr",   "pan": "lavfi=[pan=stereo|c0=0.7*c0|c1=0.7*c0]"},
    {"id": "sec", "sock": "/tmp/mpv_sec.sock", "mount": "ksdf_app_2", "pan": "lavfi=[pan=stereo|c0=0|c1=c0]"}
]

STATE_FILE = "/tmp/atc_status.json"
status_lock = threading.Lock()
feed_statuses = {f["id"]: "down" for f in FEEDS}

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

def audio_worker(feed):
    stream_id = feed["id"]
    sock_path = feed["sock"]
    mount = feed["mount"]
    pan_filter = feed["pan"]

    while True:
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except Exception:
                pass

        with status_lock:
            feed_statuses[stream_id] = "down"

        url = resolve_stream_url(mount)
        cmd = [
            "mpv",
            "--no-video",
            "--idle=yes",
            "--ao=alsa",
            "--alsa-mixer-device=default",
            f"--input-ipc-server={sock_path}",
            f"--af={pan_filter}",
            "--audio-buffer=0.4",
            "--network-timeout=10",
            "--user-agent=Mozilla/5.0",
            url
        ]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)

            while proc.poll() is None:
                is_alive = False

                if os.path.exists(sock_path):
                    try:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                            client.settimeout(0.3)
                            client.connect(sock_path)

                            # Direct ping using core-idle property
                            msg = json.dumps({"command": ["get_property", "core-idle"]}) + "\n"
                            client.sendall(msg.encode('utf-8'))
                            resp = client.recv(1024).decode('utf-8')
                            if resp and "error" in resp and '"error":"success"' in resp:
                                is_alive = True
                    except Exception:
                        is_alive = False

                with status_lock:
                    feed_statuses[stream_id] = "idle" if is_alive else "down"
                    try:
                        with open(STATE_FILE + ".tmp", "w") as sf:
                            json.dump(feed_statuses, sf)
                        os.replace(STATE_FILE + ".tmp", STATE_FILE)
                    except Exception:
                        pass

                time.sleep(0.3)

            proc.wait()
        except Exception:
            pass

        time.sleep(2.0)

for f in FEEDS:
    t = threading.Thread(target=audio_worker, args=(f,), daemon=True)
    t.start()

while True:
    time.sleep(1.0)
