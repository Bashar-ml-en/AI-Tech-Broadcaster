#!/usr/bin/env bash
# ==============================================================================
# AI Tech Broadcaster — macOS Launchd Service Manager
# Keeps the broadcaster agent running 24/7 across reboot, logout, and crashes.
#
# Usage:
#   ./scripts/setup_daemon.sh install   - Install and load launchd background service
#   ./scripts/setup_daemon.sh uninstall - Unload and remove launchd background service
#   ./scripts/setup_daemon.sh start     - Start launchd service
#   ./scripts/setup_daemon.sh stop      - Stop launchd service
#   ./scripts/setup_daemon.sh status    - Inspect launchd service status
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_NAME="ai.tech.broadcaster.plist"
SOURCE_PLIST="$SCRIPT_DIR/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"

mkdir -p "$TARGET_DIR" "$PROJECT_DIR/storage/logs"

case "$1" in
    install)
        echo "📦 Installing AI Tech Broadcaster launchd agent to $TARGET_PLIST..."
        cp -f "$SOURCE_PLIST" "$TARGET_PLIST"
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        launchctl load -w "$TARGET_PLIST"
        echo "✅ Launchd agent successfully installed and loaded!"
        echo "   • Service Label: ai.tech.broadcaster"
        echo "   • Auto-start on boot: ENABLED"
        echo "   • Auto-restart on crash: ENABLED"
        echo "   • Logs: $PROJECT_DIR/storage/logs/launchd_stderr.log"
        ;;
    uninstall)
        echo "🛑 Unloading and removing AI Tech Broadcaster launchd agent..."
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        rm -f "$TARGET_PLIST"
        echo "✅ Launchd agent uninstalled cleanly."
        ;;
    start)
        echo "🚀 Starting AI Tech Broadcaster service via launchctl..."
        launchctl start ai.tech.broadcaster
        echo "✅ Service start signaled."
        ;;
    stop)
        echo "🛑 Stopping AI Tech Broadcaster service via launchctl..."
        launchctl stop ai.tech.broadcaster
        echo "✅ Service stop signaled."
        ;;
    status)
        echo "📋 Checking launchctl service status for ai.tech.broadcaster:"
        if launchctl list | grep "ai.tech.broadcaster"; then
            echo "🟢 Launchd service is REGISTERED."
        else
            echo "🔴 Launchd service is NOT registered in launchctl."
        fi
        echo ""
        echo "Process details:"
        pgrep -fl "pipeline.py --sidecar" || echo "No active pipeline.py --sidecar process found."
        ;;
    *)
        echo "Usage: ./scripts/setup_daemon.sh {install|uninstall|start|stop|status}"
        exit 1
        ;;
esac
