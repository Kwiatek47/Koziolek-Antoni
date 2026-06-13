#!/usr/bin/env python3
"""
BIP Lublin RAG - Hybrid Retrieval (Dense + BM25) with RRF fusion.
Uses ChromaDB for dense vectors, rank-bm25 for sparse, and llama-cpp-python for LLM.
"""
import json
import math
import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from llama_cpp import Llama
from rank_bm25 import BM25Okapi

app = FastAPI(
    title="BIP Lublin RAG - Koziołek Antek",
    description="Hybrydowy system RAG oparty na danych BIP Urząd Miasta Lublin",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Config ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.json")
MODEL_PATH = os.getenv(
    "MODEL_PATH",
    os.path.join(os.path.dirname(__file__), "models", "qwen2.5-7b-instruct-q4_k_m.gguf"),
)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sdadas/st-polish-paraphrase-from-distilroberta")
TOP_K = int(os.getenv("TOP_K", "15"))
FINAL_K = int(os.getenv("FINAL_K", "6"))
N_THREADS = int(os.getenv("N_THREADS", "8"))
RRF_K = 60  # RRF constant

# --- Embedding & ChromaDB ---
embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL,
    trust_remote_code=True,
)

chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection(
    name="bip_lublin",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"},
)

# --- BM25 index (built on /index, kept in memory) ---
bm25_corpus: list[str] = []
bm25_ids: list[str] = []
bm25_metadatas: list[dict] = []
bm25_index: Optional[BM25Okapi] = None


def tokenize_pl(text: str) -> list[str]:
    """Simple Polish tokenizer - lowercase, remove punctuation, split."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def build_bm25():
    """Build BM25 index from loaded documents."""
    global bm25_index, bm25_corpus, bm25_ids, bm25_metadatas

    docs_file = DOCUMENTS_FILE
    if not os.path.exists(docs_file):
        return

    with open(docs_file) as f:
        docs = json.load(f)

    bm25_corpus = [d["content"] for d in docs]
    bm25_ids = [d["id"] for d in docs]
    bm25_metadatas = [d["metadata"] for d in docs]

    tokenized = [tokenize_pl(doc) for doc in bm25_corpus]
    bm25_index = BM25Okapi(tokenized)


# --- LLM ---
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=8192,
    n_threads=N_THREADS,
    verbose=False,
)

# --- Pydantic models ---
class Query(BaseModel):
    question: str
    top_k: Optional[int] = None


class Answer(BaseModel):
    answer: str
    sources: list[dict]
    retrieval_info: Optional[dict] = None


class IndexStatus(BaseModel):
    total_documents: int
    indexed: bool


# --- System prompt ---
SYSTEM_PROMPT = """Jesteś Koziołkiem Antkiem – inteligentnym asystentem Urzędu Miasta Lublin. Pomagasz mieszkańcom załatwiać sprawy urzędowe na podstawie danych z BIP (Biuletyn Informacji Publicznej).

ZASADY:
1. Odpowiadaj WYŁĄCZNIE na podstawie podanego kontekstu. NIE wymyślaj informacji.
2. Jeśli w kontekście brak odpowiedzi → powiedz: "Nie znalazłem tej informacji w BIP Lublin."
3. Podawaj KONKRETNE dane: adres, numer pokoju, telefon, godziny, wymagane dokumenty, opłaty, terminy.
4. Rozróżniaj wydziały prawidłowo:
   - "dowód osobisty" → Wydział Spraw Administracyjnych
   - "dowód rejestracyjny", "rejestracja pojazdu" → Wydział Komunikacji
   - "meldunek" → Wydział Spraw Administracyjnych
5. Formatuj odpowiedź:
   - Krótkie podsumowanie (1-2 zdania)
   - Kroki procedury (lista numerowana)
   - Wymagane dokumenty (lista)
   - Adres i godziny
   - Opłaty (jeśli podane)
6. Na końcu podaj źródło URL.
7. Odpowiadaj po polsku, zwięźle."""


def get_llm_response(question: str, context: str) -> str:
    """Generate LLM response with RAG context."""
    user_prompt = f"""KONTEKST Z BIP LUBLIN:
---
{context}
---

PYTANIE MIESZKAŃCA: {question}

