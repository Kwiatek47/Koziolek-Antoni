#!/usr/bin/env python3
"""
BIP Lublin RAG - Retrieval Augmented Generation for Lublin city services.
Simple API server with ChromaDB for vector search and OpenAI-compatible LLM.
"""
import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

app = FastAPI(
    title="BIP Lublin RAG",
    description="System pytań i odpowiedzi oparty na danych BIP Urząd Miasta Lublin",
    version="1.0.0",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.json")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sdadas/st-polish-paraphrase-from-distilroberta")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")

TOP_K = int(os.getenv("TOP_K", "8"))

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


class Query(BaseModel):
    question: str
    top_k: Optional[int] = None


class Answer(BaseModel):
    answer: str
    sources: list[dict]


class IndexStatus(BaseModel):
    total_documents: int
    indexed: bool


def get_llm_response(question: str, context: str) -> str:
    """Call LLM with context for RAG response."""
    from openai import OpenAI

    client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

    system_prompt = """Jesteś pomocnym asystentem Urzędu Miasta Lublin. Odpowiadasz na pytania mieszkańców na podstawie danych z BIP (Biuletyn Informacji Publicznej).

Zasady:
- Odpowiadaj TYLKO na podstawie podanego kontekstu
- Jeśli nie masz informacji w kontekście, powiedz to wprost
- Podawaj źródła (URL) przy odpowiedziach
- Odpowiadaj po polsku
- Bądź konkretny: podawaj numery telefonów, adresy, godziny, wymagane dokumenty
- Jeśli pytanie dotyczy procedury/usługi, wymień kroki do załatwienia sprawy"""

    user_prompt = f"""Kontekst z BIP Lublin:
---
{context}
---

Pytanie: {question}

Odpowiedz na podstawie powyższego kontekstu. Podaj źródła."""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    return response.choices[0].message.content


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
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        collection.add(
            ids=[d["id"] for d in batch],
            documents=[d["content"] for d in batch],
            metadatas=[d["metadata"] for d in batch],
        )

    return {"indexed": len(docs), "status": "ok"}


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
