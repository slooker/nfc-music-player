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
libasound2-plugins alsa-utils acl curl jq vim

# Clone github repo into `player` directory
git clone https://github.com/slooker/nfc-music-player.git player
cd player

## Python Environment Setup
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies with uv (or pip)
# Alternative with pip:
# pip install adafruit-blinka adafruit-circuitpython-pn532 psutil RPi.GPIO
pip install uv  # if you don't have uv
uv add adafruit-blinka
uv add adafruit-circuitpython-pn532
uv add psutil
uv add RPi.GPIO

## Install Owntone server
cd
git clone https://github.com/owntone/owntone-server.git
cd owntone-server
autoreconf -i
./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --enable-install-user
make
sudo make install

# Setup Software Volume Control
echo 'pcm.softvol {
    type softvol
    slave.pcm "plughw:0,0"
    control { name "Softvol"; card 0 }
}
ctl.softvol { type hw card 0 }

pcm.!default {
    type plug
    slave.pcm "softvol"
}
ctl.!default { type hw card 0 }' > $HOME/.asoundrc

sudo mkdir /home/owntone
sudo chown -R owntone:owntone /home/owntone
# Setup Software Volume Control
sudo -u owntone echo 'pcm.softvol {
    type softvol
    slave.pcm "plughw:0,0"
    control { name "Softvol"; card 0 }
}
ctl.softvol { type hw card 0 }

pcm.!default {
    type plug
    slave.pcm "softvol"
}
ctl.!default { type hw card 0 }' > /home/owntone/.asoundrc



# Finally, create a music directory and add permissions for the owntone user to read it:
mkdir $HOME/music
# allow traversal of parent directories
sudo setfacl -m u:owntone:x /home
sudo setfacl -m u:owntone:x $HOME

# allow read+traverse of the music tree (+ defaults for new files)
sudo setfacl -R -m u:owntone:rx $HOME/music
sudo setfacl -R -d -m u:owntone:rx $HOME/music
```

And then enable the I2C and SPI interfaces
```
sudo raspi-config
# Navigate to: Interface Options > I2C > Enable
# Navigate to: Interface Options > SPI > Enable
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

[all]
# Enable I2S and audio (required for external DAC)
dtparam=i2s=on

# Use the correct overlay for PCM5102 DAC
dtoverlay=hifiberry-dac

# Disable the HDMI output entirely since you don't use a display
hdmi_force_hotplug=0
hdmi_audio=0
hdmi_ignore_audio=1

# Increase I2C timeout
dtparam=i2c_timeout=1000
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=50000

# Reduce audio buffer underruns
dtparam=audio=off
dtparam=spi=on
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


# Move the `music-player.service` file into `/etc/systemd/system` and enable it and the owntone service
sudo mv music-player.service /etc/systemd/system

# Enable the music player as a service and start it
sudo systemctl enable music-player.service
sudo systemctl start music-player.service

