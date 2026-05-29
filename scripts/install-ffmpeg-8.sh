#!/usr/bin/env bash
# Install FFmpeg 8.1.x static binaries on Ubuntu (amd64).
# Apt on Ubuntu 22.04/24.04 ships FFmpeg 6.x; we need 8.1.1 for parity with upstream.
#
# Usage (on EC2 as ubuntu):
#   bash scripts/install-ffmpeg-8.sh
#
set -euo pipefail

FFMPEG_MIN_MAJOR=8
INSTALL_DIR="${FFMPEG_INSTALL_DIR:-/opt/ffmpeg-static}"
BIN_DIR="/usr/local/bin"
BUILD_URL="${FFMPEG_STATIC_URL:-https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-amd64.tar.xz}"

need_install() {
  if ! command -v ffmpeg >/dev/null 2>&1; then
    return 0
  fi
  local ver
  ver="$(ffmpeg -version 2>/dev/null | head -1 | sed -n 's/.*ffmpeg version \([0-9]*\).*/\1/p')"
  [[ -z "$ver" || "$ver" -lt "$FFMPEG_MIN_MAJOR" ]]
}

if ! need_install; then
  ffmpeg -version | head -1
  echo "FFmpeg ${FFMPEG_MIN_MAJOR}+ already installed — skipping."
  exit 0
fi

echo "Installing FFmpeg static build (target >= ${FFMPEG_MIN_MAJOR}.x)..."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

sudo mkdir -p "$INSTALL_DIR"
curl -fsSL "$BUILD_URL" -o "$tmp/ffmpeg.tar.xz"
tar -xJf "$tmp/ffmpeg.tar.xz" -C "$tmp"
root="$(find "$tmp" -maxdepth 1 -type d -name 'ffmpeg-*-amd64-static' | head -1)"
if [[ -z "$root" ]]; then
  root="$(find "$tmp" -maxdepth 2 -type f -name ffmpeg -printf '%h\n' 2>/dev/null | head -1)"
fi
if [[ -z "$root" || ! -x "$root/ffmpeg" ]]; then
  echo "Could not locate ffmpeg binary in archive" >&2
  exit 1
fi

sudo rsync -a "$root/" "$INSTALL_DIR/"
for bin in ffmpeg ffprobe; do
  if [[ -x "$INSTALL_DIR/$bin" ]]; then
    sudo ln -sf "$INSTALL_DIR/$bin" "$BIN_DIR/$bin"
  fi
done

hash -r
ffmpeg -version | head -1
echo "FFmpeg installed to $INSTALL_DIR (symlinked in $BIN_DIR)"
