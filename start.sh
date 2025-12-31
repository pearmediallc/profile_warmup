#!/bin/bash

echo "🚀 Starting Profile Warm-Up Application"
echo "========================================"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Start backend
echo -e "${BLUE}Starting Backend Server...${NC}"
cd backend
pip install -r requirements.txt -q
python server.py &
BACKEND_PID=$!
cd ..

sleep 2

# Start frontend
echo -e "${BLUE}Starting Frontend...${NC}"
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}========================================"
echo "✅ Application Started!"
echo "========================================"
echo ""
echo "📊 Frontend:  http://localhost:3000"
echo "🔌 Backend:   http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo -e "========================================${NC}"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
