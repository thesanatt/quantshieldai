#!/bin/bash
set -u
JOB="${1:-}"
ACTION="${2:-}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"
DOMAIN="gui/$(id -u)"

usage() {
  echo "Usage: $0 {monitor|feed} {install|uninstall|status|render}"
  exit 1
}

case "$JOB" in
  monitor) LABEL="com.quantengine.monitor"; LOG="$PROJECT_DIR/data/monitor/daemon.log" ;;
  feed)    LABEL="com.quantengine.feed";    LOG="$PROJECT_DIR/data/monitor/feed.log" ;;
  *) usage ;;
esac
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

render() {
  cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
PLIST
  if [ "$JOB" = "monitor" ]; then
    cat << PLIST
        <string>$PYTHON</string>
        <string>-m</string>
        <string>quantshield.live.daemon</string>
        <string>--once</string>
        <string>--auto-execute</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>RunAtLoad</key>
    <true/>
PLIST
  else
    cat << PLIST
        <string>/usr/bin/caffeinate</string>
        <string>-i</string>
        <string>$PROJECT_DIR/scripts/run_intraday_session.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
PLIST
    for wd in 0 1 2 3 4; do
      echo "        <dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>"
    done
    cat << PLIST
    </array>
    <key>RunAtLoad</key>
    <false/>
PLIST
  fi
  cat << PLIST
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:$PROJECT_DIR/venv/bin</string>
    </dict>
</dict>
</plist>
PLIST
}

case "$ACTION" in
  render)
    render
    ;;
  install)
    mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/data/monitor" "$PROJECT_DIR/data/intraday"
    render > "$PLIST_PATH"
    launchctl bootout "$DOMAIN" "$PLIST_PATH" 2>/dev/null
    launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
    echo "$LABEL installed ($PLIST_PATH)"
    ;;
  uninstall)
    launchctl bootout "$DOMAIN" "$PLIST_PATH" 2>/dev/null
    rm -f "$PLIST_PATH"
    echo "$LABEL removed"
    ;;
  status)
    if launchctl print "$DOMAIN/$LABEL" > /dev/null 2>&1; then
      echo "$LABEL LOADED"
    else
      echo "$LABEL NOT LOADED"
    fi
    ;;
  *) usage ;;
esac
