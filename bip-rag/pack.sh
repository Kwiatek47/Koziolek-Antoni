#!/bin/bash
# Pack everything for transfer to the server
set -e

cd "$(dirname "$0")/.."
ARCHIVE="bip-lublin-rag.tar.gz"

echo "Packing BIP Lublin RAG for server deployment..."

tar -czf "$ARCHIVE" \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='venv' \
    --exclude='chroma_db' \
    bip-rag/ \
    dane_bip/

SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "Created: $ARCHIVE ($SIZE)"
echo ""
echo "Transfer to server:"
echo "  scp $ARCHIVE user@10.8.44.10:~/"
echo ""
echo "On server:"
echo "  tar -xzf $ARCHIVE"
echo "  cd bip-rag"
echo "  chmod +x setup.sh start.sh"
echo "  ./setup.sh"
