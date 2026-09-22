#!/usr/bin/env python3
import sys, math, time, threading, urllib.request, json, os, socket, subprocess
import pygame
from evdev import InputDevice, ecodes

# --- Display & Sector Geometry (Ekron, KY) ---
SCREEN_W, SCREEN_H = 1920, 1280
CENTER = (SCREEN_W // 2, SCREEN_H // 2)

CENTER_LAT = 37.9300
CENTER_LON = -86.1790
POLL_RADIUS_NM = 65
COS_CENTER_LAT = math.cos(math.radians(CENTER_LAT))

# Range Settings (Cyclable: 60 -> 45 -> 30 -> 15)
RANGES = [60, 45, 30, 15]
current_range_idx = 0
CURRENT_RANGE_NM = RANGES[current_range_idx]
NM_SCALE = (SCREEN_H // 2 - 40) / CURRENT_RANGE_NM

# Tactical Colors
C_BG           = (8, 12, 10)
C_GRID_DIM     = (26, 42, 34)
C_GRID_BRIGHT  = (48, 80, 62)
C_TARGET_NORM  = (0, 255, 130)
C_TARGET_SEL   = (255, 195, 0)
C_ROUTE_CYAN   = (100, 225, 255)
C_LEADER       = (0, 210, 110)
C_STRIP_BG     = (16, 26, 22)
C_STRIP_BORDER = (0, 230, 120)

C_BTN_ON_BG    = (14, 40, 25)
C_BTN_ON_TXT   = (0, 255, 130)
C_BTN_MUT_BG   = (45, 15, 15)
C_BTN_MUT_TXT  = (255, 70, 70)

# Live RF Comm Status Colors
C_COMM_TX_BG   = (15, 45, 65)
C_COMM_TX_TXT  = (0, 215, 255)
C_COMM_TX_BDR  = (0, 180, 255)

C_COMM_DOWN_BG  = (50, 42, 10)
C_COMM_DOWN_TXT = (255, 205, 50)
C_COMM_DOWN_BDR = (230, 170, 0)

# --- Common Airframe Decode Table (Instant 0ms cache) ---
TYPE_DECODE_TABLE = {
    # Heavies & Cargo (UPS Core)
    "B763": "Boeing 767-300",
    "B762": "Boeing 767-200",
    "B752": "Boeing 757-200",
    "B744": "Boeing 744-400",
    "B748": "Boeing 747-8F",
    "B77L": "Boeing 777F",
    "B772": "Boeing 777-200",
    "B77W": "Boeing 777-300ER",
    "MD11": "McDonnell Douglas MD-11",
    "A306": "Airbus A300-600",
    "A332": "Airbus A330-200",
    "A333": "Airbus A330-300",
    # Commercial Narrowbody
    "B737": "Boeing 737-700",
    "B738": "Boeing 737-800",
    "B739": "Boeing 737-900",
    "B38M": "Boeing 737 MAX 8",
    "B39M": "Boeing 737 MAX 9",
    "A319": "Airbus A319",
    "A320": "Airbus A320",
    "A321": "Airbus A321",
    "A20N": "Airbus A320neo",
    "A21N": "Airbus A321neo",
    "BCS1": "Airbus A220-100",
    "BCS3": "Airbus A220-300",
    # Regionals & Feeders
    "E170": "Embraer E170",
    "E75L": "Embraer E175",
    "E190": "Embraer E190",
    "CRJ2": "Bombardier CRJ-200",
    "CRJ7": "Bombardier CRJ-700",
    "CRJ9": "Bombardier CRJ-900",
    "C208": "Cessna 208 Caravan",
    "SW4":  "Fairchild Metro III",
    # General Aviation & Trainers
    "C172": "Cessna 172 Skyhawk",
    "C182": "Cessna 182 Skylane",
    "C210": "Cessna 210 Centurion",
    "P28A": "Piper PA-28 Cherokee",
    "PA32": "Piper PA-32 Saratoga",
    "PA44": "Piper PA-44 Seminole",
    "BE36": "Beechcraft Bonanza",
    "BE58": "Beechcraft Baron",
    "SR20": "Cirrus SR20",
    "SR22": "Cirrus SR22",
    "DA40": "Diamond DA40 Star",
    "DA42": "Diamond DA42 Twin Star",
    # Bizjets & Turboprops
    "BE20": "Beechcraft Super King Air 200",
    "B350": "Beechcraft Super King Air 350",
    "PC12": "Pilatus PC-12",
    "C56X": "Cessna Citation Excel",
    "C25A": "Cessna Citation CJ2",
    "C680": "Cessna Citation Sovereign",
    "GLF5": "Gulfstream V / G550",
    "GLF6": "Gulfstream G650",
    "E55P": "Embraer Phenom 300",
    "CL35": "Bombardier Challenger 350",
    # Military
    "C130": "Lockheed C-130 Hercules",
    "C30J": "Lockheed Martin C-130J Super Hercules",
    "C17":  "Boeing C-17 Globemaster III",
    "KC46": "Boeing KC-46 Pegasus",
    "K35R": "Boeing KC-135 Stratotanker",
    "UH60": "Sikorsky UH-60 Black Hawk",
    "CH47": "Boeing CH-47 Chinook",
    "AH64": "Boeing AH-64 Apache",
    "T38":  "Northrop T-38 Talon"
}

# --- Hardware Input Pipe (SiS 4095 Controller with Auto-Reconnect) ---
touch_queue = []
touch_is_down = False
current_touch_pos = (0, 0)
touch_lock = threading.Lock()
running = True

def find_sis_device():
    for p in ["/dev/input/event0", "/dev/input/event1", "/dev/input/event2"]:
        if os.path.exists(p):
            try:
                d = InputDevice(p)
                if "touch" in d.name.lower() or "sis" in d.name.lower():
                    return d
            except Exception:
                pass
    return None

def touch_worker():
    global running, touch_is_down, current_touch_pos
    while running:
        dev = find_sis_device()
        if not dev:
            time.sleep(1.0)
            continue
        try:
            raw_x, raw_y = 0, 0
            MAX_X, MAX_Y = 4095.0, 4095.0

            for event in dev.read_loop():
                if not running:
                    break
                if event.type == ecodes.EV_ABS:
                    if event.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_X):
                        raw_x = event.value
                    elif event.code in (ecodes.ABS_MT_POSITION_Y, ecodes.ABS_Y):
                        raw_y = event.value
                elif event.type == ecodes.EV_KEY and event.code in (ecodes.BTN_TOUCH, ecodes.BTN_LEFT):
                    sx = max(0, min(SCREEN_W - 1, int((raw_x / MAX_X) * SCREEN_W)))
                    sy = max(0, min(SCREEN_H - 1, int((raw_y / MAX_Y) * SCREEN_H)))
                    with touch_lock:
                        if event.value == 1:
                            touch_is_down = True
                            current_touch_pos = (sx, sy)
                            touch_queue.append(('DOWN', sx, sy))
                        elif event.value == 0:
                            touch_is_down = False
                            touch_queue.append(('UP', sx, sy))
        except Exception:
            with touch_lock:
                touch_is_down = False
            time.sleep(1.0)

threading.Thread(target=touch_worker, daemon=True).start()

# --- Touch Targets & UI Geometry ---
RANGE_BTN_RECT = pygame.Rect(SCREEN_W - 410, 30, 370, 48)

comm_buttons = {
    "APP": {"rect": pygame.Rect(SCREEN_W - 410, 88, 115, 48), "sock": "/tmp/mpv_app.sock", "muted": False},
    "TWR": {"rect": pygame.Rect(SCREEN_W - 282, 88, 115, 48), "sock": "/tmp/mpv_twr.sock", "muted": False},
    "SEC": {"rect": pygame.Rect(SCREEN_W - 155, 88, 115, 48), "sock": "/tmp/mpv_sec.sock", "muted": False}
}

SYS_BTN_RECT   = pygame.Rect(SCREEN_W - 190, SCREEN_H - 150, 150, 48)
SHUTDOWN_RECT  = pygame.Rect(SCREEN_W - 190, SCREEN_H - 88, 150, 48)
SYS_CARD_RECT  = pygame.Rect(SCREEN_W - 440, SCREEN_H - 365, 400, 200)

# Expanded Flight Strip for 4 lines of data
STRIP_RECT     = pygame.Rect(40, SCREEN_H - 200, 435, 160)

show_sys_card = False

def toggle_mpv_mute(btn_key):
    btn = comm_buttons[btn_key]
    btn["muted"] = not btn["muted"]
    sock_path = btn["sock"]
    if os.path.exists(sock_path):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.2)
                client.connect(sock_path)
                msg = json.dumps({"command": ["set_property", "mute", btn["muted"]]}) + "\n"
                client.sendall(msg.encode('utf-8'))
        except Exception:
            pass

