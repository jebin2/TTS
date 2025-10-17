#!/bin/bash
# User-local venv path
USER_VENV="$HOME/.config/tts_tui/kokoro_env"

# Create venv on first run
if [ ! -d "$USER_VENV" ]; then
    echo "==> Creating user-local Python venv at $USER_VENV"
    python -m venv "$USER_VENV"
    source "$USER_VENV/bin/activate"
    pip install --upgrade pip
    pip install -r "$HOME/.config/tts_tui/kokoro_requirements.txt" 2>/dev/null
    pip install -r "$HOME/.config/tts_tui/requirement_tui.txt" 2>/dev/null
    deactivate
fi

# Activate venv and run TTS
source "$USER_VENV/bin/activate"
python "/opt/tts-tui/tui.py" "$@"