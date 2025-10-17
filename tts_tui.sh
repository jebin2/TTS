#!/bin/bash
# ~/.local/bin/tts-tui or /usr/bin/tts-tui

USER_VENV="$HOME/.config/tts_tui/kokoro_env"
REQUIREMENTS_MAIN="/opt/tts-tui/requirement_tui.txt"
REQUIREMENTS_KOKORO="/opt/tts-tui/kokoro_requirements.txt"
APP_ENTRY="/opt/tts-tui/tui.py"

# Create venv on first run
if [ ! -d "$USER_VENV" ]; then
    echo "==> Creating user-local Python venv at $USER_VENV"
    python -m venv "$USER_VENV"
    source "$USER_VENV/bin/activate"
    pip install --upgrade pip
    pip install -r "$REQUIREMENTS_KOKORO"
    pip install -r "$REQUIREMENTS_MAIN"
    deactivate
fi

# Function to run app safely
run_app() {
    source "$USER_VENV/bin/activate"
    python "$APP_ENTRY" "$@"
    local STATUS=$?
    deactivate
    return $STATUS
}

# Try running app
run_app "$@"
EXIT_CODE=$?

# If it failed due to missing module, reinstall once and retry
if [ $EXIT_CODE -ne 0 ]; then
    echo "==> Detected Python error, attempting dependency repair..."
    source "$USER_VENV/bin/activate"
    pip install --upgrade pip
    pip install --force-reinstall -r "$REQUIREMENTS_KOKORO"
    pip install --force-reinstall -r "$REQUIREMENTS_MAIN"
    deactivate

    echo "==> Retrying launch..."
    run_app "$@"
fi
