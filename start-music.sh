#!/bin/bash
cd /home/slooker/player

# Activate virtual environment
export PATH="/home/slooker/player/.venv/bin:$PATH"
export VIRTUAL_ENV="/home/slooker/player/.venv"

# Start music player in foreground
python main.py

# Clean up volume control if music player exits
kill $VOLUME_PID 2>/dev/null

