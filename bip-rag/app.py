#!/usr/bin/env python3
"""
BIP Lublin RAG v2 - Structured Intelligent Pipeline
Hybrid Retrieval (Dense + BM25 + RRF) with structured response extraction.
"""
import json
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
    title="Koziołek Antek - Structured RAG Pipeline",
    description="Hybrydowy system RAG z ustrukturyzowanymi odpowiedziami",
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
RRF_K = 60

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

# --- BM25 ---
bm25_corpus: list[str] = []
bm25_ids: list[str] = []
bm25_metadatas: list[dict] = []
bm25_index: Optional[BM25Okapi] = None


def tokenize_pl(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def build_bm25():
    global bm25_index, bm25_corpus, bm25_ids, bm25_metadatas
    if not os.path.exists(DOCUMENTS_FILE):
        return
    with open(DOCUMENTS_FILE) as f:
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


class WhereInfo(BaseModel):
    address: Optional[str] = None
    room: Optional[str] = None
    phone: Optional[str] = None
    hours: Optional[str] = None
    department: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class HowInfo(BaseModel):
    steps: list[str] = []
    required_documents: list[str] = []
    forms: list[str] = []
    submission_method: Optional[str] = None


class HowMuchInfo(BaseModel):
    cost: Optional[str] = None
    time_estimate: Optional[str] = None
    legal_basis: Optional[str] = None


class WhoInfo(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    gender: Optional[str] = None


class StructuredAnswer(BaseModel):
    summary: str
    where: Optional[WhereInfo] = None
    how: Optional[HowInfo] = None
    how_much: Optional[HowMuchInfo] = None
    who: Optional[WhoInfo] = None
    booking: Optional[bool] = None
    additional_info: Optional[str] = None
    sources: list[dict] = []
    raw_answer: Optional[str] = None


class IndexStatus(BaseModel):
    total_documents: int
    indexed: bool


# --- Geocoding lookup ---
KNOWN_LOCATIONS = {
    "spokojna 2": {"lat": 51.2480, "lng": 22.5590},
    "wieniawska 14": {"lat": 51.2503, "lng": 22.5615},
    "czechowska 19": {"lat": 51.2465, "lng": 22.5540},
    "filaretów 44": {"lat": 51.2280, "lng": 22.5430},
    "kleeberga 12a": {"lat": 51.2195, "lng": 22.5950},
    "leszczyńskiego 20": {"lat": 51.2525, "lng": 22.5445},
    "okopowa 11": {"lat": 51.2490, "lng": 22.5555},
    "królewska 3": {"lat": 51.2475, "lng": 22.5650},
    "szkolna 36": {"lat": 51.2455, "lng": 22.5572},
}


def find_coordinates(address: str) -> tuple[Optional[float], Optional[float]]:
    if not address:
        return None, None
    addr_lower = address.lower()
    for key, coords in KNOWN_LOCATIONS.items():
        if key in addr_lower:
            return coords["lat"], coords["lng"]
    return None, None


# --- Structured extraction prompt ---
EXTRACTION_PROMPT = """Jesteś Koziołkiem Antkiem – inteligentnym asystentem Urzędu Miasta Lublin.

Na podstawie KONTEKSTU odpowiedz na pytanie mieszkańca w formacie JSON. Wypełnij TYLKO pola, dla których masz dane w kontekście.

Format odpowiedzi (JSON):
{{
  "summary": "Krótkie podsumowanie sprawy (1-2 zdania, prostym językiem)",
  "where": {{
    "address": "Pełny adres (ulica, numer, kod, miasto)",
    "room": "Numer pokoju/piętro",
    "phone": "Numery telefonów",
    "hours": "Godziny przyjęć (pełne, np. 'pn 9:15-16:30, wt-pt 7:45-14:30')",
    "department": "Nazwa wydziału/komórki organizacyjnej"
  }},
  "how": {{
    "steps": ["Krok 1: ...", "Krok 2: ...", "Krok 3: ..."],
    "required_documents": ["Dokument 1", "Dokument 2"],
    "forms": ["Nazwa formularza/wniosku do wypełnienia"],
    "submission_method": "Sposób złożenia (osobiście/online/pocztą)"
  }},
  "how_much": {{
    "cost": "Koszt procedury (np. '85 zł' lub 'bezpłatne')",
    "time_estimate": "Czas załatwienia sprawy",
    "legal_basis": "Podstawa prawna (ustawa, rozporządzenie)"
  }},
  "who": {{
    "name": "Imię i nazwisko osoby odpowiedzialnej (jeśli podane)",
    "role": "Stanowisko/funkcja",
    "department": "Wydział",
    "gender": "M lub F (jeśli można wywnioskować z imienia)"
  }},
  "booking": true lub false,
  "additional_info": "Dodatkowe ważne informacje, uwagi, wyjątki"
}}

WAŻNE:
- Użyj TYLKO danych z kontekstu. NIE wymyślaj.
- Jeśli nie masz danych na dane pole → ustaw null.
- Rozróżniaj: "dowód osobisty" → Wydział Spraw Administracyjnych, "dowód rejestracyjny" → Wydział Komunikacji.
- Wybierz usługę NAJBARDZIEJ pasującą do pytania (patrz na tytuł usługi w kontekście).
- Pole "booking": ustaw na true jeśli sprawa wymaga osobistej wizyty w urzędzie (złożenie dokumentów, odbiór, podpis). Ustaw false jeśli można załatwić online/pocztą lub jeśli to pytanie informacyjne.
- Odpowiedz WYŁĄCZNIE poprawnym JSON-em, bez dodatkowego tekstu."""


def get_structured_response(question: str, context: str) -> dict:
    """Get structured JSON response from LLM."""
    user_prompt = f"""KONTEKST Z BIP LUBLIN:
---
{context}
---

PYTANIE MIESZKAŃCA: {question}

Odpowiedz w formacie JSON zgodnym ze specyfikacją powyżej."""

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.05,
        max_tokens=2500,
        response_format={"type": "json_object"},
    )

    raw_text = response["choices"][0]["message"]["content"]

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"summary": raw_text, "raw_fallback": True}