# Enable Owntone as a service and start it
sudo systemctl enable owntone.service
sudo systemctl start owntone.service
```
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

## Bonus - Pico W + PN532 (SPI) + PowerBoost 1000C
Bonus device - NFC reader to help you setup your library. 
*(EN power switch + LBO low-battery indicator via resistor divider)*

### PowerBoost 1000C → Pico W (Power, Switch, LBO)

| PowerBoost 1000C | Pico W | Pico Pin # | Notes |
|---|---|---:|---|
| **5V** | **VSYS** | **39** | Main power feed. **Do not** connect 5 V to 3V3. |
| **GND** | **GND** | any (e.g. **28**, **38**) | Common ground. |
| **EN** | **SPST switch → GND** | — | **OFF** when EN is tied to GND; **ON** when left open. (Disables 5 V boost only—unplug Pico USB to fully power down.) |
| **LBO** | **GP22 via divider** | **29** | LBO is active-low and pulled up >3.3 V → **use divider** below. |

#### LBO → GP22 resistor divider (choose one)

> **Wiring:** `LBO ── Rtop ──► GP22 (pin 29) ── Rbottom ──► GND`  
> *(No internal pull-ups in code; read GP22 as a plain input.)*

- **Option A (series build)**  
  - **Rtop = 100 kΩ**  
  - **Rbottom = 100 kΩ + 47 kΩ (series) = 147 kΩ**  
  - Scales 5.0 V → ~2.98 V, 4.2 V → ~2.50 V ✅

- **Option B (parallel build)**  
  - **Rtop = 100 kΩ**  
  - **Rbottom = 220 kΩ ∥ 470 kΩ ≈ 150 kΩ**  
  - Scales 5.0 V → ~3.00 V, 4.2 V → ~2.52 V ✅

---

### PN532 (SPI) → Pico W

| PN532 | Pico W | Pico Pin # | GPIO | Notes |
|---|---|---:|---:|---|
| **SCK** | **SCK1** | **14** | **GP10** | SPI clock |
| **MOSI** | **TX1 (MOSI)** | **15** | **GP11** | SPI MOSI |
| **MISO** | **RX1 (MISO)** | **16** | **GP12** | SPI MISO |
| **SS / SSEL (CS)** | **GPIO** | **11** | **GP8** | Chip-select (as used in code) |
| **RST / RSTPD_N** | **GPIO** | **22** | **GP25** | Reset line |
| **VCC** | **3V3(OUT)** | **36** | — | PN532 is a 3.3 V device |
| **GND** | **GND** | any | — | Common ground |
| **IRQ** *(optional)* | *(NC or chosen GPIO)* | — | — | Not required for SPI with Adafruit driver |

---

### Optional power LED (low current)

- **3V3(OUT) (pin 36) → (2.2–3.3 kΩ) → LED anode → LED cathode → GND**  
  *(Higher resistor = lower drain.)*

---
### Basic Wiring Diagram — Pico W + PN532 (SPI) + PowerBoost 1000C
<!--
Pico W + PN532 (SPI) + PowerBoost 1000C
- PowerBoost 5V -> Pico VSYS
- Common GND
- LBO -> divider (100k top, 147k bottom) -> Pico GP22
- EN -> SPST switch -> GND
- PN532 on 3V3 and SPI1: SCK=GP10(14), MOSI=GP11(15), MISO=GP12(16), CS=GP8(11), RST=GP25(22)
- Optional power LED on 3V3 with 2.2–3.3k
-->
<svg xmlns="http://www.w3.org/2000/svg" width="1150" height="760" viewBox="0 0 1150 760">
  <defs>
    <style>
      .box { fill:#0b1220; stroke:#5a6b9a; stroke-width:2; rx:10; }
      .title { fill:#e6e9ef; font: bold 16px system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
      .label { fill:#c8d0e0; font: 14px system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
      .pin   { fill:#a5b1c8; font: 12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
      .line  { stroke:#9fd68f; stroke-width:2.5; }
      .gline { stroke:#8fb3ff; stroke-width:2.5; }
      .wire  { stroke:#ffc96b; stroke-width:2.5; }
      .spiw  { stroke:#ff9fb2; stroke-width:2.5; }
      .groundsym { stroke:#a5b1c8; stroke-width:2; }
      .res { fill:none; stroke:#ffd86b; stroke-width:2.5; }
      .switch { fill:none; stroke:#e6e9ef; stroke-width:2.5; }
      .dot { fill:#e6e9ef; }
      .note { fill:#93a1ba; font: 12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
    </style>
    <!-- simple resistor symbol -->
    <symbol id="resistor" viewBox="0 0 40 12">
      <polyline class="res" points="0,6 6,6 10,2 14,10 18,2 22,10 26,2 30,10 34,6 40,6"/>
    </symbol>
    <!-- ground symbol -->
    <symbol id="gnd" viewBox="0 0 20 18">
      <line class="groundsym" x1="10" y1="0" x2="10" y2="6"/>
      <line class="groundsym" x1="2" y1="6" x2="18" y2="6"/>
      <line class="groundsym" x1="4" y1="9" x2="16" y2="9"/>
      <line class="groundsym" x1="6" y1="12" x2="14" y2="12"/>
    </symbol>
  </defs>

  <!-- PowerBoost 1000C -->
  <rect x="40" y="70" width="300" height="255" class="box"/>
  <text x="55" y="95" class="title">PowerBoost 1000C</text>
  <!-- PB pins -->
  <text x="55" y="125" class="pin">JST BAT (LiPo 3.7V)</text>
  <text x="55" y="155" class="pin">5V (OUT)</text>
  <text x="55" y="185" class="pin">GND</text>
  <text x="55" y="215" class="pin">EN (enable)</text>
  <text x="55" y="245" class="pin">LBO (Low-Batt, active-low)</text>
  <text x="55" y="275" class="pin">USB (charge)</text>

  <!-- Pico W -->
  <rect x="440" y="40" width="360" height="320" class="box"/>
  <text x="455" y="65" class="title">Raspberry Pi Pico W</text>
  <text x="455" y="95"  class="pin">VSYS (pin 39)</text>
  <text x="455" y="125" class="pin">GND (e.g., pin 28/38)</text>
  <text x="455" y="155" class="pin">3V3 OUT (pin 36)</text>
  <text x="455" y="185" class="pin">GP22 (pin 29) &mdash; LBO sense</text>
  <text x="455" y="215" class="pin">GP10 SCK (pin 14)</text>
  <text x="455" y="235" class="pin">GP11 MOSI (pin 15)</text>
  <text x="455" y="255" class="pin">GP12 MISO (pin 16)</text>
  <text x="455" y="275" class="pin">GP8  CS  (pin 11)</text>
  <text x="455" y="295" class="pin">GP25 RST (pin 22)</text>

  <!-- PN532 -->
  <rect x="860" y="70" width="250" height="270" class="box"/>
  <text x="875" y="95" class="title">PN532 (SPI)</text>
  <text x="875" y="125" class="pin">VCC (3.3V)</text>
  <text x="875" y="145" class="pin">GND</text>
  <text x="875" y="165" class="pin">SCK</text>
  <text x="875" y="185" class="pin">MOSI</text>
  <text x="875" y="205" class="pin">MISO</text>
  <text x="875" y="225" class="pin">SS / CS</text>
  <text x="875" y="245" class="pin">RST</text>
  <text x="875" y="265" class="pin">IRQ (optional)</text>

  <!-- Power connections -->
  <!-- 5V OUT -> VSYS -->
  <line x1="195" y1="155" x2="440" y2="95" class="line"/>
  <circle cx="195" cy="155" r="3" class="dot"/><circle cx="440" cy="95" r="3" class="dot"/>
  <text x="255" y="110" class="label">5V → VSYS</text>

  <!-- GND common -->
  <line x1="155" y1="185" x2="440" y2="125" class="gline"/>
  <circle cx="155" cy="185" r="3" class="dot"/><circle cx="440" cy="125" r="3" class="dot"/>
  <line x1="440" y1="125" x2="860" y2="145" class="gline"/>
  <circle cx="860" cy="145" r="3" class="dot"/>
  <text x="520" y="140" class="label">Common GND</text>

  <!-- EN switch to GND -->
  <line x1="155" y1="215" x2="285" y2="215" class="wire"/>
  <path d="M285,205 L305,215 L285,225" class="switch"/>
  <line x1="305" y1="215" x2="335" y2="215" class="wire"/>
  <use href="#gnd" x="335" y="207"/>
  <text x="200" y="205" class="label">EN → SPST → GND</text>

  <!-- LBO divider to GP22 -->
  <line x1="155" y1="245" x2="345" y2="245" class="wire"/>
  <circle cx="345" cy="245" r="3" class="dot"/>
  <!-- Rtop -->
  <use href="#resistor" x="345" y="239"/>
  <text x="355" y="232" class="note">Rtop 100k</text>
  <!-- Node to GP22 -->
  <line x1="385" y1="245" x2="520" y2="185" class="wire"/>
  <circle cx="520" cy="185" r="3" class="dot"/>
  <text x="430" y="200" class="label">→ GP22 (pin 29)</text>
  <!-- Rbottom to GND (147k = 100k+47k) -->
  <line x1="385" y1="245" x2="385" y2="300" class="wire"/>
  <use href="#resistor" x="365" y="300"/>
  <text x="375" y="295" class="note">Rbottom 100k + 47k (series)</text>
  <line x1="385" y1="312" x2="385" y2="340" class="wire"/>
  <use href="#gnd" x="375" y="340"/>

  <!-- 3V3 to PN532 VCC -->
  <line x1="565" y1="155" x2="860" y2="125" class="line"/>
  <circle cx="565" cy="155" r="3" class="dot"/><circle cx="860" cy="125" r="3" class="dot"/>
  <text x="710" y="140" class="label">3V3 → VCC</text>

  <!-- SPI wires -->
  <!-- SCK -->
  <line x1="565" y1="215" x2="860" y2="165" class="spiw"/>
  <circle cx="565" cy="215" r="3" class="dot"/><circle cx="860" cy="165" r="3" class="dot"/>
  <text x="700" y="190" class="label">SCK (GP10)</text>
  <!-- MOSI -->
  <line x1="565" y1="235" x2="860" y2="185" class="spiw"/>
  <circle cx="565" cy="235" r="3" class="dot"/><circle cx="860" cy="185" r="3" class="dot"/>
  <text x="700" y="210" class="label">MOSI (GP11)</text>
  <!-- MISO -->
  <line x1="565" y1="255" x2="860" y2="205" class="spiw"/>
  <circle cx="565" cy="255" r="3" class="dot"/><circle cx="860" cy="205" r="3" class="dot"/>
  <text x="700" y="230" class="label">MISO (GP12)</text>
  <!-- CS -->
  <line x1="565" y1="275" x2="860" y2="225" class="spiw"/>
  <circle cx="565" cy="275" r="3" class="dot"/><circle cx="860" cy="225" r="3" class="dot"/>
  <text x="700" y="250" class="label">CS (GP8)</text>
  <!-- RST -->
  <line x1="565" y1="295" x2="860" y2="245" class="spiw"/>
  <circle cx="565" cy="295" r="3" class="dot"/><circle cx="860" cy="245" r="3" class="dot"/>
  <text x="700" y="270" class="label">RST (GP25)</text>

  <!-- Optional power LED -->
  <rect x="40" y="360" width="1070" height="340" class="box"/>
  <text x="55" y="385" class="title">Optional: Low-current Power LED</text>
  <text x="55" y="410" class="note">3V3(OUT) (pin 36) → 2.2–3.3kΩ → LED → GND</text>
  <line x1="220" y1="450" x2="360" y2="450" class="line"/>
  <use href="#resistor" x="360" y="444"/>
  <text x="352" y="438" class="note">2.2–3.3kΩ</text>
  <!-- simple LED symbol -->
  <circle cx="420" cy="450" r="7" fill="none" stroke="#e6e9ef" stroke-width="2"/>
  <line x1="427" y1="450" x2="445" y2="450" class="switch"/>
  <line x1="445" y1="450" x2="515" y2="450" class="line"/>
  <use href="#gnd" x="515" y="442"/>
  <text x="220" y="435" class="label">From 3V3(OUT)</text>
  <text x="530" y="465" class="label">GND</text>

  <!-- Footer notes -->
  <text x="55" y="520" class="note">• Pico GPIOs are 3.3 V-only → LBO must be level-shifted with the divider above.</text>
  <text x="55" y="540" class="note">• EN→GND disables the booster’s 5 V; if Pico is also on USB, it will still run from USB.</text>
  <text x="55" y="560" class="note">• PN532 is a 3.3 V device: power from 3V3(OUT), not 5 V.</text>
  <text x="55" y="580" class="note">• SPI1 pins used: SCK=GP10(14), MOSI=GP11(15), MISO=GP12(16), CS=GP8(11), RST=GP25(22).</text>
</svg>



### Notes

- Pico W **GPIOs are 3.3 V-only** → divider on **LBO** is required.  
- For a true master OFF, either unplug Pico USB or add a switch inline between **PowerBoost 5V → VSYS (pin 39)**.  
- Keep PN532 on **3.3 V** (pin 36), not 5 V.  
- Handy ground near GP22: **pin 28 (GND)** is next to **pin 29 (GP22)**.

## License

This project is open source. Feel free to modify and distribute.
