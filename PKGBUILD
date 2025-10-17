# Maintainer: Your Name <you@example.com>
pkgname=tts-tui
pkgver=1.0.0
pkgrel=1
pkgdesc="Minimalistic Textual TTS Reader with Kokoro voice support (Textual UI)"
arch=('any')
url="https://github.com/jebin2/TTS"
license=('MIT')
depends=('python')
makedepends=('git')
source=("https://github.com/jebin2/TTS/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')  # replace with actual checksum

install_dir="/opt/${pkgname}"
desktop_target="/usr/share/applications/TTS.desktop"

build() {
    cd "${srcdir}/TTS-${pkgver}"
    echo "==> Build step completed (no compilation needed)"
}

package() {
    cd "${srcdir}/TTS-${pkgver}"
    echo "==> Creating install directory: ${install_dir}"
    install -dm755 "${pkgdir}/${install_dir}"

    echo "==> Copying runtime scripts..."
    for file in base_tts.py common.py kokoro_requirements.txt kokoro_tts.py \
                README.md requirement_tui.txt tts_runner.py tui.py; do
        echo "    -> Installing $file"
        install -Dm644 "$file" "${pkgdir}/${install_dir}/$file"
    done

    echo "==> Installing desktop entry"
    install -Dm644 TTS.desktop "${pkgdir}/${desktop_target}"

    echo "==> Installing CLI launcher"
    install -Dm755 tts_tui.sh "${pkgdir}/usr/bin/tts-tui"

    echo "==> Package step completed"
}
