#!/usr/bin/env python3
"""
BIP Lublin RAG - Retrieval Augmented Generation for Lublin city services.
Simple API server with ChromaDB for vector search and local LLM via llama-cpp-python.
"""
import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from llama_cpp import Llama

app = FastAPI(
    title="BIP Lublin RAG",
    description="System pytań i odpowiedzi oparty na danych BIP Urząd Miasta Lublin",
    version="1.0.0",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.json")
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(os.path.dirname(__file__), "models", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sdadas/st-polish-paraphrase-from-distilroberta")
TOP_K = int(os.getenv("TOP_K", "10"))
N_THREADS = int(os.getenv("N_THREADS", "8"))

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

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=4096,
    n_threads=N_THREADS,
    verbose=False,
)


class Query(BaseModel):
    question: str
    top_k: Optional[int] = None


class Answer(BaseModel):
    answer: str
    sources: list[dict]


class IndexStatus(BaseModel):
    total_documents: int
    indexed: bool


SYSTEM_PROMPT = """Jesteś Koziołkiem Antkiem – inteligentnym asystentem Urzędu Miasta Lublin. Pomagasz mieszkańcom załatwiać sprawy urzędowe na podstawie danych z BIP (Biuletyn Informacji Publicznej).

ZASADY:
1. Odpowiadaj WYŁĄCZNIE na podstawie podanego kontekstu. Nie wymyślaj informacji.
2. Jeśli w kontekście nie ma odpowiedzi, powiedz: "Nie znalazłem tej informacji w BIP."
3. Podawaj konkretne dane: adres, pokój, telefon, godziny, wymagane dokumenty, opłaty.
4. Rozróżniaj wydziały – "dowód osobisty" to Wydział Spraw Administracyjnych, "dowód rejestracyjny" to Wydział Komunikacji.
5. Podaj źródło (URL) na końcu odpowiedzi.
6. Odpowiadaj zwięźle, w punktach, po polsku.
7. Jeśli w kontekście jest kilka usług pasujących do pytania, wybierz najbardziej trafną na podstawie tytułu usługi."""


def get_llm_response(question: str, context: str) -> str:
    """Call local LLM with context for RAG response."""
    user_prompt = f"""Poniżej znajdują się fragmenty z Biuletynu Informacji Publicznej Lublin, które mogą pomóc odpowiedzieć na pytanie.

KONTEKST:
---
{context}
---

PYTANIE: {question}

INSTRUKCJE: Na podstawie powyższego kontekstu odpowiedz na pytanie. Wybierz TYLKO fragmenty, które bezpośrednio dotyczą pytania (zwróć uwagę na tytuł usługi). Podaj: adres, godziny, wymagane dokumenty, opłaty, kroki procedury, URL źródłowy."""

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    return response["choices"][0]["message"]["content"]


@app.get("/health")
def health():
    return {"status": "ok", "documents": collection.count()}


@app.get("/status", response_model=IndexStatus)
def status():
    return IndexStatus(
        total_documents=collection.count(),
        indexed=collection.count() > 0,
    )


@app.post("/index")
def index_documents():
    """Load documents.json and index into ChromaDB."""
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

    return {"indexed": len(unique_docs), "status": "ok"}


@app.post("/query", response_model=Answer)
def query(q: Query):
    """Answer a question using RAG."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    top_k = q.top_k or TOP_K

    results = collection.query(
        query_texts=[q.question],
        n_results=top_k,
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0] if "distances" in results else [0] * len(documents)

    # Simple re-ranking: boost chunks whose title closely matches the question
    question_lower = q.question.lower()
    scored = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        title = meta.get("title", "").lower()
        boost = 0
        # Strong boost if title keywords are in the question
        title_words = [w for w in title.split() if len(w) > 3]
        matching_words = sum(1 for w in title_words if w in question_lower)
        if title_words:
            boost = matching_words / len(title_words)
        scored.append((doc, meta, dist - boost * 0.5))

    scored.sort(key=lambda x: x[2])

    context_parts = []
    sources = []
    seen_urls = set()

    for doc, meta, _ in scored[:6]:
        context_parts.append(doc)
        url = meta.get("source_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                "url": url,
                "title": meta.get("title", ""),
                "type": meta.get("type", ""),
            })

    context = "\n\n---\n\n".join(context_parts)

    answer = get_llm_response(q.question, context)

    return Answer(answer=answer, sources=sources)


@app.post("/search")
def search(q: Query):
    """Search without LLM - just return relevant chunks."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    top_k = q.top_k or TOP_K

    results = collection.query(
        query_texts=[q.question],
        n_results=top_k,
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "content": doc,
            "metadata": meta,
            "score": 1 - dist,
        })

    return {"results": hits}


@app.get("/locations")
def get_locations():
    """Return office locations for the map."""
    locations_file = os.path.join(DATA_DIR, "locations.json")
    if os.path.exists(locations_file):
        with open(locations_file) as f:
            return json.load(f)
    return {"locations": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
