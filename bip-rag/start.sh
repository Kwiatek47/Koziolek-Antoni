#!/bin/bash
# Start BIP Lublin RAG server
cd "$(dirname "$0")"
source venv/bin/activate

# Start Ollama in background if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 3
fi

echo "Starting BIP RAG server on port 8000..."
exec python3 app.py
