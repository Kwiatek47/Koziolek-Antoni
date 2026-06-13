#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════╗"
echo "║  Asystent Miasta Lublin - Deploy Script     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# 1. System deps
echo "[1/6] System dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv poppler-utils curl nodejs npm docker.io docker-compose-v2 2>/dev/null || true

# 2. Install Ollama
if ! command -v ollama &> /dev/null; then
    echo "[2/6] Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
    systemctl enable ollama 2>/dev/null || true
    systemctl start ollama 2>/dev/null || true
else
    echo "[2/6] Ollama already installed"
fi

# 3. Pull model
echo "[3/6] Pulling LLM model..."
sleep 2
ollama pull llama3.1:8b

# 4. Backend setup
echo "[4/6] Setting up backend..."
cd bip-rag
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Prepare data if not done
if [ ! -f data/documents.json ]; then
    echo "  Preparing RAG dataset..."
    python3 prepare_dataset.py
    mkdir -p data
    mv documents.json data/ 2>/dev/null || true
fi

deactivate
cd ..

# 5. Frontend setup
echo "[5/6] Setting up frontend..."
cd frontend
npm ci --quiet
npm run build
cd ..

# 6. Create systemd services
echo "[6/6] Creating services..."

sudo tee /etc/systemd/system/bip-backend.service > /dev/null << 'SERVICE'
[Unit]
Description=BIP Lublin RAG Backend
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/Kozio-ek-Antoni/bip-rag
ExecStart=/home/user/Kozio-ek-Antoni/bip-rag/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=MODEL_PATH=/home/user/Kozio-ek-Antoni/bip-rag/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf
Environment=N_THREADS=8

[Install]
WantedBy=multi-user.target
SERVICE

sudo tee /etc/systemd/system/bip-frontend.service > /dev/null << 'SERVICE'
[Unit]
Description=BIP Lublin Frontend
After=network.target bip-backend.service

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/frontend
ExecStart=/usr/bin/node /home/user/frontend/.next/standalone/server.js
Restart=always
RestartSec=5
Environment=PORT=3000
Environment=BACKEND_URL=http://localhost:8000

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable bip-backend bip-frontend
sudo systemctl start bip-backend
sleep 3
sudo systemctl start bip-frontend

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  DEPLOY COMPLETE!                           ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Frontend: http://$(hostname -I | awk '{print $1}'):3000  ║"
echo "║  Backend:  http://$(hostname -I | awk '{print $1}'):8000  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "First-time indexing (run once):"
echo "  curl -X POST http://localhost:8000/index"
echo ""
echo "Check status:"
echo "  sudo systemctl status bip-backend bip-frontend"
