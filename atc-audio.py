#!/usr/bin/env python3
import subprocess, time, threading, json, os, urllib.request, socket

CONFIG_FILE = "/home/pi/PiTracon/config.json"
STATE_FILE = "/tmp/atc_status.json"

mute_states = {"app": False, "twr": False, "sec": False}
status_lock = threading.Lock()
mute_lock = threading.Lock()
url_cache = {}

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"master_volume": 4.0, "audio_streams": []}

def resolve_stream_url(mount):
    if mount in url_cache:
        return url_cache[mount]
        
    pls_url = f"https://www.liveatc.net/play/{mount}.pls"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        req = urllib.request.Request(pls_url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            for line in resp.read().decode('utf-8', errors='ignore').splitlines():
                if line.strip().startswith("File1="):
                    url = line.strip().split("=", 1)[1]
                    url_cache[mount] = url
                    return url
    except Exception:
        pass
        
    fallback = f"https://s1-fmt2.liveatc.net/{mount}"
    url_cache[mount] = fallback
    return fallback

def write_status(state):
    with status_lock:
        feed_statuses = {"app": state, "twr": state, "sec": state}
        try:
            with open(STATE_FILE + ".tmp", "w") as sf:
                json.dump(feed_statuses, sf)
            os.replace(STATE_FILE + ".tmp", STATE_FILE)
        except Exception:
            pass

def run_socket_server(stream_id, sock_path):
    if os.path.exists(sock_path):
        try:
            os.unlink(sock_path)
        except OSError:
            pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(sock_path)
        server.listen(1)
        while True:
            conn, _ = server.accept()
            with conn:
                data = conn.recv(1024)
                if data:
                    try:
                        req = json.loads(data.decode('utf-8').strip())
                        cmd = req.get("command", [])
                        if len(cmd) == 3 and cmd[0] == "set_property" and cmd[1] == "mute":
                            val = bool(cmd[2])
                            with mute_lock:
                                mute_states[stream_id] = val
                    except Exception:
                        pass
    except Exception:
        pass

for s_id, path in [("app", "/tmp/mpv_app.sock"), ("twr", "/tmp/mpv_twr.sock"), ("sec", "/tmp/mpv_sec.sock")]:
    t_sock = threading.Thread(target=run_socket_server, args=(s_id, path), daemon=True)
    t_sock.start()

def audio_worker():
    initial_start = True
    while True:
        if initial_start:
            write_status("down")
            initial_start = False
            
        config = load_config()
        streams = config.get("audio_streams", [])
        volume = config.get("master_volume", 4.0)
        
        feeds = []
        for stream in streams:
            stream_id = stream.get("id", "center")
            role = stream.get("role", "center")
            mounts = stream.get("mounts", [])
            for m in mounts:
                feeds.append({"stream_id": stream_id, "role": role, "mount": m})
                
        if not feeds:
            time.sleep(5)
            continue
            
        urls = [resolve_stream_url(f["mount"]) for f in feeds]
        
        ffmpeg_cmd = ["ffmpeg", "-nostats", "-hide_banner"]
        filter_parts = []
        amix_inputs = []
        
        with mute_lock:
            current_mutes = mute_states.copy()
            
        for idx, f in enumerate(feeds):
            ffmpeg_cmd.extend(["-i", urls[idx]])
            s_id = f["stream_id"]
            is_muted = current_mutes.get(s_id, False)
            
            if is_muted:
                pan = "c0=0|c1=0"
            else:
                if f["role"] == "left":
                    pan = "c0=c0"
                elif f["role"] == "right":
                    pan = "c1=c0"
                else:
                    pan = "c0=0.7*c0|c1=0.7*c0"
                
            filter_parts.append(f"[{idx}:a]pan=stereo|{pan}[a{idx}]")
            amix_inputs.append(f"[a{idx}]")
            
        amix_str = "".join(amix_inputs) + f"amix=inputs={len(feeds)}:duration=longest:dropout_transition=0,volume={volume}[out]"
        filter_complex = "; ".join(filter_parts) + "; " + amix_str
        
        ffmpeg_cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-f", "alsa", "default"
        ])
        
        try:
            with open("/tmp/ffmpeg_atc.log", "w") as log_file:
                proc = subprocess.Popen(ffmpeg_cmd, stdout=log_file, stderr=log_file)
                # Quick stabilization sleep
                time.sleep(0.5)
                write_status("idle")
                
                last_mutes = current_mutes.copy()
                while proc.poll() is None:
                    time.sleep(0.2)
                    with mute_lock:
                        current_mutes = mute_states.copy()
                    if current_mutes != last_mutes:
                        proc.terminate()
                        break
                        
        except Exception:
            pass
            
        time.sleep(0.1)

t_audio = threading.Thread(target=audio_worker, daemon=True)
t_audio.start()

while True:
    time.sleep(1.0)
