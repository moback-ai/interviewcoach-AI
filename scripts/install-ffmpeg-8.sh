#!/usr/bin/env bash
# Install FFmpeg on Ubuntu API hosts (amd64).
# Prefer static FFmpeg 8.x (BtbN Linux build); fall back to apt if download fails.
#
# Usage (on EC2 as ubuntu):
#   bash scripts/install-ffmpeg-8.sh
#
set -euo pipefail

FFMPEG_MIN_MAJOR=8
INSTALL_DIR="${FFMPEG_INSTALL_DIR:-/opt/ffmpeg-static}"
BIN_DIR="/usr/local/bin"
BUILD_URL="${FFMPEG_STATIC_URL:-https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz}"

need_install() {
  if ! command -v ffmpeg >/dev/null 2>&1; then
    return 0
  fi
  local ver
  ver="$(ffmpeg -version 2>/dev/null | head -1 | sed -n 's/.*ffmpeg version \([0-9]*\).*/\1/p')"
  [[ -z "$ver" || "$ver" -lt "$FFMPEG_MIN_MAJOR" ]]
}

install_via_apt() {
  echo "Installing ffmpeg from apt (Ubuntu packages)..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo apt-get install -y -qq ffmpeg
  hash -r
  ffmpeg -version | head -1
}

install_static() {
  echo "Installing FFmpeg static build (target >= ${FFMPEG_MIN_MAJOR}.x)..."
  local tmp root
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  sudo mkdir -p "$INSTALL_DIR"
  curl -fsSL "$BUILD_URL" -o "$tmp/ffmpeg.tar.xz"
  tar -xJf "$tmp/ffmpeg.tar.xz" -C "$tmp"

  root="$(find "$tmp" -type f -name ffmpeg -executable 2>/dev/null | head -1)"
  if [[ -n "$root" ]]; then
    root="$(dirname "$root")"
  else
    root="$(find "$tmp" -maxdepth 2 -type d -name 'ffmpeg-*' 2>/dev/null | head -1)"
  fi
  if [[ -z "$root" || ! -x "$root/ffmpeg" ]]; then
    echo "Could not locate ffmpeg binary in archive" >&2
    return 1
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
}

if ! need_install; then
  ffmpeg -version | head -1
  echo "FFmpeg ${FFMPEG_MIN_MAJOR}+ already installed — skipping."
  exit 0
fi

if install_static; then
  exit 0
fi

echo "WARN: Static FFmpeg install failed — falling back to apt."
if install_via_apt; then
  echo "FFmpeg available via apt (may be 6.x on Ubuntu LTS; sufficient for audio transcoding)."
  exit 0
fi

echo "WARN: Could not install ffmpeg; deploy continues but audio transcoding may fail."
exit 0
