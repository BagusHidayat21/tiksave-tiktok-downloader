#!/bin/bash
# Start both backend (FastAPI) and frontend (static HTTP server) simultaneously

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"

# Activate venv and start FastAPI backend on port 8000
echo "[Backend] Starting FastAPI on http://localhost:8000 ..."
cd "$PROJECT_DIR/backend"
"$VENV_PYTHON" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start a simple HTTP server for frontend on port 3000
echo "[Frontend] Starting static server on http://localhost:3000 ..."
cd "$PROJECT_DIR/frontend"
"$VENV_PYTHON" -m http.server 3000 &
FRONTEND_PID=$!

echo ""
echo "Both servers are running:"
echo "  Frontend : http://localhost:3000"
echo "  Backend  : http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop all servers."

# Kill both processes on exit
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
