#!/usr/bin/env bash
# start KHOJI OSINT on linux / kali / mac
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 khoji.py "$@"
fi
echo "python3 not found. on kali: sudo apt install python3"
