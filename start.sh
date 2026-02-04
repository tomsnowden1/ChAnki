#!/bin/bash
# ChAnki v2 - Startup Script

echo "🚀 Starting ChAnki v2..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Check if port 5173 is already in use
if lsof -i :5173 | grep -q LISTEN; then
    echo "⚠️  Server already running on port 5173"
    echo "   Visit: http://localhost:5173"
    exit 0
fi

# Start the server
echo "📡 Starting server on http://localhost:5173"
echo "   Press Ctrl+C to stop"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 5173
