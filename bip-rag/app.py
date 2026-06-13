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
    os.path.join(os.path.dirname(__file__), "models", "Qwen2.5-3B-Instruct-Q4_K_M.gguf"),
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


PL_NORMALIZE = str.maketrans("óąęćśźżłń", "oaecszzln")


def tokenize_pl(text: str) -> list[str]:
    text = text.lower().translate(PL_NORMALIZE)
    text = re.sub(r"[^\w\s]", " ", text)
    return [t[:5] for t in text.split() if len(t) > 2]


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
    n_ctx=4096,
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
    "spokojna 2": {"lat": 51.24968, "lng": 22.55295},
    "wieniawska 14": {"lat": 51.24865, "lng": 22.55838},
    "czechowska 19": {"lat": 51.24780, "lng": 22.55120},
    "filaretów 44": {"lat": 51.22800, "lng": 22.54300},
    "kleeberga 12a": {"lat": 51.21950, "lng": 22.59500},
    "leszczyńskiego 20": {"lat": 51.24920, "lng": 22.54720},
    "okopowa 11": {"lat": 51.24850, "lng": 22.55650},
    "królewska 3": {"lat": 51.24620, "lng": 22.55730},
    "szkolna 36": {"lat": 51.24550, "lng": 22.55720},
    "peowiaków 13": {"lat": 51.24710, "lng": 22.55480},
    "zana 38": {"lat": 51.23650, "lng": 22.54950},
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
EXTRACTION_PROMPT = """Jesteś Koziołkiem Antkiem - asystentem Urzędu Miasta Lublin. Odpowiadaj JSON-em.

Format:
{"summary":"krótko o sprawie","where":{"address":"pełny adres z ulicą i nr","room":"pokój/piętro/stanowisko","phone":"numery tel","hours":"dokładne godziny dla każdego dnia","department":"wydział"},"how":{"steps":["konkretny krok 1","konkretny krok 2","konkretny krok 3"],"required_documents":["dokument1","dokument2"],"forms":["formularz"],"submission_method":"osobiście/online/ePUAP"},"how_much":{"cost":"kwota lub bezpłatne","time_estimate":"CZAS WYDANIA dokumentu (np. 30 dni), NIE czas wizyty","legal_basis":"pełna nazwa ustawy z Dz.U."},"who":null,"booking":true/false,"additional_info":"ważne uwagi, wyjątki"}

Zasady:
- TYLKO dane z kontekstu, null jeśli brak danych
- W "hours" podaj DOKŁADNE godziny z kontekstu (np. "pn 7:45-16:45, wt-pt 7:45-15:15")
- W "phone" podaj WSZYSTKIE numery telefonów z kontekstu
- W "address" podaj pełny adres z nazwą ulicy, numerem, stanowiskiem/piętrem
- W "steps" podaj 3-5 KONKRETNYCH kroków (nie ogólniki). Wyciągnij je z sekcji "Sposób i miejsce składania"
- W "required_documents" wymień WSZYSTKIE dokumenty z sekcji "Wymagane załączniki" i "Dokumenty do wglądu"
- W "time_estimate" podaj czas WYDANIA DOKUMENTU (z "Termin załatwienia sprawy"), NIE czas wizyty w urzędzie
- W "cost" podaj opłatę z sekcji "Wymagane opłaty"
- "who" = null (nie wypełniaj chyba że pytanie dotyczy konkretnej osoby)
- NIE wymyślaj URL-i ani danych których nie ma w kontekście
- booking=true gdy wizyta osobista wymagana
- W sources podaj URL-e zrodlowe z kontekstu jesli dostepne
- Kontekst moze zawierac DWA typy dokumentow:
  * type=usluga -> procedura LOKALNA w Urzedzie Miasta Lublin (adres, godziny, wydzial, oplaty lokalne)
  * type=wiedza_bazowa -> definicja/ustawa OGOLNOPOLSKA (NIE podawaj adresow Lublina z wiedzy bazowej)
- Gdy pytanie dotyczy definicji pojecia (co to jest X) -> odpowiadaj z wiedzy bazowej
- Gdy pytanie dotyczy procedury (jak wyrobic X) -> odpowiadaj z karty uslugi
- Podawaj legal_basis z metadanych legal_ref gdy dostepne
- Jesli informacji NIE MA w kontekscie -> null, NIE wymyslaj
- Odpowiedz WYLACZNIE JSON"""


def get_structured_response(question: str, context: str) -> dict:
    """Get structured JSON response from LLM."""
    user_prompt = f"""KONTEKST Z BIP LUBLIN:
---
{context}
---

PYTANIE MIESZKAŃCA: {question}

Odpowiedz TYLKO poprawnym JSON-em, bez tekstu przed/po."""

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.05,
        max_tokens=1200,
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