# --- Fast System Diagnostics ---
sys_stats = {"cpu": "0%", "temp": "0C", "mem": "0/0MB", "disk": "0GB", "wifi": "OFFLINE"}
prev_idle, prev_total = 0, 0

def sys_monitor_worker():
    global sys_stats, prev_idle, prev_total
    while running:
        try:
            with open('/proc/stat', 'r') as f:
                fields = [float(x) for x in f.readline().strip().split()[1:8]]
                idle = fields[3] + fields[4]
                total = sum(fields)
                diff_idle = idle - prev_idle
                diff_total = total - prev_total
                prev_idle, prev_total = idle, total
                cpu_pct = int(100.0 * (1.0 - (diff_idle / diff_total))) if diff_total > 0 else 0

            temp_c = 0.0
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp_c = int(f.read().strip()) / 1000.0

            mem_total, mem_avail = 0, 0
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal:' in line:
                        mem_total = int(line.split()[1]) // 1024
                    elif 'MemAvailable:' in line:
                        mem_avail = int(line.split()[1]) // 1024
            mem_used = mem_total - mem_avail
            mem_pct = int((mem_used / mem_total) * 100) if mem_total > 0 else 0

            st = os.statvfs('/')
            disk_total = (st.f_blocks * st.f_frsize) / (1024**3)
            disk_free = (st.f_bavail * st.f_frsize) / (1024**3)
            disk_used = disk_total - disk_free

            wifi_status = "OFFLINE"
            try:
                out = subprocess.check_output(["iwgetid", "-r"], timeout=1).decode('utf-8').strip()
                if out:
                    sig = ""
                    if os.path.exists('/proc/net/wireless'):
                        with open('/proc/net/wireless', 'r') as wf:
                            wlines = wf.readlines()
                            if len(wlines) >= 3:
                                parts = wlines[2].split()
                                if len(parts) >= 4:
                                    sig = f"{parts[3].replace('.', '')} dBm"
                    wifi_status = f"{out[:10]} ({sig})" if sig else out[:14]
            except Exception:
                pass

            sys_stats = {
                "cpu": f"{cpu_pct}%",
                "temp": f"{temp_c:.1f}°C",
                "mem": f"{mem_used}/{mem_total}MB ({mem_pct}%)",
                "disk": f"{disk_used:.1f}/{disk_total:.1f}GB",
                "wifi": wifi_status
            }
        except Exception:
            pass
        time.sleep(2.0)

