# NFC Music Player for Raspberry Pi Zero 2W

A touchless music player that uses NFC cards to trigger playback of specific songs or albums, with real-time volume control via rotary encoder.

## Features

- 🎵 **NFC Card Music Triggering** - Place cards to play specific songs or albums
- 🔊 **Real-time Volume Control** - Rotary encoder with hardware volume adjustment
- 💨 **Instant Card Removal Detection** - Music stops immediately when card is removed
- 🔄 **Card Switching** - Change cards mid-song to switch tracks
- 🎛️ **Hardware DAC Audio** - High-quality I2S audio output via PCM5102
- 🔧 **Auto-recovery** - Automatically restarts if NFC communication fails

## Hardware Requirements

### Components
- Raspberry Pi Zero 2W
- PN532 NFC Reader/Writer Module
- PCM5102 I2S DAC Module (with built-in headphone jack)
- Rotary Encoder (KY-040 or similar)
- NFC cards (NTAG213, MIFARE Classic, etc.)

### Pin Connections

#### NFC PN532 Module
| PN532 Pin | Pi Zero Pin | GPIO       | Description                                 |
|-----------|------------|------------|---------------------------------------------|
| VCC       | 17         | -          | 3.3V power (do NOT use 5V)                 |
| GND       | 9          | -          | Ground                                      |
| SCK       | 23         | GPIO11     | SPI Clock                                   |
| MOSI      | 19         | GPIO10     | SPI Master Out / Slave In                   |
| MISO      | 21         | GPIO9      | SPI Master In / Slave Out                   |
| SS / CS   | 26         | GPIO8      | SPI Chip Select                             |
| IRQ       | 22         | GPIO25     | Interrupt pin for card detection (optional)|
| RSTO      | Not used   | -          | Reset pin (optional, can leave unconnected)|

#### PCM5102 I2S DAC
| PCM5102 Pin | Pi Zero Pin | GPIO   | Description                       |
|------------|------------|--------|-----------------------------------|
| VCC        | 1          | 3.3V   | Power (optional, 3.3V supply)     |
| GND        | 6          | GND    | Ground                            |
| DIN        | 40         | GPIO21 | I2S Data Input                     |
| BCK        | 12         | GPIO18 | I2S Bit Clock                      |
| LCK (LRCK) | 35         | GPIO19 | I2S Word Select / Left-Right Clock |

#### Rotary Encoder (Volume Control)
| Encoder Pin | Pi Zero Pin | GPIO | Description |
|-------------|-------------|------|-------------|
| VCC | 3.3V | - | Power |
| GND | GND | - | Ground |
| CLK | Pin 11 | GPIO 17 | Clock |
| DT | Pin 13 | GPIO 27 | Data |
| SW | Pin 15 | GPIO 22 | Switch/Button |

## Software Installation

### System Dependencies
```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv git mpg123 alsa-utils i2c-tools

# Enable I2C interface
sudo raspi-config
# Navigate to: Interface Options > I2C > Enable
```

### Python Environment Setup
```bash
# Create project directory
mkdir -p /home/slooker/player
cd /home/slooker/player

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies with uv (or pip)
pip install uv  # if you don't have uv
uv add adafruit-blinka
uv add adafruit-circuitpython-pn532
uv add psutil
uv add RPi.GPIO

# Alternative with pip:
# pip install adafruit-blinka adafruit-circuitpython-pn532 psutil RPi.GPIO
```

### Audio Configuration

#### Enable I2S Audio
Add to `/boot/firmware/config.txt`:
```
dtparam=i2s=on
dtparam=audio=on
dtoverlay=i2s-dac
hdmi_audio=0
hdmi_ignore_audio=1
```

#### Setup Software Volume Control
Create `~/.asoundrc`:
```
pcm.softvol {
    type softvol
    slave.pcm "hw:0,0"
    control {
        name "SoftMaster"
        card 0
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.!default {
    type plug
    slave.pcm "softvol"
}

ctl.!default {
    type hw
    card 0
}
```

After creating the file, reboot the Pi:
```bash
sudo reboot
```