Odpowiedz na podstawie kontekstu. Wybierz TYLKO fragmenty bezpośrednio dotyczące pytania (zwróć uwagę na tytuł usługi i wydział). Podaj konkretne informacje: adres, godziny, dokumenty, opłaty, procedurę, źródło URL."""

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    return response["choices"][0]["message"]["content"]


# --- Hybrid retrieval with RRF ---
def hybrid_search(question: str, top_k: int = 15, final_k: int = 6) -> tuple[list[str], list[dict], dict]:
    """
    Hybrid retrieval: dense (ChromaDB) + sparse (BM25), fused with RRF.
    Returns (documents, metadatas, debug_info).
    """
    # Dense search via ChromaDB
    dense_results = collection.query(
        query_texts=[question],
        n_results=top_k,
    )
    dense_ids = dense_results["ids"][0]
    dense_docs = dense_results["documents"][0]
    dense_metas = dense_results["metadatas"][0]
    dense_distances = dense_results["distances"][0]

    # Build id->data lookup
    id_to_doc = {}
    id_to_meta = {}
    for i, did in enumerate(dense_ids):
        id_to_doc[did] = dense_docs[i]
        id_to_meta[did] = dense_metas[i]

    # BM25 sparse search
    bm25_results_ids = []
    if bm25_index is not None:
        query_tokens = tokenize_pl(question)
        bm25_scores = bm25_index.get_scores(query_tokens)
        top_bm25_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k]
        for idx in top_bm25_indices:
            if bm25_scores[idx] > 0:
                bid = bm25_ids[idx]
                bm25_results_ids.append(bid)
                if bid not in id_to_doc:
                    id_to_doc[bid] = bm25_corpus[idx]
                    id_to_meta[bid] = bm25_metadatas[idx]

    # RRF fusion
    rrf_scores: dict[str, float] = {}

    for rank, did in enumerate(dense_ids):
        rrf_scores[did] = rrf_scores.get(did, 0) + 1.0 / (RRF_K + rank + 1)

    for rank, bid in enumerate(bm25_results_ids):
        rrf_scores[bid] = rrf_scores.get(bid, 0) + 1.0 / (RRF_K + rank + 1)

    # Title-based boost
    question_lower = question.lower()
    for did, score in list(rrf_scores.items()):
        meta = id_to_meta.get(did, {})
        title = meta.get("title", "").lower()
        title_words = [w for w in title.split() if len(w) > 3]
        if title_words:
            matching = sum(1 for w in title_words if w in question_lower)
            title_boost = (matching / len(title_words)) * 0.02
            rrf_scores[did] = score + title_boost

    # Sort by RRF score (descending)
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    # Deduplicate by source_url + take top final_k
    final_docs = []
    final_metas = []
    seen_content_hashes = set()

    for did in sorted_ids:
        if len(final_docs) >= final_k:
            break
        doc = id_to_doc.get(did, "")
        content_hash = hash(doc[:200])
        if content_hash in seen_content_hashes:
            continue
        seen_content_hashes.add(content_hash)
        final_docs.append(doc)
        final_metas.append(id_to_meta.get(did, {}))

    debug_info = {
        "dense_top3": dense_ids[:3],
        "bm25_top3": bm25_results_ids[:3],
        "rrf_top3": sorted_ids[:3],
        "dense_count": len(dense_ids),
        "bm25_count": len(bm25_results_ids),
    }

    return final_docs, final_metas, debug_info


# --- Endpoints ---

@app.get("/health")
def health():
    return {
        "status": "ok",
        "documents": collection.count(),
        "bm25_ready": bm25_index is not None,
        "model": os.path.basename(MODEL_PATH),
    }


@app.get("/status", response_model=IndexStatus)
def status():
    return IndexStatus(
        total_documents=collection.count(),
        indexed=collection.count() > 0,
    )


@app.post("/index")
def index_documents():
    """Load documents.json, index into ChromaDB and build BM25."""
    global collection

    if not os.path.exists(DOCUMENTS_FILE):
        raise HTTPException(404, f"Documents file not found: {DOCUMENTS_FILE}")

    with open(DOCUMENTS_FILE) as f:
        docs = json.load(f)

    if collection.count() > 0:
        chroma_client.delete_collection("bip_lublin")
        collection = chroma_client.get_or_create_collection(
            name="bip_lublin",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    batch_size = 100
    seen_ids = set()
    unique_docs = []
    for d in docs:
        doc_id = d["id"]
        while doc_id in seen_ids:
            doc_id += "_"
        seen_ids.add(doc_id)
        d["id"] = doc_id
        unique_docs.append(d)

    for i in range(0, len(unique_docs), batch_size):
        batch = unique_docs[i:i + batch_size]
        collection.add(
            ids=[d["id"] for d in batch],
            documents=[d["content"] for d in batch],
            metadatas=[d["metadata"] for d in batch],
        )

    # Build BM25 index
    build_bm25()

    return {"indexed": len(unique_docs), "bm25_docs": len(bm25_corpus), "status": "ok"}


@app.post("/query", response_model=Answer)
def query(q: Query):
    """Answer a question using hybrid RAG (dense + BM25 + RRF)."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    top_k = q.top_k or TOP_K

    documents, metadatas, debug_info = hybrid_search(q.question, top_k=top_k, final_k=FINAL_K)

    context_parts = []
    sources = []
    seen_urls = set()

    for doc, meta in zip(documents, metadatas):
        context_parts.append(doc)
        url = meta.get("source_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                "url": url,
                "title": meta.get("title", ""),
                "type": meta.get("type", ""),
                "department": meta.get("department", ""),
            })

    context = "\n\n---\n\n".join(context_parts)
    answer = get_llm_response(q.question, context)

    return Answer(answer=answer, sources=sources, retrieval_info=debug_info)


@app.post("/search")
def search(q: Query):
    """Search without LLM - return relevant chunks with hybrid scoring."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    top_k = q.top_k or TOP_K
    documents, metadatas, debug_info = hybrid_search(q.question, top_k=top_k, final_k=top_k)

    hits = []
    for i, (doc, meta) in enumerate(zip(documents, metadatas)):
        hits.append({
            "content": doc[:500],
            "metadata": meta,
            "rank": i + 1,
        })

    return {"results": hits, "retrieval_info": debug_info}


@app.get("/locations")
def get_locations():
    """Return office locations for the map."""
    locations_file = os.path.join(DATA_DIR, "locations.json")
    if os.path.exists(locations_file):
        with open(locations_file) as f:
            return json.load(f)
    return {"locations": []}


@app.on_event("startup")
def startup_event():
    """Build BM25 index on startup if documents exist."""
    if os.path.exists(DOCUMENTS_FILE):
        build_bm25()
        print(f"BM25 index built: {len(bm25_corpus)} documents")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
