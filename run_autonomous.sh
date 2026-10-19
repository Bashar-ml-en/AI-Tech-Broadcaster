#!/usr/bin/env bash
# ==============================================================================
# AutoBroadcaster Autonomous 24/7 Background Manager
# Controls the autonomous AI news ingestion, CEO video rendering, and multi-platform publishing.
#
# Usage:
#   ./run_autonomous.sh start    - Start AutoBroadcaster 24/7 in background
#   ./run_autonomous.sh stop     - Stop the background broadcaster
#   ./run_autonomous.sh restart  - Restart the broadcaster cleanly
#   ./run_autonomous.sh status   - Check live running status & recent cycles
#   ./run_autonomous.sh logs     - Follow real-time execution logs
#   ./run_autonomous.sh trigger  - Trigger an immediate reel broadcast
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PID_FILE="$PROJECT_DIR/storage/broadcaster.pid"
LOG_FILE="$PROJECT_DIR/storage/logs/broadcaster.log"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
UVICORN_BIN="$PROJECT_DIR/.venv/bin/uvicorn"

mkdir -p "$PROJECT_DIR/storage/logs" "$PROJECT_DIR/storage/staging"

is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    # Also check by process name
    if pgrep -f "uvicorn src.webhook_server:app" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "$PID"
            return
        fi
    fi
    pgrep -f "uvicorn src.webhook_server:app" | head -n 1 || true
}

start() {
    if is_running; then
        PID=$(get_pid)
        echo "⚡ AutoBroadcaster is ALREADY running (PID: $PID)"
        echo "   Dashboard: http://localhost:8000/dashboard"
        echo "   Logs: tail -f $LOG_FILE"
        exit 0
    fi

    echo "🚀 Starting AutoBroadcaster in 24/7 autonomous mode..."
    rm -f "$PROJECT_DIR/storage/.cycle.lock"

    # Start with nohup so closing the terminal never kills the agent
    nohup "$UVICORN_BIN" src.webhook_server:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"

    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ AutoBroadcaster successfully started in background (PID: $PID)!"
        echo "   • Multi-Cadence Schedule: Stories (15m), Reels (30m), Posts (60m)"
        echo "   • Local Web Console: http://localhost:8000/dashboard"
        echo "   • Cloud Web Console: https://ai-tech-broadcaster.vercel.app"
        echo "   • View logs anytime: ./run_autonomous.sh logs"
    else
        echo "❌ Failed to start broadcaster. Check logs:"
        tail -n 20 "$LOG_FILE"
        exit 1
    fi
}

stop() {
    echo "🛑 Stopping AutoBroadcaster..."
    PID=$(get_pid)
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null || true
        sleep 1
        kill -9 "$PID" 2>/dev/null || true
    fi
    pkill -f "uvicorn src.webhook_server:app" 2>/dev/null || true
    pkill -f "pipeline.py --sidecar" 2>/dev/null || true
    rm -f "$PID_FILE" "$PROJECT_DIR/storage/.cycle.lock"
    echo "✅ Broadcaster stopped cleanly."
}

status() {
    if is_running; then
        PID=$(get_pid)
        echo "🟢 AutoBroadcaster is RUNNING (PID: $PID)"
        echo "   • Port: 8000 (http://localhost:8000/dashboard)"
        echo "   • Uptime / Process details:"
        ps -p "$PID" -o pid,etime,pcpu,pmem,command
        echo ""
        echo "📋 Latest Activity from Database:"
        sqlite3 "$PROJECT_DIR/storage/published_history.db" "SELECT id, format_type, publish_status, headline, created_at FROM posts ORDER BY id DESC LIMIT 3;"
    else
        echo "🔴 AutoBroadcaster is STOPPED"
        echo "   Start it with: ./run_autonomous.sh start"
    fi
}

logs() {
    echo "📜 Tailing live broadcaster log ($LOG_FILE)... (Press Ctrl+C to exit)"
    tail -f "$LOG_FILE"
}

trigger() {
    FMT="${2:-reel}"
    echo "⚡ Triggering immediate autonomous broadcast cycle (format: $FMT)..."
    "$PYTHON_BIN" -c "
from src.pipeline import execute_broadcast_cycle
res = execute_broadcast_cycle(target_format='$FMT')
print('Cycle Result:', res)
"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    trigger)
        trigger "$@"
        ;;
    test-tiktok)
        shift
        if [ "$1" == "--publish" ]; then
            "$PYTHON_BIN" manage.py tiktok-test --publish
        else
            "$PYTHON_BIN" manage.py tiktok-test
        fi
        ;;
    *)
        echo "Usage: ./run_autonomous.sh {start|stop|restart|status|logs|trigger [reel|post|story]|test-tiktok [--publish]}"
        exit 1
        ;;
esac
