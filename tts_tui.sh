#!/bin/bash
# ~/.local/bin/tts-tui or /usr/bin/tts-tui

APP_DIR="/opt/tts-tui"
USER_VENV="$HOME/.config/tts_tui/kokoro_env"
PY_VERSION="3.10.12"
REQUIREMENTS_MAIN="$APP_DIR/requirement_tui.txt"
REQUIREMENTS_KOKORO="$APP_DIR/kokoro_requirements.txt"
APP_ENTRY="$APP_DIR/tui.py"

# === Ensure pyenv + Python 3.10.12 installed ===
if command -v pyenv >/dev/null 2>&1; then
    if ! pyenv versions --bare | grep -qx "$PY_VERSION"; then
        echo "==> Installing Python $PY_VERSION via pyenv..."
        pyenv install "$PY_VERSION" || {
            echo "Error: pyenv failed to install Python $PY_VERSION"
            exit 1
        }
    fi
    PYTHON_BIN="$(pyenv prefix "$PY_VERSION")/bin/python"
else
    echo "⚠️ pyenv not found; trying system Python 3.10.12..."
    PYTHON_BIN="$(command -v python3.10 || command -v python3 || command -v python)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Error: No suitable Python interpreter found."
    exit 1
fi

echo "Using Python: $PYTHON_BIN"

# === Create venv if missing ===
if [ ! -d "$USER_VENV" ]; then
    echo "==> Creating venv at $USER_VENV (Python $PY_VERSION)"
    "$PYTHON_BIN" -m venv "$USER_VENV"
    source "$USER_VENV/bin/activate"
    pip install --upgrade pip setuptools wheel
    pip install -r "$REQUIREMENTS_KOKORO"
    pip install -r "$REQUIREMENTS_MAIN"
    deactivate
fi

# === Run app function ===
run_app() {
    source "$USER_VENV/bin/activate"
    python "$APP_ENTRY" "$@"
    local STATUS=$?
    deactivate
    return $STATUS
}

# === Attempt run ===
run_app "$@"
EXIT_CODE=$?

# === Auto repair if failed ===
if [ $EXIT_CODE -ne 0 ]; then
    echo "==> Dependency repair in progress..."
    source "$USER_VENV/bin/activate"
    pip install --upgrade pip setuptools wheel
    pip install --force-reinstall -r "$REQUIREMENTS_KOKORO"
    pip install --force-reinstall -r "$REQUIREMENTS_MAIN"
    deactivate
    echo "==> Retrying launch..."
    run_app "$@"
fi
