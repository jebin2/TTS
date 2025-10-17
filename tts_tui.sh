#!/bin/bash
# ~/.local/bin/tts-tui or /usr/bin/tts-tui

APP_DIR="/opt/tts-tui"
USER_VENV="$HOME/.config/tts_tui/kokoro_env"
PY_VERSION="3.10.12"
REQUIREMENTS_MAIN="$APP_DIR/requirement_tui.txt"
REQUIREMENTS_KOKORO="$APP_DIR/kokoro_requirements.txt"
APP_ENTRY="$APP_DIR/tui.py"

# === Determine Python ===
if command -v pyenv >/dev/null 2>&1; then
    # Ensure Python version installed via pyenv
    if ! pyenv versions --bare | grep -qx "$PY_VERSION"; then
        echo "==> Installing Python $PY_VERSION via pyenv..."
        pyenv install -s "$PY_VERSION" || {
            echo "❌ pyenv failed to install Python $PY_VERSION"
            exit 1
        }
    fi
    PYTHON_BIN="$(pyenv prefix "$PY_VERSION")/bin/python"
else
    # Fallback to system Python >=3.10
    PYTHON_BIN="$(command -v python3.10 || command -v python3 || command -v python)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ No suitable Python found."
    exit 1
fi

echo "Using Python: $PYTHON_BIN"

# === Create venv ===
create_venv() {
    echo "==> Creating fresh venv at $USER_VENV"
    rm -rf "$USER_VENV"
    "$PYTHON_BIN" -m venv "$USER_VENV"
    source "$USER_VENV/bin/activate"
    pip install --upgrade pip setuptools wheel
    pip install -r "$REQUIREMENTS_KOKORO"
    pip install -r "$REQUIREMENTS_MAIN"
    deactivate
}

# Create venv if missing
[ ! -d "$USER_VENV" ] && create_venv

# === Function to run the app ===
run_app() {
    source "$USER_VENV/bin/activate"
    "$USER_VENV/bin/python" "$APP_ENTRY" "$@"
    local STATUS=$?
    deactivate
    return $STATUS
}

# === Attempt run with auto-repair ===
attempt_run() {
    run_app "$@"
    STATUS=$?
    if [ $STATUS -ne 0 ]; then
        echo "==> Python error detected, reinstalling dependencies..."
        source "$USER_VENV/bin/activate"
        pip install --upgrade pip setuptools wheel
        pip install --force-reinstall -r "$REQUIREMENTS_KOKORO"
        pip install --force-reinstall -r "$REQUIREMENTS_MAIN"
        deactivate

        run_app "$@"
        STATUS=$?

        if [ $STATUS -ne 0 ]; then
            echo "==> Launch still failing, recreating venv..."
            create_venv
            run_app "$@"
        fi
    fi
}

attempt_run "$@"
