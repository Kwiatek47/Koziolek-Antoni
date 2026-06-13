#!/bin/bash
# Deploy script for Koziołek Antek
# Usage: ssh user@10.8.44.10 'bash -s' < deploy.sh
# Or copy to server and run: bash deploy.sh

set -e

echo "=== Koziołek Antek - Full Deploy ==="
echo ""

cd ~/Kozio-ek-Antoni

echo "[1/6] Pulling latest from GitHub..."
git pull origin main

echo ""
echo "[2/6] Installing Python dependencies (pymupdf)..."
cd bip-rag
source venv/bin/activate
pip install pymupdf==1.24.0 --quiet

echo ""
echo "[3/6] Re-generating dataset (with PDF support)..."
python prepare_dataset.py

echo ""
echo "[4/6] Restarting backend + re-indexing..."
sudo systemctl restart bip-backend
echo "Waiting 15s for backend startup..."
sleep 15
curl -s -X POST http://localhost:8000/index | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Indexed: {d[\"indexed\"]} docs, BM25: {d[\"bm25_docs\"]}')"

echo ""
echo "[5/6] Building frontend..."
cd ../frontend
npm install --silent
npm run build
cp -r .next/static .next/standalone/.next/
cp -r public .next/standalone/

echo ""
echo "[6/6] Restarting frontend..."
sudo systemctl restart bip-frontend

echo ""
echo "=== Deploy complete! ==="
echo ""
echo "Health check:"
curl -s http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Backend: {d[\"status\"]} | Docs: {d[\"documents\"]} | Cache: {d[\"cache\"][\"size\"]}/{d[\"cache\"][\"max_size\"]}')"
echo ""
echo "App: http://10.8.44.10:3000"
