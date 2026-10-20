#!/bin/sh
# Fathom installer: curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/fathom/main/install.sh | sh
# Prefers pipx/pip; falls back to the standalone binary from GitHub Releases.
set -eu
REPO="YOUR_GITHUB_USERNAME/fathom"

if command -v pipx >/dev/null 2>&1; then
  pipx install fathom-shell && exec fathom doctor
fi
if command -v python3 >/dev/null 2>&1 && python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip install --user fathom-shell && echo "Installed. Make sure ~/.local/bin is on your PATH." && exit 0
fi

os=$(uname -s); arch=$(uname -m)
case "$os-$arch" in
  Linux-x86_64)  asset=fathom-linux-x86_64 ;;
  Linux-aarch64|Linux-arm64) asset=fathom-linux-arm64 ;;
  Darwin-arm64)  asset=fathom-macos-arm64 ;;
  Darwin-x86_64) asset=fathom-macos-x86_64 ;;
  *) echo "Unsupported platform $os-$arch; install Python 3.9+ and run: pip install fathom-shell"; exit 1 ;;
esac
dest="${FATHOM_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$dest"
curl -fsSL "https://github.com/$REPO/releases/latest/download/$asset" -o "$dest/fathom"
chmod +x "$dest/fathom"
echo "Installed to $dest/fathom"
