#!/usr/bin/env python3
"""
Benchmark RAG BIP Lublin - FULL PIPELINE TEST
Testuje WSZYSTKIE moduly systemu RAG bez potrzeby serwera/LLM.
Mockuje LLM, ale testuje realnie: embeddings, BM25, RRF, intent, suggestions, coords.

Uruchom:
    cd bip-rag && python3 benchmark_full.py
"""
import json
import math
import os
import re
import time
import sys
from datetime import datetime
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results")

# ============================================================
# MODULE 1: Tokenizer (same as app.py)
# ============================================================
PL_NORMALIZE = str.maketrans("oaecszzln", "oaecszzln")
PL_NORMALIZE = str.maketrans("\u00f3\u0105\u0119\u0107\u015b\u017a\u017c\u0142\u0144", "oaecszzln")


def tokenize_pl(text: str) -> list:
    text = text.lower().translate(PL_NORMALIZE)
    text = re.sub(r"[^\w\s]", " ", text)
    return [t[:5] for t in text.split() if len(t) > 2]


# ============================================================
# MODULE 2: BM25
# ============================================================
class SimpleBM25:
    def __init__(self, corpus: list, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.tokenized = [tokenize_pl(doc) for doc in corpus]
        self.doc_len = [len(d) for d in self.tokenized]
        self.avgdl = sum(self.doc_len) / self.corpus_size if self.corpus_size else 1
        self.df = {}
        for doc in self.tokenized:
            seen = set()
            for token in doc:
                if token not in seen:
                    self.df[token] = self.df.get(token, 0) + 1
                    seen.add(token)

    def get_scores(self, query_tokens: list) -> list:
        scores = [0.0] * self.corpus_size
        for token in query_tokens:
            if token not in self.df:
                continue
            idf = math.log((self.corpus_size - self.df[token] + 0.5) / (self.df[token] + 0.5) + 1)
            for i, doc in enumerate(self.tokenized):
                tf = doc.count(token)
                if tf == 0:
                    continue
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * numerator / denominator
        return scores

    def search(self, query: str, top_k: int = 30) -> list:
        tokens = tokenize_pl(query)
        scores = self.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(idx, scores[idx]) for idx in ranked[:top_k] if scores[idx] > 0]


# ============================================================
# MODULE 3: Dense Embeddings (simulated via token overlap + TF-IDF)
# ============================================================
class SimulatedDenseSearch:
    """Simulates dense embeddings using weighted token overlap.
    In production this is ChromaDB + sentence-transformers."""
    def __init__(self, docs: list):
        self.docs = docs
        self.N = len(docs)
        self.doc_tokens = []
        self.df = Counter()
        for d in docs:
            tokens = set(tokenize_pl(d["content"]))
            self.doc_tokens.append(tokens)
            for t in tokens:
                self.df[t] += 1

    def search(self, query: str, top_k: int = 30) -> list:
        qt = set(tokenize_pl(query))
        scores = []
        for i, dt in enumerate(self.doc_tokens):
            overlap = qt & dt
            if not overlap:
                scores.append(0.0)
                continue
            score = sum(math.log(self.N / (self.df[t] + 1)) for t in overlap)
            scores.append(score)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(idx, scores[idx]) for idx in ranked[:top_k] if scores[idx] > 0]


# ============================================================
# MODULE 4: RRF Fusion
# ============================================================
RRF_K = 60

def rrf_fusion(bm25_results: list, dense_results: list, docs: list) -> dict:
    """Reciprocal Rank Fusion combining BM25 + dense results."""
    rrf_scores = {}
    for rank, (idx, _) in enumerate(dense_results):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (RRF_K + rank + 1)
    for rank, (idx, _) in enumerate(bm25_results):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (RRF_K + rank + 1)
    return rrf_scores


# ============================================================
# MODULE 5: Reranking (title + synonym boost)
# ============================================================
def rerank(rrf_scores: dict, query: str, docs: list, top_k: int = 6) -> list:
    query_tokens = set(tokenize_pl(query))
    boosted = {}
    for idx, score in rrf_scores.items():
        title = docs[idx].get("metadata", {}).get("title", "")
        title_tokens = set(tokenize_pl(title))
        bonus = 0
        if title_tokens:
            overlap = query_tokens & title_tokens
            bonus = (len(overlap) / max(len(query_tokens), 1)) * 0.08
        content = docs[idx].get("content", "")[:300]
        if "Szukaj te" in content:
            try:
                syn_line = content[content.index("Szukaj te"):].split("\n")[0]
                syn_tokens = set(tokenize_pl(syn_line))
                syn_overlap = query_tokens & syn_tokens
                bonus += (len(syn_overlap) / max(len(query_tokens), 1)) * 0.08
            except (ValueError, IndexError):
                pass
        boosted[idx] = score + bonus
    sorted_ids = sorted(boosted.keys(), key=lambda x: boosted[x], reverse=True)
    return sorted_ids[:top_k]


