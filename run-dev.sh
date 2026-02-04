#!/bin/bash
# GigaBoard Full Stack Development
# Starts Backend and Frontend simultaneously

echo "🚀 Starting GigaBoard Full Stack..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/apps/backend"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $(jobs -p) 2>/dev/null
    wait
    echo "✅ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Backend
echo "📦 Starting Backend (port 8000)..."
cd "$SCRIPT_DIR/apps/backend"
"$SCRIPT_DIR/.venv/bin/python" run_dev.py &
BACKEND_PID=$!
sleep 3

# Start Frontend
echo "🎨 Starting Frontend (port 5173)..."
cd "$SCRIPT_DIR"
npm --workspace apps/web run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Services started:"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for all background jobs
wait
