#!/bin/bash
# Dev-only convenience: starts a virtual display + VNC + noVNC web bridge
# inside the playwright container so headed (HEADED=1) Playwright runs can
# be watched live at http://localhost:6080/vnc.html. Not part of the
# container image -- installs on demand into the running container, so it
# must be re-run after the container is recreated (e.g. a resource-limit
# change in docker-compose.yml forces a fresh container).
set -e

if ! command -v x11vnc >/dev/null 2>&1 || ! command -v websockify >/dev/null 2>&1; then
  # The base Playwright image already ships Xvfb, but not x11vnc/novnc --
  # check each tool independently rather than just "is Xvfb there".
  apt-get update -qq
  apt-get install -y -qq xvfb x11vnc novnc websockify
fi

pkill -f "Xvfb :99" 2>/dev/null || true
pkill -f "x11vnc -display :99" 2>/dev/null || true
pkill -f "websockify.*6080" 2>/dev/null || true
sleep 1

Xvfb :99 -screen 0 1280x800x24 > /tmp/xvfb.log 2>&1 &
sleep 2
DISPLAY=:99 x11vnc -display :99 -forever -shared -nopw -rfbport 5900 > /tmp/x11vnc.log 2>&1 &
sleep 1
websockify --web=/usr/share/novnc/ 6080 localhost:5900 > /tmp/novnc.log 2>&1 &
sleep 1

echo "noVNC ready at http://localhost:6080/vnc.html"