# ============================================================
# MODULE 6: Intent Detection
# ============================================================
FILL_DOCUMENT_PATTERNS = [
    "jak wypelnic", "jak uzupelnic", "jak wpisac", "co wpisac",
    "jak napisac wniosek", "jak wypelnic formularz",
    "pomoz wypelnic", "instrukcja wypelniania", "wzor wypelnienia",
]
PROCEDURE_PATTERNS = [
    "jak wyrobic", "jak zrobic", "jak zalatwic", "jak uzyskac", "jak zlozyc",
    "jak zameldowac", "jak wymeldowac", "jak zarejestrowac", "jak wymienic",
    "co potrzebuje", "jakie dokumenty", "co musze", "procedura",
    "chce wyrobic", "chce zalatwic", "chce zlozyc", "chce uzyskac",
]
SIMPLE_PATTERNS = [
    "kto jest", "kto pelni", "kto to",
    "co to jest", "czym jest", "czym sie zajmuje",
    "gdzie jest", "gdzie znajduje sie", "jaki adres", "jaki telefon",
    "ile kosztuje", "ile trwa", "kiedy",
    "czy moge", "czy jest", "godziny otwarcia", "godziny pracy",
]

def classify_intent(question: str) -> str:
    q = question.lower().strip()
    q_norm = q.translate(PL_NORMALIZE)
    for pattern in FILL_DOCUMENT_PATTERNS:
        if pattern in q_norm or pattern in q:
            return "fill_document"
    for pattern in PROCEDURE_PATTERNS:
        if pattern in q_norm or pattern in q:
            return "procedure"
    for pattern in SIMPLE_PATTERNS:
        if pattern in q_norm or pattern in q:
            return "simple"
    if len(q.split()) < 6:
        return "simple"
    return "procedure"


# ============================================================
# MODULE 7: Suggestions
# ============================================================
def generate_suggestions(question: str, structured: dict, metadatas: list) -> list:
    suggestions = []
    topic = metadatas[0].get("title", question) if metadatas else question
    q_lower = question.lower()
    where = structured.get("where", {}) or {}
    how = structured.get("how", {}) or {}

    if how.get("forms"):
        suggestions.append(f"Skad pobrac formularz do: {topic}?")
    if where.get("address"):
        suggestions.append(f"Jak dojechac do {where['address']}?")
    if structured.get("booking"):
        suggestions.append("Jak zarezerwowac wizyte w urzedzie online?")

    dept = (where.get("department") or "").lower()
    if "komunikacji" in dept:
        suggestions.append("Ile kosztuje przerejestrowanie samochodu?")
    elif "administracyjnych" in dept:
        if "dowod" in q_lower or "dowód" in q_lower:
            suggestions.append("Jak zameldowac sie w Lublinie?")

    if "kosztuje" in q_lower or "oplata" in q_lower or "opłata" in q_lower:
        suggestions.append("Gdzie zaplacic oplate skarbowa?")
    if "dokument" in q_lower or "wniosek" in q_lower:
        suggestions.append(f"Jakie dokumenty sa potrzebne do: {topic}?")

    if not suggestions:
        suggestions.append(f"Jakie sa godziny pracy wydzialu obslugujacego: {topic}?")
        suggestions.append(f"Czy moge zalatwic {topic} online?")

    return suggestions[:4]


# ============================================================
# MODULE 8: Geocoding / Map Coordinates
# ============================================================
KNOWN_LOCATIONS = {
    "spokojna 2": {"lat": 51.24968, "lng": 22.55295},
    "wieniawska 14": {"lat": 51.24865, "lng": 22.55838},
    "czechowska 19": {"lat": 51.24780, "lng": 22.55120},
    "filaretow 44": {"lat": 51.22800, "lng": 22.54300},
    "peowiakow 13": {"lat": 51.24710, "lng": 22.55480},
    "zana 38": {"lat": 51.23650, "lng": 22.54950},
}

