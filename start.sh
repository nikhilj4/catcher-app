#!/bin/bash
# start.sh - Master script to run both backend and frontend

echo "Starting Catcher App..."

# Start backend in the background
echo "Starting backend on port 8001..."
(cd backend && python -m uvicorn main:app --reload --port 8001) &
BACKEND_PID=$!

# Wait a second for backend to initialize
sleep 2

# Start frontend
echo "Starting frontend on port 5173..."
(cd frontend && npm run dev)

# When frontend is stopped (Ctrl+C), kill the backend as well
kill $BACKEND_PID