Verify the volume control exists:
```bash
amixer scontrols
# Should show: Simple mixer control 'SoftMaster',0
```

## Project Setup

### Create Music Directory and Mapping
```bash
# Create music directory
mkdir -p /home/slooker/music

# Create NFC card mapping file
nano /home/slooker/music.csv
```

Add your card mappings to `music.csv`:
```
# UID,filename (relative to music directory)
04A1B2C3,song1.mp3
823E9FAB,album_folder
A4CC7905,another_song.mp3
```

### Copy Project Files
Place these files in `/home/slooker/player/`:
- `music-player.py` - Main NFC music player
- `volume_control_separate.py` - Rotary encoder volume control

## Systemd Service Setup

### Create Startup Script
```bash
nano /home/slooker/player/start_music_player.sh
```

```bash
#!/bin/bash
cd /home/slooker/player

# Activate virtual environment
export PATH="/home/slooker/player/.venv/bin:$PATH"
export VIRTUAL_ENV="/home/slooker/player/.venv"

# Start volume control in background
python volume_control_separate.py &
VOLUME_PID=$!

# Start music player in foreground
python music-player.py

# Clean up volume control if music player exits
kill $VOLUME_PID 2>/dev/null
```

```bash
chmod +x /home/slooker/player/start_music_player.sh
```

### Create Systemd Service
```bash
sudo nano /etc/systemd/system/music-player.service
```

```ini
[Unit]
Description=NFC Music Player with Volume Control
After=sound.service
Wants=sound.service

[Service]
Type=simple
User=slooker
ExecStart=/home/slooker/player/start_music_player.sh
WorkingDirectory=/home/slooker/player
Restart=always
RestartSec=5
Environment=HOME=/home/slooker

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service
```bash
sudo systemctl enable music-player.service
sudo systemctl start music-player.service

# Check status
sudo systemctl status music-player.service

# View logs
sudo journalctl -u music-player.service -f
```

## Usage

### Adding NFC Cards
1. Run the music player to see card UIDs:
   ```bash
   python music-player.py
   ```
2. Place an NFC card near the reader
3. Note the UID that appears (e.g., `A4CC7905`)
4. Add to `/home/slooker/music.csv`:
   ```
   A4CC7905,your_song.mp3
   ```

### Controls
- **Place NFC Card**: Start playing assigned music
- **Remove NFC Card**: Stop playback immediately
- **Rotate Encoder**: Adjust volume (0-100%)
- **Press Encoder**: Toggle mute/unmute
- **Different Card**: Switch to new song instantly

### File Organization
```
/home/slooker/
├── music/
│   ├── song1.mp3
│   ├── song2.mp3
│   ├── album_folder/
│   │   ├── track1.mp3
│   │   └── track2.mp3
│   └── music.csv
└── player/
    ├── .venv/
    ├── music-player.py
    ├── volume_control_separate.py
    └── start_music_player.sh
```

## Troubleshooting

### Check I2C Devices
```bash
sudo i2cdetect -y 1
# Should show PN532 at address 0x24
```

### Test Audio
```bash
# Test speaker output
speaker-test -c 2 -t wav

# Test volume control
amixer sget SoftMaster
amixer sset SoftMaster 75%
```

### View Service Logs
```bash
# Real-time logs
sudo journalctl -u music-player.service -f

# Recent logs
sudo journalctl -u music-player.service --since "10 minutes ago"
```

### Manual Testing
```bash
# Test components individually
cd /home/slooker/player
source .venv/bin/activate

# Test volume control only
python volume_control_separate.py

# Test music player only  
python music-player.py
```

## Technical Notes

- **Volume Control**: Uses ALSA's `softvol` plugin for real-time volume adjustment without interrupting playback
- **Card Removal Detection**: Uses threaded NFC monitoring with watchdog timer for reliable detection during audio playback
- **Auto-Recovery**: Automatically restarts NFC communication if I2C bus becomes unresponsive
- **Hardware Compatibility**: Designed for Pi Zero 2W but should work on other Pi models with GPIO

## License

This project is open source. Feel free to modify and distribute.