# --- Intent classification (rule-based, zero latency) ---
PROCEDURE_PATTERNS = [
    "jak wyrobić", "jak zrobić", "jak załatwić", "jak uzyskać", "jak złożyć",
    "jak zameldować", "jak wymeldować", "jak zarejestrować", "jak wymienić",
    "co potrzebuję", "jakie dokumenty", "co muszę", "procedura",
    "chcę wyrobić", "chcę załatwić", "chcę złożyć", "chcę uzyskać",
    "chcę zameldować", "chcę zarejestrować",
    "jak mogę", "gdzie mogę załatwić",
    "potrzebuję wyrobić", "muszę wyrobić", "muszę złożyć",
]

SIMPLE_PATTERNS = [
    "kto jest", "kto pełni", "kto to",
    "co to jest", "czym jest", "czym się zajmuje",
    "gdzie jest", "gdzie znajduje się", "jaki adres", "jaki telefon",
    "ile kosztuje", "ile trwa", "kiedy",
    "czy mogę", "czy jest",
    "jaki formularz", "jaki wniosek", "jaki druk",
    "godziny otwarcia", "godziny pracy",
]


def classify_intent(question: str) -> str:
    """Classify question as 'procedure' (full pipeline) or 'simple' (quick answer)."""
    q = question.lower().strip()

    for pattern in PROCEDURE_PATTERNS:
        if pattern in q:
            return "procedure"

    for pattern in SIMPLE_PATTERNS:
        if pattern in q:
            return "simple"

    # Default: if question is short (< 8 words), likely simple
    if len(q.split()) < 6:
        return "simple"

    return "procedure"


# --- Simple response (for info questions) ---
SIMPLE_PROMPT = """Jesteś Koziołkiem Antkiem - asystentem Urzędu Miasta Lublin. Odpowiedz krótko (2-4 zdania) na pytanie mieszkańca.

ZASADY:
- Użyj WYŁĄCZNIE informacji z podanego kontekstu
- NIE wymyślaj linków, adresów URL, numerów telefonów
- NIE podawaj informacji których nie ma w kontekście
- Jeśli kontekst nie zawiera odpowiedzi, powiedz: "Nie mam informacji na ten temat w bazie Urzędu Miasta Lublin."
- Odpowiadaj po polsku, konkretnie
- Dla definicji pojęć (type=wiedza_bazowa) podaj krótkie wyjaśnienie + źródło prawne jeśli jest
- NIE podawaj adresów Lublina gdy odpowiadasz z wiedzy ogólnopolskiej"""


def get_simple_response(question: str, context: str) -> str:
    """Quick text response for simple informational questions."""
    user_prompt = f"""Kontekst:\n{context}\n\nPytanie: {question}\n\nOdpowiedz krótko (2-4 zdania):"""

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SIMPLE_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=300,
    )
    return response["choices"][0]["message"]["content"]


# --- Hybrid retrieval ---
def hybrid_search(question: str, top_k: int = 30, final_k: int = 6) -> tuple[list[str], list[dict]]:
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

    # Token-based title re-ranking (prefix stemming for Polish)
    query_tokens_set = set(tokenize_pl(question))

    for did in list(rrf_scores.keys()):
        meta = id_to_meta.get(did, {})
        title = meta.get("title", "")
        title_tokens = set(tokenize_pl(title))
        if title_tokens:
            overlap = query_tokens_set & title_tokens
            rrf_scores[did] += (len(overlap) / max(len(query_tokens_set), 1)) * 0.08

        doc = id_to_doc.get(did, "")
        header = doc[:300]
        if "Szukaj też:" in header:
            synonym_line = header[header.index("Szukaj też:"):].split("\n")[0]
            syn_tokens = set(tokenize_pl(synonym_line))
            syn_overlap = query_tokens_set & syn_tokens
            rrf_scores[did] += (len(syn_overlap) / max(len(query_tokens_set), 1)) * 0.08

    # Knowledge base boost for definition queries
    question_lower = question.lower()
    DEFINITION_PATTERNS = [
        "co to jest", "czym jest", "co oznacza", "co to znaczy",
        "czym sie rozni", "jaka jest roznica", "definicja",
        "co to", "czym to", "na czym polega",
    ]
    is_definition_query = any(p in question_lower for p in DEFINITION_PATTERNS)
    if is_definition_query:
        for did in list(rrf_scores.keys()):
            meta = id_to_meta.get(did, {})
            if meta.get("type") == "wiedza_bazowa":
                rrf_scores[did] += 0.08
            elif meta.get("type") == "usluga":
                rrf_scores[did] -= 0.03

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