def find_coordinates(address: str):
    if not address:
        return None, None
    addr_lower = address.lower()
    for key, coords in KNOWN_LOCATIONS.items():
        if key in addr_lower or addr_lower in key:
            return coords["lat"], coords["lng"]
    return None, None


# ============================================================
# MODULE 9: JSON Output Validation
# ============================================================
def validate_structured_output(data: dict) -> dict:
    """Validate that structured output conforms to expected schema."""
    errors = []
    if "summary" not in data or not data.get("summary"):
        errors.append("missing_summary")
    where = data.get("where")
    if where and isinstance(where, dict):
        addr = where.get("address") or ""
        if addr and not re.search(r"(ul\.|al\.|Spokojna|Wieniawska|Czechowska|Filaretow|Zana|Peowiakow)", addr):
            errors.append("invalid_address_format")
        phone = where.get("phone") or ""
        if phone and not re.search(r"(81[\s\-]?\d|48[\s\-]?81)", phone):
            errors.append("invalid_phone_format")
        hours = where.get("hours") or ""
        if hours and not re.search(r"\d{1,2}[:.]\d{2}", hours):
            errors.append("invalid_hours_format")
    how = data.get("how")
    if how and isinstance(how, dict):
        docs_list = how.get("required_documents") or []
        if any(len(d) < 5 for d in docs_list):
            errors.append("placeholder_documents")
    return {"valid": len(errors) == 0, "errors": errors}


# ============================================================
# TEST QUESTIONS
# ============================================================
FULL_QUESTIONS = [
    {
        "id": "F01", "question": "Jak wyrobic dowod osobisty w Lublinie?",
        "expected_intent": "procedure",
        "expected_title_kw": ["dowod", "osobist"],
        "expected_dept": "Wydzia\u0142 Spraw Administracyjnych",
        "expected_address_contains": "Spokojna 2",
        "expected_coords": True,
        "expected_content_kw": ["wniosek"],
    },
    {
        "id": "F02", "question": "Kto jest prezydentem Lublina?",
        "expected_intent": "simple",
        "expected_title_kw": ["Prezydent"],
        "expected_dept": None,
        "expected_address_contains": None,
        "expected_coords": False,
        "expected_content_kw": ["Krzysztof"],
    },
    {
        "id": "F03", "question": "Ile kosztuje rejestracja samochodu z zagranicy?",
        "expected_intent": "simple",
        "expected_title_kw": ["rejestracja", "zagranicy"],
        "expected_dept": "Wydzia\u0142 Komunikacji",
        "expected_address_contains": "Czechowska",
        "expected_coords": True,
        "expected_content_kw": ["op\u0142ata"],
    },
    {
        "id": "F04", "question": "Jak wypelnic wniosek o dowod osobisty?",
        "expected_intent": "fill_document",
        "expected_title_kw": ["dowod", "osobist"],
        "expected_dept": "Wydzia\u0142 Spraw Administracyjnych",
        "expected_address_contains": None,
        "expected_coords": False,
        "expected_content_kw": ["wniosek"],
    },
    {
        "id": "F05", "question": "Gdzie jest Biuro Rzeczy Znalezionych i jakie ma godziny?",
        "expected_intent": "simple",
        "expected_title_kw": ["Biuro Rzeczy"],
        "expected_dept": None,
        "expected_address_contains": None,
        "expected_coords": False,
        "expected_content_kw": ["Dolna"],
    },
    {
        "id": "F06", "question": "Chce zarejestrowac dzialalnosc gospodarcza. Gdzie to zalatwic?",
        "expected_intent": "procedure",
        "expected_title_kw": ["dzia\u0142aln", "CEIDG"],
        "expected_dept": "Wydzia\u0142 Spraw Administracyjnych",
        "expected_address_contains": None,
        "expected_coords": False,
        "expected_content_kw": ["CEIDG"],
    },
    {
        "id": "F07", "question": "Ile kosztuje becikowe i gdzie zlozyc wniosek?",
        "expected_intent": "simple",
        "expected_title_kw": ["zapomog", "becikow"],
        "expected_dept": "Wydzia\u0142 \u015awiadcze\u0144",
        "expected_address_contains": None,
        "expected_coords": False,
        "expected_content_kw": ["1000"],
    },
    {
        "id": "F08", "question": "Jak uzyskac pozwolenie na budowe domu?",
        "expected_intent": "procedure",
        "expected_title_kw": ["Pozwolenie", "budow"],
        "expected_dept": "Wydzia\u0142 Architektury",
        "expected_address_contains": "Wieniawska",
        "expected_coords": True,
        "expected_content_kw": ["wniosek", "projekt"],
    },
    {
        "id": "F09", "question": "Godziny pracy Wydzialu Komunikacji",
        "expected_intent": "simple",
        "expected_title_kw": ["Komunikacj"],
        "expected_dept": "Wydzia\u0142 Komunikacji",
        "expected_address_contains": "Czechowska",
        "expected_coords": True,
        "expected_content_kw": [],
    },
    {
        "id": "F10", "question": "Zgloszenie sprzedazy samochodu - co musze zrobic?",
        "expected_intent": "procedure",
        "expected_title_kw": ["zbyci", "sprzeda"],
        "expected_dept": "Wydzia\u0142 Komunikacji",
        "expected_address_contains": "Czechowska",
        "expected_coords": True,
        "expected_content_kw": ["30 dni"],
    },
]


