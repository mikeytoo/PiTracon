# PiTracon Installation & Deployment Guide

This guide walks through deploying **PiTracon** on a fresh installation of Raspberry Pi OS Lite (64-bit).

---

## 1. Prerequisites & Base System Setup

1. Flash **Raspberry Pi OS Lite (64-bit)** to a high-end MicroSD card using the official Raspberry Pi Imager.
2. Configure your hostname (e.g., `pitracon`), Wi-Fi credentials, and enable SSH under OS Customization settings before writing.
3. Insert the card into your Raspberry Pi, boot up, connect via SSH, and ensure system repositories are up to date:

    sudo apt update && sudo apt upgrade -y

---

## 2. Install System Dependencies

Install the required runtime libraries, media engines, and kernel input packages:

    sudo apt install -y python3-pip python3-pygame python3-evdev mpv alsa-utils git

Verify that your audio output device is detected and accessible:

    aplay -l

---

## 3. Clone Repository

Clone the project directly into the default `/home/pi/` directory:

    cd /home/pi
    git clone https://github.com/mikeytoo/PiTracon.git
    cd /home/pi/PiTracon

Ensure all scripts have executable flags set:

    chmod +x start-pitracon.sh pitracon.py atc-audio.py

---

## 4. Local Configuration

Create your active runtime configuration from the provided template:

    cp config.json.example config.json
    nano config.json

### Key Parameters to Adjust:
* **`center_lat` / `center_lon`**: Set your home coordinates or regional airport reference point.
* **`mount`**: The mount points from your local LiveATC station (identified from `https://www.liveatc.net/play/{mount}.pls`).
* **`digitizer_max_x` / `digitizer_max_y`**: Maximum native coordinate ceiling of your touchscreen controller (default is `4095` for SiS HID controllers).

---

## 5. Enable Systemd Appliance Service

To configure PiTracon to run autonomously as a dedicated appliance on boot:

1. Copy the systemd service unit to the system directory:

    sudo cp /home/pi/PiTracon/pitracon.service /etc/systemd/system/

2. Reload systemd, enable the unit on boot, and start the service:

    sudo systemctl daemon-reload
    sudo systemctl enable pitracon.service
    sudo systemctl start pitracon.service

---

## 6. Verification & Troubleshooting

Check running service status:

    sudo systemctl status pitracon.service

Stream live application logs to diagnose display or network issues:

    sudo journalctl -u pitracon.service -f

Inspect active audio IPC sockets and feed status:

    ls -la /tmp/mpv_*.sock
    cat /tmp/atc_status.json