# --- Hybrid retrieval ---
def hybrid_search(question: str, top_k: int = 15, final_k: int = 6) -> tuple[list[str], list[dict]]:
    """Hybrid retrieval: dense + BM25 + RRF fusion."""
    dense_results = collection.query(query_texts=[question], n_results=top_k)
    dense_ids = dense_results["ids"][0]
    dense_docs = dense_results["documents"][0]
    dense_metas = dense_results["metadatas"][0]

    id_to_doc = {}
    id_to_meta = {}
    for i, did in enumerate(dense_ids):
        id_to_doc[did] = dense_docs[i]
        id_to_meta[did] = dense_metas[i]

    bm25_results_ids = []
    if bm25_index is not None:
        query_tokens = tokenize_pl(question)
        bm25_scores = bm25_index.get_scores(query_tokens)
        top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k]
        for idx in top_indices:
            if bm25_scores[idx] > 0:
                bid = bm25_ids[idx]
                bm25_results_ids.append(bid)
                if bid not in id_to_doc:
                    id_to_doc[bid] = bm25_corpus[idx]
                    id_to_meta[bid] = bm25_metadatas[idx]

    # RRF
    rrf_scores: dict[str, float] = {}
    for rank, did in enumerate(dense_ids):
        rrf_scores[did] = rrf_scores.get(did, 0) + 1.0 / (RRF_K + rank + 1)
    for rank, bid in enumerate(bm25_results_ids):
        rrf_scores[bid] = rrf_scores.get(bid, 0) + 1.0 / (RRF_K + rank + 1)

    # Title boost
    question_lower = question.lower()
    for did in rrf_scores:
        meta = id_to_meta.get(did, {})
        title = meta.get("title", "").lower()
        title_words = [w for w in title.split() if len(w) > 3]
        if title_words:
            matching = sum(1 for w in title_words if w in question_lower)
            rrf_scores[did] += (matching / len(title_words)) * 0.02

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    final_docs = []
    final_metas = []
    seen = set()

    for did in sorted_ids:
        if len(final_docs) >= final_k:
            break
        doc = id_to_doc.get(did, "")
        h = hash(doc[:200])
        if h in seen:
            continue
        seen.add(h)
        final_docs.append(doc)
        final_metas.append(id_to_meta.get(did, {}))

    return final_docs, final_metas


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
    return IndexStatus(total_documents=collection.count(), indexed=collection.count() > 0)


@app.post("/index")
def index_documents():
    """Load and index documents into ChromaDB + BM25."""
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

    build_bm25()
    return {"indexed": len(unique_docs), "bm25_docs": len(bm25_corpus), "status": "ok"}


@app.post("/query")
def query(q: Query):
    """Structured RAG query - returns WHERE/HOW/HOW_MUCH/WHO sections."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    top_k = q.top_k or TOP_K
    documents, metadatas = hybrid_search(q.question, top_k=top_k, final_k=FINAL_K)

    context = "\n\n---\n\n".join(documents)
    structured = get_structured_response(q.question, context)

    # Enrich with coordinates
    where = structured.get("where")
    if where and isinstance(where, dict):
        address = where.get("address", "")
        lat, lng = find_coordinates(address)
        if lat:
            where["lat"] = lat
            where["lng"] = lng

    # Determine gender for "who" avatar
    who = structured.get("who")
    if who and isinstance(who, dict) and not who.get("gender"):
        name = who.get("name", "")
        if name:
            if name.split()[0][-1] == "a":
                who["gender"] = "F"
            else:
                who["gender"] = "M"

    # Infer booking if LLM didn't set it - show booking when in-person visit required
    if structured.get("booking") is None:
        how = structured.get("how")
        submission = ""
        if how and isinstance(how, dict):
            submission = (how.get("submission_method") or "").lower()
        where_present = where and isinstance(where, dict) and where.get("address")
        if where_present and ("osobiście" in submission or "osobist" in submission or not submission):
            structured["booking"] = True
        else:
            structured["booking"] = False

    # Build sources
    sources = []
    seen_urls = set()
    for meta in metadatas:
        url = meta.get("source_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                "url": url,
                "title": meta.get("title", ""),
                "department": meta.get("department", ""),
            })

    return {
        **structured,
        "sources": sources,
    }


@app.post("/search")
def search(q: Query):
    """Search without LLM - return relevant chunks."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty.")
    top_k = q.top_k or TOP_K
    documents, metadatas = hybrid_search(q.question, top_k=top_k, final_k=top_k)
    return {"results": [{"content": d[:500], "metadata": m} for d, m in zip(documents, metadatas)]}


@app.get("/locations")
def get_locations():
    locations_file = os.path.join(DATA_DIR, "locations.json")
    if os.path.exists(locations_file):
        with open(locations_file) as f:
            return json.load(f)
    return {"locations": []}


@app.on_event("startup")
def startup_event():
    if os.path.exists(DOCUMENTS_FILE):
        build_bm25()
        print(f"BM25 index built: {len(bm25_corpus)} documents")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