threading.Thread(target=sys_monitor_worker, daemon=True).start()

# --- Target Data Structure ---
class LiveAircraft:
    __slots__ = ('icao', 'callsign', 'lat', 'lon', 'alt', 'speed', 'heading', 'vs', 'last_update', 'x_nm', 'y_nm')

    def __init__(self, icao, callsign, lat, lon, alt_ft, speed_kts, track_deg, vs_fpm):
        self.icao = icao.lower()
        self.callsign = callsign.strip() if callsign.strip() else icao.upper()
        self.lat = lat
        self.lon = lon
        self.alt = alt_ft
        self.speed = speed_kts
        self.heading = track_deg
        self.vs = vs_fpm
        self.last_update = time.time()
        self._calc_nm()

    def update_coords(self, lat, lon, alt_ft, speed_kts, track_deg, vs_fpm):
        self.lat = lat
        self.lon = lon
        self.alt = alt_ft
        self.speed = speed_kts
        self.heading = track_deg
        self.vs = vs_fpm
        self.last_update = time.time()
        self._calc_nm()

    def _calc_nm(self):
        d_lat = self.lat - CENTER_LAT
        d_lon = self.lon - CENTER_LON
        self.y_nm = -(d_lat * 60.04)
        self.x_nm = d_lon * 60.04 * COS_CENTER_LAT

    def get_interpolated_pos(self, now):
        dt = max(0.0, now - self.last_update)
        if dt > 15.0 or self.speed < 10:
            return self.x_nm, self.y_nm
        dist_nm = (self.speed / 3600.0) * dt
        rad = math.radians(self.heading)
        return self.x_nm + dist_nm * math.sin(rad), self.y_nm - dist_nm * math.cos(rad)

