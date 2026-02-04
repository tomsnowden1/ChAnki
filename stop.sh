#!/bin/bash
# ChAnki v2 - Shutdown Script

echo "🛑 Stopping ChAnki server..."

# Find and kill process on port 5173
PID=$(lsof -i :5173 | grep LISTEN | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "   No server running on port 5173"
else
    kill $PID 2>/dev/null
    echo "✅ Server stopped (PID: $PID)"
fi
