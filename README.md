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
sudo apt install -y python3-pip python3-venv git mpg123 alsa-utils i2c-tools \
build-essential git autotools-dev autoconf automake libtool gettext gawk \
gperf bison flex libconfuse-dev libunistring-dev libsqlite3-dev \
libavcodec-dev libavformat-dev libavfilter-dev libswscale-dev libavutil-dev \
libasound2-dev libxml2-dev libgcrypt20-dev libavahi-client-dev zlib1g-dev \
libevent-dev libplist-dev libsodium-dev libjson-c-dev libwebsockets-dev \
libcurl4-openssl-dev libprotobuf-c-dev \
samba samba-common-bin smbclient cifs-utils \
libasound2-plugins alsa-utils acl curl jq
```
And then enable the I2C and SPI interfaces
```
sudo raspi-config
# Navigate to: Interface Options > I2C > Enable
# Navigate to: Interface Options > SPI > Enable
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
#### Install Owntone server
```
git clone https://github.com/owntone/owntone-server.git
cd owntone-server
autoreconf -i
./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --enable-install-user
make
sudo make install
```
Edit the owntone config to add spotify support: 
`nano /etc/owntone.conf`

Change the `audio { }` section like so (assuming your local computer is output 0):
```
audio {
  nickname = "Computer"
  type = "alsa"
  card = "softvol"        # use our PCM by name (from .asoundrc)
  mixer = "Softvol"       # exact control name
  mixer_device = "hw:0"   # control lives on card 0
}
```
You can test that your outputs are set up by running `sudo -u owntone speaker-test -D softvol -c 2 -t sine -l 1`

and add the following under the audio section:
```
spotify {
  bitrate = 3
  base_playlist_disable = true
  artist_override = true
  album_override = true
}
```
Also, change the music path from `/srv/music` to `/home/<your login>/music`.
Finally, create a music directory and add permissions for the owntone user to read it:
```
# allow traversal of parent directories
sudo setfacl -m u:owntone:x /home
sudo setfacl -m u:owntone:x /home/<you>

# allow read+traverse of the music tree (+ defaults for new files)
sudo setfacl -R -m u:owntone:rx /home/<you>/music
sudo setfacl -R -d -m u:owntone:rx /home/<you>/music
```
Finally, go to `http://<raspberry pi ip>:3689/#/settings/online-services` and connect your spotify account

### Audio Configuration
#### Setting Owntone Settings
To see a list of outputs, run this:
```bash
curl -s "http://localhost:3689/api/outputs" | jq .
```
Usually your local pi will be output 0.  


#### Enable I2S Audio
Assuming you are using a Pi Zero 2W, your entire `/boot/firmware/config.txt` should be as follows:
```
# For more options and information see
# http://rptl.io/configtxt
# Some settings may impact device functionality. See link above for details

# Automatically load initramfs files, if found
auto_initramfs=1

# Disable the VC4 GPU driver (No graphics needed)
dtoverlay=vc4-fkms-v3d
disable_fw_kms_setup=1

# Run in 64-bit mode (optional)
arm_64bit=1

# Disable overscan if you don't use a display
disable_overscan=1

# Run at max CPU speed (optional, can be adjusted)
arm_boost=1

# Audio settings for PCM5102 DAC (using I2S interface)
[all]
# Enable I2S and audio (required for external DAC)
dtparam=i2s=on
#dtparam=audio=on
hdmi_audio=0
hdmi_ignore_audio=1

# Use the correct overlay for PCM5102 DAC
dtoverlay=hifiberry-dac

# Disable the HDMI output entirely since you don't use a display
hdmi_force_hotplug=0
dtparam=i2c_arm=on

dtparam=i2c_arm_baudrate=50000

# Increase I2C timeout
dtparam=i2c_timeout=1000

# Reduce audio buffer underruns
dtparam=audio=off
dtparam=spi=on
```

#### Setup Software Volume Control
Create `~/.asoundrc`:
```
pcm.softvol {
    type softvol
    slave.pcm "plughw:0,0"
    control { name "Softvol"; card 0 }
}
ctl.softvol { type hw card 0 }

pcm.!default {
    type plug
    slave.pcm "softvol"
}
ctl.!default { type hw card 0 }
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
```
### Setup Player
Clone the github repo:
```
gh repo clone slooker/nfc-music-player
```
Move the `music-player.service` file into `/etc/systemd/system` and enable it:
```
sudo mv music-player.service /etc/systemd/system

# Enable the music player as a service and start it
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
4. Add to `/home/slooker/player/library.py` (note, you only need one of these, pick which one is relevant for you):
   ```
    # name of spotify playlist
    "<nfc tag string>": {
        "uris": "spotify:playlist:37i9dQZF1DWZLL3REk8t1E",
        "shuffle": "true"
    },
    # name of local album
    "<nfc tag string>": {
        "uris": "library:album:8249546791409011466",
        "shuffle": "false"
    },
   ```

   You can get the spotify playlist id from the url.  For example, https://open.spotify.com/album/7nnNLD5cv828YSFxXaezRm, for this album, you would create an entry below in your `library.py` file:
   ```
   # Perfect Circle - Eat the Elephant
   "<nfc tag string>": {
       "uris": "spotify:playlist:7nnNLD5cv828YSFxXaezRm",
       "shuffle": "true"
   },
   ```

   For a local playlist or album, you would look in Owntone (usually http://owntone.local:3689 or http://<raspberry pi ip>:3689)
   

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