targets = {}
target_lock = threading.Lock()
route_cache = {}
type_cache = {}
model_desc_cache = {}
PERSISTENT_CACHE_FILE = "/home/pi/type_cache.json"

# Load previously learned airframes from disk
if os.path.exists(PERSISTENT_CACHE_FILE):
    try:
        with open(PERSISTENT_CACHE_FILE, "r") as f:
            learned = json.load(f)
            TYPE_DECODE_TABLE.update(learned)
    except Exception:
        pass

def save_learned_type(ac_type, full_name):
    if not ac_type or not full_name or ac_type in TYPE_DECODE_TABLE:
        return
    TYPE_DECODE_TABLE[ac_type] = full_name
    try:
        data = {}
        if os.path.exists(PERSISTENT_CACHE_FILE):
            with open(PERSISTENT_CACHE_FILE, "r") as f:
                data = json.load(f)
        data[ac_type] = full_name
        with open(PERSISTENT_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
last_api_status = "CONNECTING..."
selected_icao = None

# Background Route & Airframe Model Resolver
def route_worker():
    while running:
        lookup_cs = None
        lookup_icao = None
        with target_lock:
            if selected_icao:
                t = targets.get(selected_icao)
                if t:
                    if t.callsign and t.callsign not in route_cache:
                        lookup_cs = t.callsign
                    if selected_icao not in model_desc_cache:
                        lookup_icao = selected_icao

        if lookup_cs and lookup_cs not in route_cache:
            try:
                url = f"https://api.adsbdb.com/v0/callsign/{lookup_cs}"
                req = urllib.request.Request(url, headers={'User-Agent': 'FlightWall/1.0'})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    fr = data.get('response', {}).get('flightroute', {})
                    orig = fr.get('origin', {}).get('icao_code') or fr.get('origin', {}).get('iata_code')
                    dest = fr.get('destination', {}).get('icao_code') or fr.get('destination', {}).get('iata_code')
                    route_cache[lookup_cs] = f"{orig} -> {dest}" if orig and dest else "ROUTE N/A"
            except Exception:
                route_cache[lookup_cs] = "ROUTE N/A"

        # Fallback API check for airframe description if not in local decode table
        if lookup_icao and lookup_icao not in model_desc_cache:
            raw_type = type_cache.get(lookup_icao, "")
            if raw_type in TYPE_DECODE_TABLE:
                model_desc_cache[lookup_icao] = TYPE_DECODE_TABLE[raw_type]
            else:
                try:
                    url = f"https://api.adsbdb.com/v0/aircraft/{lookup_icao}"
                    req = urllib.request.Request(url, headers={'User-Agent': 'FlightWall/1.0'})
                    with urllib.request.urlopen(req, timeout=3.5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        ac = data.get('response', {}).get('aircraft', {})
                        mf = ac.get('manufacturer', '')
                        md = ac.get('type', '')
                        resolved = ""
                        if mf and md:
                            resolved = f"{mf} {md}"
                        elif md:
                            resolved = md
                        
                        if resolved:
                            model_desc_cache[lookup_icao] = resolved
                            if raw_type:
                                save_learned_type(raw_type, resolved)
                        else:
                            model_desc_cache[lookup_icao] = raw_type
                except Exception:
                    model_desc_cache[lookup_icao] = raw_type

        time.sleep(0.5)

threading.Thread(target=route_worker, daemon=True).start()

# ADS-B Poller
def adsb_worker():
    global last_api_status, selected_icao
    url = f"https://api.adsb.lol/v2/point/{CENTER_LAT:.4f}/{CENTER_LON:.4f}/{POLL_RADIUS_NM}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    while running:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                ac_list = data.get('ac', []) or []
                now = time.time()

                with target_lock:
                    for s in ac_list:
                        icao = (s.get('hex') or "").lower()
                        if not icao:
                            continue

                        callsign = (s.get('flight') or "").strip()
                        lat = s.get('lat')
                        lon = s.get('lon')
                        if lat is None or lon is None:
                            continue

                        raw_alt = s.get('alt_baro')
                        if raw_alt == "ground" or raw_alt is None:
                            raw_alt = s.get('alt_geom') or 0
                        alt_ft = int(raw_alt) if isinstance(raw_alt, (int, float)) else 0

                        speed_kts = int(s.get('gs') or 0)
                        track = float(s.get('track') or 0.0)
                        vs_fpm = int(s.get('baro_rate') or 0)
                        ac_type = (s.get('t') or "").strip()

                        if ac_type and icao not in type_cache:
                            type_cache[icao] = ac_type
                            if ac_type in TYPE_DECODE_TABLE:
                                model_desc_cache[icao] = TYPE_DECODE_TABLE[ac_type]

                        if icao in targets:
                            targets[icao].update_coords(lat, lon, alt_ft, speed_kts, track, vs_fpm)
                        else:
                            targets[icao] = LiveAircraft(icao, callsign, lat, lon, alt_ft, speed_kts, track, vs_fpm)

                    dead = [k for k, v in targets.items() if now - v.last_update > 25.0]
                    for k in dead:
                        if selected_icao == k:
                            selected_icao = None
                        del targets[k]

                last_api_status = f"LIVE ({len(ac_list)} ACFT)"
        except Exception:
            last_api_status = "NET RECONNECTING"

        time.sleep(3.8)

threading.Thread(target=adsb_worker, daemon=True).start()

# --- Graphics & Display Subsystem ---
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.mouse.set_visible(False)

font_ring  = pygame.font.Font(None, 32)
font_tag   = pygame.font.Font(None, 33)
font_ui    = pygame.font.Font(None, 40)
font_btn   = pygame.font.Font(None, 32)

font_strip_cs    = pygame.font.Font(None, 46)
font_strip_route = pygame.font.Font(None, 36)
font_strip_desc  = pygame.font.Font(None, 32)
font_strip_info1 = pygame.font.Font(None, 30)
font_strip_info2 = pygame.font.Font(None, 28)

font_sys_title   = pygame.font.Font(None, 32)
font_sys_body    = pygame.font.Font(None, 28)

# Pre-generate Radar Scope Surfaces
scope_surfaces = {}

def build_scope_surface(range_nm):
    surf = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    surf.fill(C_BG)
    scale = (SCREEN_H // 2 - 40) / range_nm

    if range_nm == 60:
        rings = (15, 30, 45, 60)
    elif range_nm == 45:
        rings = (15, 30, 45)
    elif range_nm == 30:
        rings = (5, 10, 20, 30)
    else:  # 15 NM
        rings = (3, 6, 9, 12, 15)

    for r_nm in rings:
        r_px = int(r_nm * scale)
        col = C_GRID_BRIGHT if r_nm == range_nm or r_nm == rings[len(rings)//2] else C_GRID_DIM
        pygame.draw.circle(surf, col, CENTER, r_px, 2 if col == C_GRID_BRIGHT else 1)
        lbl = font_ring.render(f"{r_nm} NM", True, col)
        surf.blit(lbl, (CENTER[0] + 8, CENTER[1] - r_px + 8))

    pygame.draw.line(surf, C_GRID_DIM, (CENTER[0], 0), (CENTER[0], SCREEN_H), 1)
    pygame.draw.line(surf, C_GRID_DIM, (0, CENTER[1]), (SCREEN_W, CENTER[1]), 1)
    pygame.draw.circle(surf, C_GRID_BRIGHT, CENTER, 10, 2)
    surf.blit(font_ui.render("TRACON TERMINAL RADAR - EKRON SECTOR", True, C_GRID_BRIGHT), (40, 40))
    return surf

for r in RANGES:
    scope_surfaces[r] = build_scope_surface(r)

clock = pygame.time.Clock()
shutdown_press_time = None
shutdown_triggered = False

while running:
    now = time.time()
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    # Process Discrete Touch Input
    while touch_queue:
        ev_type, tx, ty = touch_queue.pop(0)
        if ev_type == 'DOWN':
            # 1. Range Cycle Button
            if RANGE_BTN_RECT.collidepoint(tx, ty):
                current_range_idx = (current_range_idx + 1) % len(RANGES)
                CURRENT_RANGE_NM = RANGES[current_range_idx]
                NM_SCALE = (SCREEN_H // 2 - 40) / CURRENT_RANGE_NM
                continue

            # 2. Comm Mute Buttons
            btn_hit = False
            for k, btn in comm_buttons.items():
                if btn["rect"].collidepoint(tx, ty):
                    toggle_mpv_mute(k)
                    btn_hit = True
                    break
            if btn_hit:
                continue

            # 3. System Status Button
            if SYS_BTN_RECT.collidepoint(tx, ty):
                show_sys_card = not show_sys_card
                continue

            # 4. Tap inside active System Card
            if show_sys_card and SYS_CARD_RECT.collidepoint(tx, ty):
                show_sys_card = False
                continue

            # 5. Shutdown Protection Box
            if SHUTDOWN_RECT.collidepoint(tx, ty):
                continue

            # 6. Tap inside Flight Strip Card
            if selected_icao and STRIP_RECT.collidepoint(tx, ty):
                continue

            # 7. Aircraft Target Selection (75px hit radius)
            hit = None
            with target_lock:
                for icao, t in targets.items():
                    x_nm, y_nm = t.get_interpolated_pos(now)
                    sx = CENTER[0] + x_nm * NM_SCALE
                    sy = CENTER[1] + y_nm * NM_SCALE
                    if math.hypot(tx - sx, ty - sy) < 75:
                        hit = icao
                        break

            selected_icao = hit
            if not hit and show_sys_card:
                show_sys_card = False

    # --- Shutdown 2-Second Hold Verification ---
    with touch_lock:
        is_down = touch_is_down
        cx, cy = current_touch_pos

    if is_down and SHUTDOWN_RECT.collidepoint(cx, cy):
        if shutdown_press_time is None:
            shutdown_press_time = now
        elif (now - shutdown_press_time) >= 2.0 and not shutdown_triggered:
            shutdown_triggered = True
            screen.fill((0, 0, 0))
            msg = font_ui.render("SHUTTING DOWN SYSTEM...", True, (255, 70, 70))
            screen.blit(msg, (CENTER[0] - msg.get_width() // 2, CENTER[1] - msg.get_height() // 2))
            pygame.display.flip()
            time.sleep(1.0)
            subprocess.run(["/sbin/poweroff"])
            running = False
            break
    else:
        shutdown_press_time = None

    # --- Fast Frame Render ---
    screen.blit(scope_surfaces[CURRENT_RANGE_NM], (0, 0))

    selected_on_screen = False

    # Render Targets
    with target_lock:
        for icao, t in targets.items():
            x_nm, y_nm = t.get_interpolated_pos(now)
            sx = int(CENTER[0] + x_nm * NM_SCALE)
            sy = int(CENTER[1] + y_nm * NM_SCALE)

            if not (0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H):
                continue

            is_sel = (icao == selected_icao)
            if is_sel:
                selected_on_screen = True

            color = C_TARGET_SEL if is_sel else C_TARGET_NORM

            # 1-minute velocity vector
            leader_len = (t.speed / 60.0) * NM_SCALE
            rad = math.radians(t.heading)
            lx = int(sx + leader_len * math.sin(rad))
            ly = int(sy - leader_len * math.cos(rad))
            pygame.draw.line(screen, C_LEADER if not is_sel else C_TARGET_SEL, (sx, sy), (lx, ly), 3)

            # Target blip & halo
            pygame.draw.circle(screen, color, (sx, sy), 7, 2)
            pygame.draw.circle(screen, color, (sx, sy), 3)
            if is_sel:
                pygame.draw.circle(screen, C_TARGET_SEL, (sx, sy), 36, 2)
                pygame.draw.line(screen, (100, 80, 20), CENTER, (sx, sy), 1)

            # STARS Data Block
            trend = "^" if t.vs > 200 else ("v" if t.vs < -200 else " ")
            alt_fl = f"{int(round(t.alt / 100)):03d}"
            spd_val = f"{int(round(t.speed / 10)):02d}"
            ac_type = type_cache.get(icao, "")

            tx_off, ty_off = sx + 22, sy - 36
            pygame.draw.line(screen, C_GRID_DIM, (sx, sy), (tx_off - 5, ty_off + 12), 1)

            screen.blit(font_tag.render(t.callsign, True, color), (tx_off, ty_off))
            screen.blit(font_tag.render(f"{alt_fl}{trend} {spd_val}", True, color), (tx_off, ty_off + 24))
            if ac_type:
                screen.blit(font_tag.render(ac_type, True, (160, 210, 190) if not is_sel else color), (tx_off, ty_off + 48))

    if selected_icao and not selected_on_screen:
        selected_icao = None

    # Flight Strip Card (Bottom Left - 4 Lines)
    if selected_icao:
        with target_lock:
            sel_t = targets.get(selected_icao)
            if sel_t:
                pygame.draw.rect(screen, C_STRIP_BG, STRIP_RECT)
                pygame.draw.rect(screen, C_STRIP_BORDER, STRIP_RECT, 2)

                # Line 1: Callsign & Route
                screen.blit(font_strip_cs.render(sel_t.callsign, True, C_TARGET_SEL), (55, SCREEN_H - 192))
                route_str = route_cache.get(sel_t.callsign, "FETCHING...")
                screen.blit(font_strip_route.render(route_str, True, C_ROUTE_CYAN), (220, SCREEN_H - 188))

                # Line 2: Decoded Airframe Name
                sel_type = type_cache.get(selected_icao, "----")
                decoded_name = model_desc_cache.get(selected_icao, TYPE_DECODE_TABLE.get(sel_type, sel_type))
                screen.blit(font_strip_desc.render(f"{sel_type}  |  {decoded_name}", True, (130, 220, 240)), (55, SCREEN_H - 150))

                # Line 3: Bearing, Distance & Nav Stats
                x_nm, y_nm = sel_t.get_interpolated_pos(now)
                dist_nm = math.hypot(x_nm, y_nm)
                bearing = (math.degrees(math.atan2(x_nm, -y_nm)) + 360) % 360
                info1 = f"BRG: {int(bearing):03d}°   DIST: {dist_nm:.1f} NM   HDG: {int(sel_t.heading):03d}°"
                screen.blit(font_strip_info1.render(info1, True, (210, 240, 225)), (55, SCREEN_H - 114))

                # Line 4: Altitude, Speed, Climb Rate
                info2 = f"ALT: {sel_t.alt:,d} FT   GS: {sel_t.speed} KT   VS: {sel_t.vs:+d} FPM"
                screen.blit(font_strip_info2.render(info2, True, (170, 210, 190)), (55, SCREEN_H - 80))

    # --- TOP RIGHT CONTROLS ---
    pygame.draw.rect(screen, (16, 26, 22), RANGE_BTN_RECT)
    pygame.draw.rect(screen, C_GRID_BRIGHT, RANGE_BTN_RECT, 2)
    range_lbl = font_btn.render(f"RANGE: {CURRENT_RANGE_NM} NM [ZOOM]", True, C_TARGET_NORM)
    screen.blit(range_lbl, (RANGE_BTN_RECT.x + (RANGE_BTN_RECT.width - range_lbl.get_width()) // 2,
                            RANGE_BTN_RECT.y + (RANGE_BTN_RECT.height - range_lbl.get_height()) // 2))

    # Ingest live RF transmit/down states
    live_comm_states = {}
    if os.path.exists("/tmp/atc_status.json"):
        try:
            with open("/tmp/atc_status.json", "r") as sf:
                live_comm_states = json.load(sf)
        except Exception:
            pass

    for name, b in comm_buttons.items():
        is_mut = b["muted"]
        key_id = name.lower()
        live_st = live_comm_states.get(key_id, "down")

        if is_mut:
            bg_col = C_BTN_MUT_BG
            txt_col = C_BTN_MUT_TXT
            bdr_col = (180, 40, 40)
            lbl_text = f"{name}: MUT"
        elif live_st == "tx":
            # Active RF transmission / squelch break (Cyan / Blue)
            bg_col = C_COMM_TX_BG
            txt_col = C_COMM_TX_TXT
            bdr_col = C_COMM_TX_BDR
            lbl_text = f"{name}: TX"
        elif live_st == "down":
            # Feed disconnected / reconnecting (Yellow / Amber)
            bg_col = C_COMM_DOWN_BG
            txt_col = C_COMM_DOWN_TXT
            bdr_col = C_COMM_DOWN_BDR
            lbl_text = f"{name}: ERR"
        else:
            # Idle / Quiet Carrier (Tactical Green)
            bg_col = C_BTN_ON_BG
            txt_col = C_BTN_ON_TXT
            bdr_col = (0, 180, 90)
            lbl_text = f"{name}: ON"

        pygame.draw.rect(screen, bg_col, b["rect"])
        pygame.draw.rect(screen, bdr_col, b["rect"], 2)

        lbl = font_btn.render(lbl_text, True, txt_col)
        screen.blit(lbl, (b["rect"].x + (b["rect"].width - lbl.get_width()) // 2,
                          b["rect"].y + (b["rect"].height - lbl.get_height()) // 2))
        continue

    # --- BOTTOM RIGHT CONTROLS ---
    sys_bg = (25, 45, 55) if show_sys_card else (16, 26, 30)
    sys_bdr = (0, 200, 240) if show_sys_card else (40, 100, 120)
    pygame.draw.rect(screen, sys_bg, SYS_BTN_RECT)
    pygame.draw.rect(screen, sys_bdr, SYS_BTN_RECT, 2)
    sys_btn_lbl = font_btn.render("SYS: DIAG", True, (0, 230, 255) if show_sys_card else (140, 200, 220))
    screen.blit(sys_btn_lbl, (SYS_BTN_RECT.x + (SYS_BTN_RECT.width - sys_btn_lbl.get_width()) // 2,
                             SYS_BTN_RECT.y + (SYS_BTN_RECT.height - sys_btn_lbl.get_height()) // 2))

    pwr_bg, pwr_bdr, pwr_col, lbl_str = (24, 16, 16), (80, 30, 30), (140, 70, 70), "STANDBY"
    if shutdown_press_time:
        hold_pct = min(1.0, (now - shutdown_press_time) / 2.0)
        pwr_bg, pwr_bdr, pwr_col, lbl_str = (50, 15, 15), (255, 60, 60), (255, 200, 200), "HOLD 2S"
        pygame.draw.rect(screen, (120, 25, 25), (SHUTDOWN_RECT.x, SHUTDOWN_RECT.y, int(SHUTDOWN_RECT.width * hold_pct), SHUTDOWN_RECT.height))

    pygame.draw.rect(screen, pwr_bg, SHUTDOWN_RECT, 0 if not shutdown_press_time else 1)
    pygame.draw.rect(screen, pwr_bdr, SHUTDOWN_RECT, 2)
    pwr_surf = font_btn.render(lbl_str, True, pwr_col)
    screen.blit(pwr_surf, (SHUTDOWN_RECT.x + (SHUTDOWN_RECT.width - pwr_surf.get_width()) // 2,
                           SHUTDOWN_RECT.y + (SHUTDOWN_RECT.height - pwr_surf.get_height()) // 2))

    if show_sys_card:
        pygame.draw.rect(screen, (12, 20, 24), SYS_CARD_RECT)
        pygame.draw.rect(screen, (0, 200, 240), SYS_CARD_RECT, 2)

        hdr_surf = font_sys_title.render("SYSTEM DIAGNOSTICS", True, (0, 230, 255))
        screen.blit(hdr_surf, (SYS_CARD_RECT.x + 18, SYS_CARD_RECT.y + 16))

        lines = [
            f"CPU:  {sys_stats['cpu']} @ {sys_stats['temp']}",
            f"RAM:  {sys_stats['mem']}",
            f"DISK: {sys_stats['disk']} USED",
            f"WIFI: {sys_stats['wifi']}"
        ]
        for idx, l in enumerate(lines):
            screen.blit(font_sys_body.render(l, True, (180, 230, 240)), (SYS_CARD_RECT.x + 18, SYS_CARD_RECT.y + 55 + idx * 30))

    status_msg = f"FEED: {last_api_status}"
    screen.blit(font_tag.render(status_msg, True, (120, 160, 140)), (40, 85))

    pygame.display.flip()
    clock.tick(30)

running = False
pygame.quit()
sys.exit()
