# PiTracon

**PiTracon** is an autonomous, standalone desktop appliance that transforms a Raspberry Pi and touchscreen into an authentic Terminal Radar Approach Control (TRACON) tactical console. 

It provides real-time ADS-B target tracking, dead-reckoned vector prediction, expandable flight progress strips, and multi-channel spatial LiveATC radio feeds with zero-latency touch mutes.

---

## Features

* **Authentic Tactical Radar Display:**
  * Rendered via low-overhead Pygame on raw Linux DRM/KMS framebuffers.
  * Real-time ADS-B target tracking with multi-step range ring rings (15, 30, 45, 60 NM).
  * 3-minute velocity lead vectors and dead-reckoned target interpolation.
  * Dynamic aircraft type resolution with persistent local JSON airframe caching.
* **Spatial Multi-Channel Audio:**
  * Simultaneous multi-stream playback using background `mpv` worker daemons.
  * Native stereo spatial panning (e.g., Approach hard-left, Tower center, Sector hard-right).
  * Zero-latency individual channel muting via UNIX domain IPC sockets.
* **Interactive Touch Controls:**
  * Direct kernel `evdev` touch input processing with auto-reconnecting digitizer threads.
  * Top-right range ring selector and stacked comm audio buttons with live connection status (`ON`, `MUT`, `ERR`).
  * Bottom-left interactive flight strip card detailing selected target metrics.
  * Failsafe 2-second hold-to-shutdown system standby control.
* **Turnkey Appliance Design:**
  * Fully automated `systemd` service integration for silent, unattended headless boot.

---

## Hardware Bill of Materials (BOM)

| Component | Tested Hardware | Notes |
| :--- | :--- | :--- |
| **SBC** | Raspberry Pi Zero 2 W | Quad-core 64-bit ARM; Pi 4/5 also fully supported |
| **Display** | 10.1" - 15.6" Touch Display | HDMI video input + USB HID touch interface |
| **Digitizer** | SiS / Goodix HID Touch Controller | Auto-calibrated via `evdev` scaling |
| **Audio** | USB DAC or 3.5mm Output | Stereo speakers or headphones for spatial separation |
| **Storage** | 16 GB+ MicroSD | Raspberry Pi OS Lite (64-bit recommended) |
| **Power** | 5V 2.5A+ Micro-USB / USB-C | Clean power supply to prevent undervoltage blips |

---

## Architecture Overview

```text
[ ADS-B API Feeds ]                  [ LiveATC Feeds ]
         │                                   │
         ▼                                   ▼
┌──────────────────┐               ┌───────────────────┐
│ pitracon.py      │◄─ IPC State ─►│ atc-audio.py      │
│ (Tactical Radar) │  /tmp/*.sock  │ (3x mpv Workers)  │
└────────┬─────────┘               └─────────┬─────────┘
         │                                   │
         ▼                                   ▼
 [ DRM/KMS Display ]                 [ ALSA Stereo Bus ]