# --- Suggestion generation (no LLM, rule-based for speed) ---
def generate_suggestions(question: str, structured: dict, metadatas: list[dict]) -> list[str]:
    """Generate Perplexity-style follow-up questions based on response. Includes topic context."""
    suggestions = []
    question_lower = question.lower()

    # Extract topic from question for context-aware follow-ups
    topic = ""
    for meta in metadatas[:1]:
        topic = meta.get("title", "")
    if not topic:
        topic = question

    where = structured.get("where")
    how = structured.get("how")
    how_much = structured.get("how_much")
    department = ""
    if where and isinstance(where, dict):
        department = where.get("department", "")

    # Context-aware suggestions (include topic!)
    if how and isinstance(how, dict):
        docs = how.get("required_documents", [])
        forms = how.get("forms", [])
        if forms:
            suggestions.append(f"Skąd pobrać formularz do: {topic}?")
        elif docs:
            suggestions.append(f"Jakie dokładnie dokumenty są potrzebne do: {topic}?")
        if how.get("submission_method") and "online" in (how.get("submission_method") or ""):
            suggestions.append(f"Jak złożyć wniosek o {topic} przez internet?")

    if where and isinstance(where, dict) and where.get("address"):
        addr = where.get("address", "")
        suggestions.append(f"Jak dojechać do {addr}?")

    if how_much and isinstance(how_much, dict):
        if how_much.get("cost") and "bezpłat" not in (how_much.get("cost") or "").lower():
            suggestions.append("Gdzie zapłacić opłatę skarbową?")
        if how_much.get("time_estimate"):
            suggestions.append(f"Czy mogę przyspieszyć {topic}?")

    if structured.get("booking"):
        suggestions.append("Jak zarezerwować wizytę w urzędzie online?")

    # Department-specific related topics
    if department and "spraw administracyjnych" in department.lower():
        if "dowód" in question_lower and "meldunek" not in question_lower:
            suggestions.append("Jak zameldować się w Lublinie?")
    elif department and "komunikacji" in department.lower():
        if "rejestrac" in question_lower:
            suggestions.append("Ile kosztuje przerejestrowanie samochodu?")

    return suggestions[:4]


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

    # Clear existing data by getting fresh collection
    try:
        chroma_client.delete_collection("bip_lublin")
    except Exception:
        pass
    collection = chroma_client.create_collection(
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
        collection.upsert(
            ids=[d["id"] for d in batch],
            documents=[d["content"] for d in batch],
            metadatas=[d["metadata"] for d in batch],
        )

    build_bm25()
    return {"indexed": len(unique_docs), "bm25_docs": len(bm25_corpus), "status": "ok"}


@app.post("/query")
def query(q: Query):
    """Structured RAG query - detects intent and adapts response format."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    top_k = q.top_k or TOP_K
    intent = classify_intent(q.question)
    documents, metadatas = hybrid_search(q.question, top_k=top_k, final_k=FINAL_K)

    context_parts = []
    for doc, meta in zip(documents, metadatas):
        doc_type = meta.get("type", "unknown")
        scope = meta.get("scope", "")
        legal_ref = meta.get("legal_ref", "")
        header = f"[{doc_type}"
        if scope:
            header += f", zasieg: {scope}"
        if legal_ref:
            header += f", {legal_ref}"
        header += "]"
        context_parts.append(f"{header}\n{doc}")
    context = "\n\n---\n\n".join(context_parts)

    if intent == "simple":
        # Quick text answer - no full structured pipeline
        answer = get_simple_response(q.question, context)
        sources = []
        seen_urls = set()
        for meta in metadatas:
            url = meta.get("source_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append({"url": url, "title": meta.get("title", ""), "department": meta.get("department", "")})
        suggestions = generate_suggestions(q.question, {}, metadatas)
        return {
            "intent": "simple",
            "summary": answer,
            "sources": sources[:2],
            "suggestions": suggestions,
        }

    # Full structured response for procedural questions
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

    # Build sources - filter to only relevant ones
    sources = []
    seen_urls = set()
    question_words = set(w for w in q.question.lower().split() if len(w) > 3)
    for meta in metadatas:
        url = meta.get("source_url", "")
        title = meta.get("title", "").lower()
        if not url or url in seen_urls:
            continue
        # Only include sources with title overlap to the question
        has_overlap = any(w in title for w in question_words)
        if has_overlap or len(sources) == 0:
            seen_urls.add(url)
            sources.append({
                "url": url,
                "title": meta.get("title", ""),
                "department": meta.get("department", ""),
            })

    # Generate follow-up suggestions based on response context
    suggestions = generate_suggestions(q.question, structured, metadatas)

    return {
        **structured,
        "sources": sources,
        "suggestions": suggestions,
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
