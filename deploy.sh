#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════╗"
echo "║  Koziołek Antek - Deploy Script v2          ║"
echo "║  Hybrid RAG (Dense + BM25) + Qwen 2.5 7B   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# 1. System deps
echo "[1/5] System dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv poppler-utils curl 2>/dev/null || true

# Install Node.js 20+ via NodeSource
if ! node --version 2>/dev/null | grep -qE "^v(2[0-9]|[3-9])"; then
    echo "  Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# 2. Download Qwen 2.5 7B GGUF model
echo "[2/5] Downloading Qwen 2.5 7B model..."
cd bip-rag
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

mkdir -p models
if [ ! -f models/qwen2.5-7b-instruct-q4_k_m.gguf ]; then
    huggingface-cli download bartowski/Qwen2.5-3B-Instruct-GGUF Qwen2.5-3B-Instruct-Q4_K_M.gguf --local-dir models/
fi

# 3. Prepare data
echo "[3/5] Preparing RAG dataset..."
if [ ! -f data/documents.json ]; then
    python3 prepare_dataset.py
    mkdir -p data
    mv documents.json data/ 2>/dev/null || true
fi

deactivate
cd ..

# 4. Frontend setup
echo "[4/5] Building frontend..."
cd frontend
npm ci --quiet
npm run build

# Copy static assets for standalone mode
cp -r .next/static .next/standalone/.next/
cp -r public .next/standalone/
cd ..

# 5. Create systemd services
echo "[5/5] Creating systemd services..."

sudo tee /etc/systemd/system/bip-backend.service > /dev/null << 'SERVICE'
[Unit]
Description=Koziołek Antek - RAG Backend (Hybrid BM25 + Dense)
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/Kozio-ek-Antoni/bip-rag
ExecStart=/home/user/Kozio-ek-Antoni/bip-rag/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=MODEL_PATH=/home/user/Kozio-ek-Antoni/bip-rag/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf
Environment=N_THREADS=16
Environment=TOP_K=15
Environment=FINAL_K=6

[Install]
WantedBy=multi-user.target
SERVICE

sudo tee /etc/systemd/system/bip-frontend.service > /dev/null << 'SERVICE'
[Unit]
Description=Koziołek Antek - Frontend
After=network.target bip-backend.service

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/Kozio-ek-Antoni/frontend/.next/standalone
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5
Environment=PORT=3000
Environment=HOSTNAME=0.0.0.0
Environment=BACKEND_URL=http://localhost:8000

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable bip-backend bip-frontend
sudo systemctl restart bip-backend
sleep 10
sudo systemctl restart bip-frontend

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  DEPLOY COMPLETE!                           ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Frontend: http://$(hostname -I | awk '{print $1}'):3000       ║"
echo "║  Backend:  http://$(hostname -I | awk '{print $1}'):8000       ║"
echo "║  Model:    Qwen 2.5 7B Instruct Q4_K_M     ║"
echo "║  Search:   Hybrid (Dense + BM25 + RRF)     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "First-time indexing:"
echo "  curl -X POST http://localhost:8000/index"
echo ""
echo "Test query:"
echo "  curl -s -X POST http://localhost:8000/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"question\": \"Jak wyrobić dowód osobisty?\"}' | python3 -m json.tool"
echo ""
echo "Check status:"
echo "  sudo systemctl status bip-backend bip-frontend"
