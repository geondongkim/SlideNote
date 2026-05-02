#!/usr/bin/env bash
# SlideNote 개발 서버 일괄 실행 (백엔드 + 프론트엔드)

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/2] 백엔드 실행 (FastAPI :8000)..."
cd "$ROOT/src/backend"
if [ ! -d venv ]; then
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "[2/2] 프론트엔드 실행 (Vite :5173)..."
cd "$ROOT/src/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "SlideNote 실행 중"
echo "  백엔드:    http://localhost:8000"
echo "  프론트엔드: http://localhost:5173"
echo ""
echo "종료: Ctrl+C"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
