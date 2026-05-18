#!/bin/bash

# CRYPTO PULSE SIGNALS - Startup Script

set -e

echo "🚀 Starting CRYPTO PULSE SIGNALS..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check required variables
required_vars=(
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_ADMIN_CHAT_ID"
    "SUPABASE_URL"
    "SUPABASE_KEY"
    "NEWS_API_KEY"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: $var is not set in .env"
        exit 1
    fi
done

echo "✅ Environment variables validated"

# Create necessary directories
mkdir -p logs data charts

echo "✅ Directories created"

# Start with Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "🐳 Starting with Docker Compose..."
    docker-compose up -d
    
    echo ""
    echo "✅ SIGNALFORGE AI started successfully!"
    echo ""
    echo "📊 Services:"
    echo "  - Signal Engine: Running"
    echo "  - API Server: http://localhost:8000"
    echo "  - Dashboard: http://localhost:8501"
    echo ""
    echo "📝 View logs:"
    echo "  docker-compose logs -f"
    echo ""
    
else
    echo "⚠️  Docker Compose not found. Starting manually..."
    
    # Check Python
    if ! command -v python &> /dev/null; then
        echo "❌ Error: Python not found!"
        exit 1
    fi
    
    # Install dependencies
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    
    # Start services in background
    echo "🚀 Starting Signal Engine..."
    nohup python src/main.py > logs/engine.log 2>&1 &
    
    echo "🚀 Starting API Server..."
    nohup uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
    
    echo "🚀 Starting Dashboard..."
    nohup streamlit run src/dashboard/app.py --server.port=8501 > logs/dashboard.log 2>&1 &
    
    echo ""
    echo "✅ SIGNALFORGE AI started successfully!"
    echo ""
    echo "📊 Services:"
    echo "  - Signal Engine: Check logs/engine.log"
    echo "  - API Server: http://localhost:8000"
    echo "  - Dashboard: http://localhost:8501"
    echo ""
fi

echo "🎉 Ready to generate signals!"
