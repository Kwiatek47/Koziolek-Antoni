#!/bin/bash
set -e

echo "=== BIP Lublin RAG - Setup ==="

# Install system dependencies
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv poppler-utils curl

# Install Ollama for local LLM
if ! command -v ollama &> /dev/null; then
    echo "[2/5] Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo "[2/5] Ollama already installed"
fi

# Create venv and install Python deps
echo "[3/5] Setting up Python environment..."
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Pull LLM model
echo "[4/5] Pulling LLM model (llama3.1:8b)..."
ollama pull llama3.1:8b

# Prepare data
echo "[5/5] Preparing RAG dataset..."
mkdir -p data
if [ -f "../dane_bip/uslugi.json" ]; then
    python3 prepare_dataset.py
    mv documents.json data/
    echo "Dataset ready!"
else
    echo "WARNING: dane_bip not found. Place data in ../dane_bip/ and run:"
    echo "  python3 prepare_dataset.py && mv documents.json data/"
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start the server:"
echo "  cd $(pwd)"
echo "  source venv/bin/activate"
echo "  python3 app.py"
echo ""
echo "Then index the data:"
echo "  curl -X POST http://localhost:8000/index"
echo ""
echo "And query:"
echo '  curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '"'"'{"question": "Jak wyrobić dowód osobisty?"}'"'"''