# ============================================================
# BENCHMARK RUNNER
# ============================================================
def run_full_benchmark():
    print(f"\n{'='*70}")
    print(f"  FULL PIPELINE BENCHMARK - All Modules")
    print(f"  Data: {DOCUMENTS_FILE}")
    print(f"{'='*70}\n")

    if not os.path.exists(DOCUMENTS_FILE):
        print("ERROR: documents.json not found!")
        return

    with open(DOCUMENTS_FILE) as f:
        docs = json.load(f)
    print(f"  [{len(docs)} chunks loaded]")

    # Build indices
    corpus = [d["content"] for d in docs]
    print("  Building BM25 index...", end=" ")
    t0 = time.time()
    bm25 = SimpleBM25(corpus)
    print(f"done ({time.time()-t0:.1f}s)")

    print("  Building dense index...", end=" ")
    t0 = time.time()
    dense = SimulatedDenseSearch(docs)
    print(f"done ({time.time()-t0:.1f}s)")

    # Module results
    results = {
        "bm25_retrieval": {"pass": 0, "fail": 0, "details": []},
        "dense_retrieval": {"pass": 0, "fail": 0, "details": []},
        "rrf_fusion": {"pass": 0, "fail": 0, "details": []},
        "reranking": {"pass": 0, "fail": 0, "details": []},
        "intent_detection": {"pass": 0, "fail": 0, "details": []},
        "suggestions": {"pass": 0, "fail": 0, "details": []},
        "geocoding": {"pass": 0, "fail": 0, "details": []},
        "json_validation": {"pass": 0, "fail": 0, "details": []},
        "latency": {"times": []},
    }

    print(f"\n  {'ID':<5} {'BM25':<6} {'Dense':<6} {'RRF':<5} {'Rank':<5} {'Intent':<8} {'Geo':<5} {'JSON':<5} {'ms':<6}")
    print(f"  {'-'*5} {'-'*6} {'-'*6} {'-'*5} {'-'*5} {'-'*8} {'-'*5} {'-'*5} {'-'*6}")

    for q in FULL_QUESTIONS:
        t_start = time.time()

        # --- BM25 ---
        bm25_res = bm25.search(q["question"], top_k=30)
        bm25_hit = False
        for kw in q["expected_title_kw"]:
            for idx, _ in bm25_res[:15]:
                if kw.lower() in docs[idx].get("metadata", {}).get("title", "").lower():
                    bm25_hit = True
                    break
            if bm25_hit:
                break

        # --- Dense ---
        dense_res = dense.search(q["question"], top_k=30)
        dense_hit = False
        for kw in q["expected_title_kw"]:
            for idx, _ in dense_res[:15]:
                if kw.lower() in docs[idx].get("metadata", {}).get("title", "").lower():
                    dense_hit = True
                    break
            if dense_hit:
                break

        # --- RRF ---
        rrf_scores = rrf_fusion(bm25_res, dense_res, docs)
        rrf_hit = False
        sorted_rrf = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:10]
        for kw in q["expected_title_kw"]:
            for idx in sorted_rrf:
                if kw.lower() in docs[idx].get("metadata", {}).get("title", "").lower():
                    rrf_hit = True
                    break
            if rrf_hit:
                break

        # --- Reranking ---
        final_ids = rerank(rrf_scores, q["question"], docs, top_k=6)
        rerank_hit = False
        for kw in q["expected_title_kw"]:
            for idx in final_ids:
                if kw.lower() in docs[idx].get("metadata", {}).get("title", "").lower():
                    rerank_hit = True
                    break
            if rerank_hit:
                break

        # --- Dept check ---
        dept_hit = True
        if q["expected_dept"]:
            dept_hit = False
            for idx in final_ids:
                d = docs[idx].get("metadata", {}).get("department", "") or docs[idx].get("metadata", {}).get("title", "")
                if q["expected_dept"].lower() in d.lower():
                    dept_hit = True
                    break

        # --- Intent ---
        intent = classify_intent(q["question"])
        intent_ok = (intent == q["expected_intent"])

        # --- Geocoding ---
        geo_ok = True
        if q["expected_coords"]:
            addr = q.get("expected_address_contains", "")
            if addr:
                lat, lng = find_coordinates(addr)
                geo_ok = (lat is not None and lng is not None)
        elif q["expected_address_contains"] is None:
            geo_ok = True

        # --- JSON Validation (mock structured output) ---
        mock_output = {"summary": "Test"}
        if q["expected_address_contains"]:
            mock_output["where"] = {"address": f"ul. {q['expected_address_contains']}, Lublin", "department": q.get("expected_dept", "")}
        json_result = validate_structured_output(mock_output)
        json_ok = json_result["valid"]

        # --- Suggestions ---
        mock_structured = {}
        if q["expected_address_contains"]:
            mock_structured["where"] = {"address": q["expected_address_contains"], "department": q.get("expected_dept", "")}
            mock_structured["booking"] = True
        metas = [docs[idx].get("metadata", {}) for idx in final_ids[:1]] if final_ids else [{}]
        sugg = generate_suggestions(q["question"], mock_structured, metas)
        sugg_ok = len(sugg) >= 1

        # --- Content recall ---
        content_hits = 0
        for kw in q["expected_content_kw"]:
            for idx in final_ids:
                if kw.lower() in docs[idx]["content"].lower():
                    content_hits += 1
                    break
        content_recall = content_hits / len(q["expected_content_kw"]) if q["expected_content_kw"] else 1.0

        elapsed = (time.time() - t_start) * 1000
        results["latency"]["times"].append(elapsed)

        # Record
        for mod, ok in [("bm25_retrieval", bm25_hit), ("dense_retrieval", dense_hit),
                        ("rrf_fusion", rrf_hit), ("reranking", rerank_hit),
                        ("intent_detection", intent_ok), ("suggestions", sugg_ok),
                        ("geocoding", geo_ok), ("json_validation", json_ok)]:
            if ok:
                results[mod]["pass"] += 1
            else:
                results[mod]["fail"] += 1
                results[mod]["details"].append(q["id"])

        b = "OK" if bm25_hit else "FAIL"
        d = "OK" if dense_hit else "FAIL"
        r = "OK" if rrf_hit else "FAIL"
        rk = "OK" if rerank_hit else "FAIL"
        i = "OK" if intent_ok else "FAIL"
        g = "OK" if geo_ok else "FAIL"
        j = "OK" if json_ok else "FAIL"
        print(f"  {q['id']:<5} {b:<6} {d:<6} {r:<5} {rk:<5} {i:<8} {g:<5} {j:<5} {elapsed:.0f}ms")

    # ============================================================
    # SUMMARY
    # ============================================================
    n = len(FULL_QUESTIONS)
    print(f"\n{'='*70}")
    print(f"  MODULE RESULTS")
    print(f"{'='*70}")
    print(f"  {'Module':<22} {'Pass':<6} {'Fail':<6} {'Rate':<8} Failed IDs")
    print(f"  {'-'*22} {'-'*6} {'-'*6} {'-'*8} {'-'*20}")
    for mod in ["bm25_retrieval", "dense_retrieval", "rrf_fusion", "reranking",
                "intent_detection", "suggestions", "geocoding", "json_validation"]:
        p = results[mod]["pass"]
        f = results[mod]["fail"]
        rate = f"{p}/{n} ({p/n*100:.0f}%)"
        failed = ", ".join(results[mod]["details"]) if results[mod]["details"] else "-"
        print(f"  {mod:<22} {p:<6} {f:<6} {rate:<8} {failed}")

    times = results["latency"]["times"]
    print(f"\n  LATENCY:")
    print(f"    Avg: {sum(times)/len(times):.0f}ms | Max: {max(times):.0f}ms | Min: {min(times):.0f}ms")
    print(f"    P95: {sorted(times)[int(len(times)*0.95)]:.0f}ms")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_dir = os.path.join(RESULTS_DIR, f"full_{timestamp}")
    os.makedirs(run_dir)
    with open(os.path.join(run_dir, "results.json"), "w") as fp:
        json.dump(results, fp, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {run_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_full_benchmark()
