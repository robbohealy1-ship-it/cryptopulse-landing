#!/bin/bash

# CRYPTO PULSE SIGNALS - Stop Script

echo "🛑 Stopping CRYPTO PULSE SIGNALS..."

if command -v docker-compose &> /dev/null; then
    echo "🐳 Stopping Docker containers..."
    docker-compose down
    echo "✅ All services stopped"
else
    echo "🔍 Finding and stopping processes..."
    
    # Kill Python processes
    pkill -f "src/main.py"
    pkill -f "uvicorn src.api.server"
    pkill -f "streamlit run src/dashboard/app.py"
    
    echo "✅ All services stopped"
fi

echo "👋 CRYPTO PULSE SIGNALS stopped successfully"
