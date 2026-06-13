#!/usr/bin/env python3
"""
BIP Lublin RAG v2 - Structured Intelligent Pipeline
Hybrid Retrieval (Dense + BM25 + RRF) with structured response extraction.
"""
import json
import os
import re
import time
import hashlib
from collections import OrderedDict
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

# --- Response Cache (in-memory LRU, top 50 questions → 0s response) ---
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "50"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", str(24 * 3600)))  # 24h default


class ResponseCache:
    """LRU cache with TTL for query responses. Normalizes questions for fuzzy matching."""

    def __init__(self, max_size: int = 50, ttl: int = 86400):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _normalize(question: str) -> str:
        q = question.lower().strip()
        q = re.sub(r"[^\w\s]", "", q)
        q = re.sub(r"\s+", " ", q)
        return q

    def _key(self, question: str) -> str:
        normalized = self._normalize(question)
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, question: str) -> Optional[dict]:
        key = self._key(question)
        if key in self._cache:
            ts, response = self._cache[key]
            if time.time() - ts < self.ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return response
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def put(self, question: str, response: dict):
        key = self._key(question)
        self._cache[key] = (time.time(), response)
        self._cache.move_to_end(key)
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def invalidate(self):
        self._cache.clear()

    @property
    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / max(self._hits + self._misses, 1)) * 100:.1f}%",
        }


response_cache = ResponseCache(max_size=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)

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
EXTRACTION_PROMPT = """Jesteś Koziołkiem Antkiem - asystentem Urzędu Miasta Lublin. Odpowiadaj WYŁĄCZNIE JSON-em.

Format odpowiedzi (wypełnij TYLKO pola dla których masz dane w kontekście, resztę ustaw na null):
{
  "summary": "1-2 zdania co to za sprawa",
  "where": {
    "address": "ul. [nazwa] [numer], Lublin",
    "room": "pokój/piętro/stanowisko lub null",
    "phone": "numer(y) telefonu z kontekstu lub null",
    "hours": "godziny z kontekstu lub null",
    "department": "nazwa wydziału z kontekstu"
  },
  "how": {
    "steps": ["krok wyciągnięty z kontekstu"],
    "required_documents": ["dokument z kontekstu"],
    "forms": ["nazwa formularza z kontekstu"],
    "submission_method": "osobiście/online/ePUAP"
  },
  "how_much": {
    "cost": "kwota z kontekstu lub bezpłatne",
    "time_estimate": "czas z kontekstu",
    "legal_basis": "ustawa z kontekstu w formacie: Ustawa z dnia... (Dz.U. ...)"
  },
  "who": null,
  "booking": true,
  "additional_info": "uwagi z kontekstu lub null"
}

KRYTYCZNE ZASADY:
1. KOPIUJ dosłownie z kontekstu - NIE parafrazuj, NIE tłumacz, NIE wymyślaj
2. Adres MUSI zawierać "ul." lub "al." + nazwę ulicy + numer. Jeśli nie ma adresu w kontekście -> null
3. Telefon MUSI zaczynać się od "81" lub "+48 81" (to Lublin). Jeśli nie ma telefonu -> null
4. Godziny MUSZĄ być w formacie "pn-pt" lub "pn", "wt" itp. z cyframi godzin. Nie ma -> null
5. required_documents: wymień KONKRETNE nazwy dokumentów z sekcji "Wymagane załączniki"/"Dokumenty do wglądu". Pusta lista [] jeśli brak
6. forms: wymień KONKRETNE nazwy formularzy/wniosków z kontekstu. Pusta lista [] jeśli brak
7. steps: wyciągnij z sekcji "Sposób i miejsce składania dokumentów". Pusta lista [] jeśli brak
8. legal_basis: MUSI być po polsku w formacie "Ustawa z dnia... (Dz.U. rok poz. X)". Nie ma -> null
9. NIGDY nie wymyślaj danych - lepiej null niż fałsz
10. Odpowiedz WYŁĄCZNIE poprawnym JSON-em, zero tekstu przed/po"""


def get_structured_response(question: str, context: str) -> dict:
    """Get structured JSON response from LLM."""
    user_prompt = f"""KONTEKST Z BIP LUBLIN:
---
{context}
---

PYTANIE MIESZKAŃCA: {question}

INSTRUKCJA: Wyciągnij dane z kontekstu powyżej. Pole "address" to ADRES FIZYCZNY (np. "ul. Spokojna 2, Lublin"), NIE sposób złożenia. Pole "submission_method" to sposób złożenia (osobiście/online). NIE mieszaj tych pól.

Odpowiedz TYLKO poprawnym JSON-em:"""

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
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                return {"summary": raw_text, "raw_fallback": True}
        else:
            return {"summary": raw_text, "raw_fallback": True}

    return sanitize_response(data)


