pkgname=tts-tui
pkgver=1.0.2
pkgrel=1
pkgdesc="Minimalistic Textual TTS Reader with Kokoro voice support (Textual UI)"
arch=('any')
url="https://github.com/jebin2/TTS"
license=('MIT')
depends=('python' 'python-pip')
makedepends=('pyenv')
source=("https://github.com/jebin2/TTS/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')  # replace later with actual checksum

install_dir="/opt/${pkgname}"
desktop_target="/usr/share/applications/TTS.desktop"

build() {
    cd "${srcdir}/TTS-${pkgver}"
    echo "========================================"
    echo "==> BUILD STEP STARTED"
    echo "==> Current directory: $(pwd)"
    echo "==> Setting up Python environment using pyenv..."
    
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

    echo "==> Installing Python 3.10.12 via pyenv (if not already installed)..."
    pyenv install -s 3.10.12
    pyenv local 3.10.12
    echo "==> Python version in use: $(python --version)"

    echo "==> Creating virtual environment kokoro_env..."
    python -m venv kokoro_env
    source kokoro_env/bin/activate

    echo "==> Upgrading pip..."
    pip install --upgrade pip

    echo "==> Installing kokoro requirements..."
    pip install -r kokoro_requirements.txt

    echo "==> Installing TUI requirements..."
    pip install -r requirement_tui.txt

    deactivate
    echo "==> Virtual environment setup completed."
    echo "========================================"
}

package() {
    cd "${srcdir}/TTS-${pkgver}"
    echo "========================================"
    echo "==> PACKAGE STEP STARTED"
    echo "==> Current directory: $(pwd)"
    echo "==> Creating install directory: ${install_dir}"
    install -dm755 "${pkgdir}/${install_dir}"

    echo "==> Copying runtime files..."
    for file in base_tts.py common.py kokoro_requirements.txt kokoro_tts.py \
                README.md requirement_tui.txt tts_runner.py tui.py; do
        echo "    -> Installing $file"
        install -Dm644 "$file" "${pkgdir}/${install_dir}/$file"
    done

    echo "==> Updating Exec path in TTS.desktop"
    sed -i "s|^Exec=.*|Exec=${install_dir}/kokoro_env/bin/python ${install_dir}/tui.py|" TTS.desktop

    echo "==> Installing desktop entry to ${desktop_target}"
    install -Dm644 TTS.desktop "${pkgdir}/${desktop_target}"

    echo "==> Creating symlink for CLI access at /usr/bin/tts-tui"
    install -Dm755 /dev/stdin "${pkgdir}/usr/bin/tts-tui" <<EOF
#!/bin/bash
${install_dir}/kokoro_env/bin/python ${install_dir}/tui.py "\$@"
EOF

    echo "==> Package step completed."
    echo "========================================"
}
