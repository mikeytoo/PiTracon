# PiTracon

**PiTracon** is an autonomous, standalone desktop appliance that transforms a Raspberry Pi and touchscreen into an authentic Terminal Radar Approach Control (TRACON) tactical console. 

It provides real-time ADS-B target tracking, dead-reckoned vector prediction, expandable flight progress strips, and multi-channel spatial LiveATC radio feeds with zero-latency touch mutes.

---

## Features

* **Authentic Tactical Radar Display:**
  * Rendered via low-overhead Pygame on raw Linux DRM/KMS framebuffers.
  * Real-time ADS-B target tracking with multi-step range rings (15, 30, 45, 60 NM).
  * 3-minute velocity lead vectors and dead-reckoned target interpolation.
  * Dynamic aircraft type resolution with persistent local JSON airframe caching.
* **Spatial Multi-Channel Audio:**
  * Simultaneous multi-stream playback using background `mpv` worker daemons.
  * Native stereo spatial panning (Approach hard-left, Tower center, Sector hard-right).
  * Zero-latency individual channel muting via UNIX domain IPC sockets.
* **Interactive Touch Controls:**
  * Direct kernel `evdev` touch input processing with auto-reconnecting digitizer threads.
  * Top-right range ring selector and stacked comm audio buttons with live connection status (`ON`, `MUT`, `ERR`).
  * Bottom-left interactive flight strip card detailing selected target metrics.
  * Failsafe 2-second hold-to-shutdown system standby control.
* **Turnkey Appliance & Physical Build:**
  * Fully automated `systemd` service integration for silent, unattended headless boot.
  * Includes parametric OpenSCAD source files (`.scad`) for 3D-printing a custom desktop display mount.

---

## Hardware Bill of Materials (BOM)

| Component | Tested Hardware | Notes |
| :--- | :--- | :--- |
| **SBC** | Raspberry Pi Zero 2 W | Quad-core 64-bit ARM; Pi 4/5 also fully supported |
| **Display** | 10.1" - 15.6" Touch Display | HDMI video input + USB HID touch interface |
| **Digitizer** | SiS / Goodix HID Touch Controller | Auto-calibrated via `evdev` scaling |
| **Enclosure** | 3D-Printed Desktop Stand | Parametric OpenSCAD design in `/cad` directory |
| **Audio** | USB DAC or 3.5mm Output | Stereo speakers or headphones for spatial separation |
| **Storage** | 16 GB+ MicroSD | Raspberry Pi OS Lite (64-bit recommended) |
| **Connections** | Micro USB OTG cable, Mini HDMI Cable, USB A to USB C cable | For connecting the Raspberry Pi to the display
| **Power** | 5V 2.5A+ Micro-USB / USB-C | Clean power supply to prevent undervoltage blips |

---

## 3D Printing the Mount

The parametric desktop mount file is located under `cad/display_mount.scad`.

1. Open `cad/display_mount.scad` in [OpenSCAD](https://openscad.org/).
2. Adjust screen dimensions, bezel offsets, or tilt angle if modifying for a different panel.
3. Render (`F6`) and export to `.stl`.
4. Recommended slice settings:
   * **Material:** PETG or PLA
   * **Infill:** 20%–25% (Gyroid or Grid)
   * **Walls/Perimeters:** 3 to 4 walls for structural rigidity around screw bosses

---

## Quickstart

For full step-by-step instructions, see the **[Installation Guide (INSTALL.md)](INSTALL.md)**.

    # 1. Install dependencies
    sudo apt update && sudo apt install -y python3-pygame python3-evdev mpv alsa-utils git

    # 2. Clone repo
    cd /home/pi
    git clone https://github.com/mikeytoo/PiTracon.git
    cd /home/pi/PiTracon

    # 3. Configure
    cp config.json.example config.json
    nano config.json

    # 4. Enable service
    sudo cp pitracon.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now pitracon.service

---

## Touchscreen Controls

* **Range Ring Toggle (Top Right):** Tap to cycle radar view through 60, 45, 30, and 15 NM ranges.
* **Audio Mute Buttons (`APP`, `TWR`, `SEC`):** Tap to instantly mute/unmute individual audio channels. 
  * Green (`ON`): Connected and active.
  * Red (`MUT`): Audio feed muted.
  * Yellow (`ERR`): Connection dropped or resolving mount.
* **Target Flight Strip (Bottom Left):** Tap any active target on the radar scope to pin and inspect speed, altitude, heading, distance, and airframe specs. Tap the strip card to collapse it.
* **Standby / Power Control (Bottom Right):** Press and hold the `STANDBY` button for 2 full seconds to trigger an orderly Linux system shutdown.

## System Requirements
This project uses `mpv` via ALSA for isolated, non-blocking audio streams. 

Install the required dependencies:
\`\`\`bash
sudo apt update
sudo apt install mpv python3-pygame python3-evdev
\`\`\`

## Background Audio Service (systemd)
To ensure the ATC audio mixer runs continuously in the background and restarts on failure, create a systemd service.

1. Create the service file:
\`\`\`bash
sudo nano /etc/systemd/system/atc-audio.service
\`\`\`

2. Paste the following configuration (verify your paths):
\`\`\`ini
[Unit]
Description=ATC Audio MPV Controller
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Environment="XDG_RUNTIME_DIR=/run/user/1000"
WorkingDirectory=/home/pi/PiTracon
ExecStart=/usr/bin/python3 /home/pi/PiTracon/atc-audio.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
\`\`\`

3. Enable and start the service:
\`\`\`bash
sudo systemctl daemon-reload
sudo systemctl enable atc-audio.service
sudo systemctl start atc-audio.service
\`\`\`
---

## License

This project is open-source and released under the [MIT License](LICENSE).