def sanitize_response(data: dict) -> dict:
    """Post-process LLM output to remove hallucinated/invalid data."""

    # Validate WHERE
    where = data.get("where")
    if where and isinstance(where, dict):
        # Address must contain a street name pattern (ul./al./pl.) or known Lublin street
        addr = where.get("address") or ""
        if addr and not re.search(r"(ul\.|al\.|pl\.|Spokojna|Wieniawska|Czechowska|Filaretów|Kleeberga|Okopowa|Leszczyńskiego|Królewska|Szkolna|Peowiaków|Zana)", addr):
            where["address"] = None

        # Phone must be Lublin area (81) or null
        phone = where.get("phone") or ""
        if phone and not re.search(r"(81[\s\-]?\d|48[\s\-]?81|\+48[\s\-]?81)", phone):
            where["phone"] = None

        # Hours must have time digits (HH:MM pattern)
        hours = where.get("hours") or ""
        if hours and not re.search(r"\d{1,2}[:.]\d{2}", hours):
            where["hours"] = None

        # If where has no real data left, null it
        real_values = [v for k, v in where.items() if v and v != "null" and k != "department"]
        if not real_values and not where.get("department"):
            data["where"] = None

    # Validate HOW
    how = data.get("how")
    if how and isinstance(how, dict):
        # Remove placeholder documents
        PLACEHOLDER_PATTERNS = {"dokument1", "dokument2", "dokument 1", "dokument 2",
                                "formularz1", "formularz 1", "wniosek1", "formularz",
                                "wniosek", "dokument"}
        docs = how.get("required_documents") or []
        how["required_documents"] = [d for d in docs if d.lower().strip() not in PLACEHOLDER_PATTERNS and len(d) > 5]

        forms = how.get("forms") or []
        how["forms"] = [f for f in forms if f.lower().strip() not in PLACEHOLDER_PATTERNS and len(f) > 5]

        # Remove generic/vague steps (too short = likely hallucinated)
        steps = how.get("steps") or []
        how["steps"] = [s for s in steps if len(s) > 15]

    # Validate HOW_MUCH
    how_much = data.get("how_much")
    if how_much and isinstance(how_much, dict):
        # Legal basis must not contain CJK characters
        legal = how_much.get("legal_basis") or ""
        if legal and re.search(r"[\u4e00-\u9fff\u3000-\u303f\u3040-\u309f\u30a0-\u30ff]", legal):
            how_much["legal_basis"] = None
        # Legal basis should reference Polish law format
        elif legal and not re.search(r"(Dz\.?\s?U|ustaw|rozporządzeni|uchwał)", legal, re.IGNORECASE):
            how_much["legal_basis"] = None

    # Strip CJK from summary if present
    summary = data.get("summary") or ""
    if re.search(r"[\u4e00-\u9fff\u3000-\u303f]", summary):
        data["summary"] = re.sub(r"[\u4e00-\u9fff\u3000-\u303f\u3040-\u309f\u30a0-\u30ff]+", "", summary).strip()

    return data


# --- Intent classification (rule-based, zero latency) ---
FILL_DOCUMENT_PATTERNS = [
    "jak wypełnić", "jak wypelnic", "jak uzupełnić", "jak uzupelnic",
    "jak wpisać", "jak wpisac", "co wpisać", "co wpisac",
    "jak napisać wniosek", "jak napisac wniosek",
    "jak wypełnić formularz", "jak wypełnić wniosek", "jak wypełnić druk",
    "jak wypełnić podanie", "jak wypełnić zgłoszenie", "jak wypełnić deklarację",
    "co wpisać w rubryce", "co wpisać w polu", "co wpisać w formularzu",
    "pomóż wypełnić", "pomoz wypelnic", "pomoc z wypełnieniem",
    "instrukcja wypełniania", "instrukcja wypelniania",
    "wzór wypełnienia", "wzor wypelnienia", "przykład wypełnienia",
    "jakie dane wpisać", "jakie dane podać w formularzu",
    "jak prawidłowo wypełnić", "jak poprawnie wypełnić",
    "co wpisać w wniosku", "co w rubryce", "które pola wypełnić",
    "fill out", "how to fill", "how do i fill",
    "як заповнити", "як заповніті",
]

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
    """Classify question as 'fill_document', 'procedure', or 'simple'."""
    q = question.lower().strip()

    for pattern in FILL_DOCUMENT_PATTERNS:
        if pattern in q:
            return "fill_document"

    for pattern in PROCEDURE_PATTERNS:
        if pattern in q:
            return "procedure"

    for pattern in SIMPLE_PATTERNS:
        if pattern in q:
            return "simple"

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


