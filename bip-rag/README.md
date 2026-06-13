# BIP Lublin RAG

System pytań i odpowiedzi oparty na danych z BIP Urzędu Miasta Lublin.
Wykorzystuje RAG (Retrieval-Augmented Generation) z lokalnym LLM.

## Stack

- **Embedding**: `sdadas/st-polish-paraphrase-from-distilroberta` (polski model)
- **Vector DB**: ChromaDB
- **LLM**: Llama 3.1 8B (przez Ollama)
- **API**: FastAPI

## Szybki start

```bash
# 1. Setup (instalacja zależności, modeli, przygotowanie danych)
chmod +x setup.sh start.sh
./setup.sh

# 2. Start serwera
./start.sh

# 3. Zaindeksuj dane (jednorazowo)
curl -X POST http://localhost:8000/index

# 4. Zadaj pytanie
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Jak wyrobić dowód osobisty w Lublinie?"}'
```

## API Endpoints

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/health` | GET | Status serwera |
| `/status` | GET | Liczba zaindeksowanych dokumentów |
| `/index` | POST | Indeksuj dokumenty z `data/documents.json` |
| `/query` | POST | Zadaj pytanie (RAG: wyszukaj + LLM) |
| `/search` | POST | Tylko wyszukiwanie semantyczne (bez LLM) |

## Struktura danych

```
bip-rag/
├── app.py                  # Serwer FastAPI
├── prepare_dataset.py      # Przygotowanie chunków do RAG
├── setup.sh                # Instalacja na serwerze
├── start.sh                # Uruchomienie
├── requirements.txt
├── data/
│   ├── documents.json      # Przetworzone chunki
│   └── chroma_db/          # Baza wektorowa (generowana)
└── ../dane_bip/            # Surowe dane z BIP
    ├── uslugi.json         # 399 kart usług
    ├── struktura_organizacyjna_full.json
    ├── organy_doradcze_full.json
    ├── pdf/                # PDFy główne
    └── pdf_uslugi/         # Załączniki z kart usług
```

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Default | Opis |
|---------|---------|------|
| `EMBEDDING_MODEL` | `sdadas/st-polish-paraphrase-from-distilroberta` | Model embeddingów |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | URL API LLM (Ollama) |
| `LLM_MODEL` | `llama3.1:8b` | Model LLM |
| `LLM_API_KEY` | `ollama` | Klucz API (dla Ollama dowolny) |
| `TOP_K` | `8` | Liczba chunków do kontekstu |
