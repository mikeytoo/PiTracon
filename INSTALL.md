# PiTracon Installation & Deployment Guide

This guide walks through deploying **PiTracon** on a fresh installation of Raspberry Pi OS Lite (64-bit).[cite: 1]

---

## 1. Prerequisites & Base System Setup

1. Flash **Raspberry Pi OS Lite (64-bit)** to a reliable SanDisk MicroSD card using the official Raspberry Pi Imager.[cite: 1]
2. Configure your hostname (e.g., `pitracon`), Wi-Fi credentials, and enable SSH under OS Customization settings before writing.[cite: 1]
3. Insert the card into your Raspberry Pi, boot up, connect via SSH, and ensure system repositories are up to date:[cite: 1]

    sudo apt update && sudo apt upgrade -y[cite: 1]

---

## 2. Install System Dependencies

Install the required runtime libraries, media engines, the audio server, and kernel input packages:[cite: 1]

    sudo apt install -y python3-pip python3-pygame python3-evdev mpv pulseaudio git

PiTracon relies on PulseAudio to handle stream multiplexing and strict HDMI format translation (IEC958). Enable user lingering so the audio server remains active in a headless environment without an active SSH session:

    sudo loginctl enable-linger pi
    systemctl --user enable --now pulseaudio.service

---

## 3. Clone Repository

Clone the project directly into the default `/home/pi/` directory:[cite: 1]

    cd /home/pi[cite: 1]
    git clone https://github.com/mikeytoo/PiTracon.git[cite: 1]
    cd /home/pi/PiTracon[cite: 1]

Ensure all scripts have executable flags set:[cite: 1]

    chmod +x start-pitracon.sh pitracon.py atc-audio.py[cite: 1]

---

## 4. Local Configuration

Create your active runtime configuration from the provided template:[cite: 1]

    cp config.json.example config.json[cite: 1]
    nano config.json[cite: 1]

### Key Parameters to Adjust:[cite: 1]
* **`center_lat` / `center_lon`**: Set your home coordinates or regional airport reference point.[cite: 1]
* **`mount`**: The mount points from your local LiveATC station (identified from `https://www.liveatc.net/play/{mount}.pls`).[cite: 1]
* **`digitizer_max_x` / `digitizer_max_y`**: Maximum native coordinate ceiling of your touchscreen controller (default is `4095` for SiS HID controllers).[cite: 1]

---

## 5. Enable Systemd Appliance Service

To configure PiTracon to run autonomously as a dedicated appliance on boot:[cite: 1]

1. Copy the systemd service unit to the system directory. This unit file includes the `XDG_RUNTIME_DIR` and `PULSE_SERVER` environment variables required to bridge the headless audio gap:[cite: 1]

    sudo cp /home/pi/PiTracon/pitracon.service /etc/systemd/system/[cite: 1]

2. Reload systemd, enable the unit on boot, and start the service:[cite: 1]

    sudo systemctl daemon-reload[cite: 1]
    sudo systemctl enable pitracon.service[cite: 1]
    sudo systemctl start pitracon.service[cite: 1]

---

## 6. Verification & Troubleshooting

Check running service status:[cite: 1]

    sudo systemctl status pitracon.service[cite: 1]

Stream live application logs to diagnose display or network issues:[cite: 1]

    sudo journalctl -u pitracon.service -f[cite: 1]

Inspect active audio IPC sockets and feed status:[cite: 1]

    ls -la /tmp/mpv_*.sock[cite: 1]
    cat /tmp/atc_status.json[cite: 1]