# --- Fill document response (step-by-step form guidance) ---
FILL_DOCUMENT_PROMPT = """Jesteś Koziołkiem Antkiem - asystentem Urzędu Miasta Lublin. Pomagasz wypełniać formularze i wnioski urzędowe.

Odpowiedz JSON-em w formacie:
{"summary":"krótki opis dokumentu i jego przeznaczenia","document_name":"pełna nazwa formularza/wniosku","fields":[{"name":"nazwa pola","description":"co dokładnie wpisać","example":"przykładowa wartość","tips":"dodatkowe wskazówki/uwagi"}],"general_tips":["ogólna wskazówka 1","ogólna wskazówka 2"],"common_mistakes":["częsty błąd 1","częsty błąd 2"],"where_to_get":"skąd pobrać formularz (link/miejsce)","where_to_submit":"gdzie i jak złożyć wypełniony dokument"}

Zasady:
- Podaj KAŻDE pole formularza osobno z opisem co wpisać
- W "example" podaj REALISTYCZNY przykład (np. "Jan Kowalski", "ul. Lipowa 5/3, 20-001 Lublin")
- W "tips" podaj typowe pułapki i wskazówki (np. "wpisz DRUKOWANYMI LITERAMI", "data w formacie DD.MM.RRRR")
- W "common_mistakes" opisz najczęstsze błędy przy wypełnianiu tego dokumentu
- Jeśli formularz ma warianty/sekcje opcjonalne, wyjaśnij kiedy je wypełnić
- Bazuj WYŁĄCZNIE na kontekście - nie wymyślaj pól których nie znasz
- Jeśli kontekst nie opisuje pól formularza szczegółowo, podaj ogólne wskazówki wypełniania na podstawie typu dokumentu
- Odpowiedz WYŁĄCZNIE JSON"""


def get_fill_document_response(question: str, context: str) -> dict:
    """Get structured form-filling guidance from LLM."""
    user_prompt = f"""KONTEKST Z BIP LUBLIN (formularze i procedury):
---
{context}
---

PYTANIE MIESZKAŃCA: {question}

Odpowiedz TYLKO poprawnym JSON-em z instrukcją wypełniania formularza."""

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": FILL_DOCUMENT_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1500,
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
        "cache": response_cache.stats,
    }


@app.get("/cache")
def cache_stats():
    """Cache statistics and management."""
    return response_cache.stats


@app.delete("/cache")
def cache_clear():
    """Clear the response cache."""
    response_cache.invalidate()
    return {"status": "cleared"}


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
    response_cache.invalidate()
    return {"indexed": len(unique_docs), "bm25_docs": len(bm25_corpus), "status": "ok"}


@app.post("/query")
def query(q: Query):
    """Structured RAG query - detects intent and adapts response format."""
    if collection.count() == 0:
        raise HTTPException(400, "Index is empty. Call POST /index first.")

    # Check cache first (0s response for repeated questions)
    cached = response_cache.get(q.question)
    if cached is not None:
        return {**cached, "cached": True}

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
        result = {
            "intent": "simple",
            "summary": answer,
            "sources": sources[:2],
            "suggestions": suggestions,
        }
        response_cache.put(q.question, result)
        return result

    if intent == "fill_document":
        # Form-filling guidance pipeline
        fill_data = get_fill_document_response(q.question, context)
        sources = []
        seen_urls = set()
        for meta in metadatas:
            url = meta.get("source_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append({"url": url, "title": meta.get("title", ""), "department": meta.get("department", "")})
        suggestions = [
            f"Gdzie złożyć {fill_data.get('document_name', 'ten wniosek')}?",
            f"Jakie dokumenty dołączyć do {fill_data.get('document_name', 'wniosku')}?",
            f"Ile kosztuje złożenie {fill_data.get('document_name', 'wniosku')}?",
        ]
        result = {
            "intent": "fill_document",
            "summary": fill_data.get("summary", ""),
            "document_name": fill_data.get("document_name", ""),
            "fields": fill_data.get("fields", []),
            "general_tips": fill_data.get("general_tips", []),
            "common_mistakes": fill_data.get("common_mistakes", []),
            "where_to_get": fill_data.get("where_to_get"),
            "where_to_submit": fill_data.get("where_to_submit"),
            "sources": sources[:3],
            "suggestions": suggestions,
        }
        response_cache.put(q.question, result)
        return result

    # Full structured response for procedural questions
    structured = get_structured_response(q.question, context)

    # Fallback: extract address from context if LLM missed it
    where = structured.get("where")
    if not where or not isinstance(where, dict):
        structured["where"] = {}
        where = structured["where"]

    if not where.get("address"):
        # Try to find address in context chunks
        for doc in documents[:3]:
            addr_match = re.search(r"(?:ul\.|al\.|pl\.)\s*[\w\s]+\d+[\w]?(?:\s*,\s*\d{2}-\d{3})?\s*Lublin", doc)
            if addr_match:
                where["address"] = addr_match.group().strip()
                break

    if not where.get("department"):
        # Extract department from first metadata
        for meta in metadatas[:2]:
            dept = meta.get("department", "")
            if dept:
                where["department"] = dept
                break

    # Enrich with coordinates
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

    result = {
        **structured,
        "sources": sources,
        "suggestions": suggestions,
    }
    response_cache.put(q.question, result)
    return result


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
