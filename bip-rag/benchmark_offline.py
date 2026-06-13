#!/usr/bin/env python3
"""
Benchmark RAG BIP Lublin - OFFLINE (no server needed).
Testuje retrieval (BM25) bezpośrednio na documents.json.
Nie wymaga żadnych zewnętrznych pakietów.

Uruchom:
    cd bip-rag && python3 benchmark_offline.py
"""
import json
import math
import os
import re
import time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results")


# --- Minimal BM25 implementation (no deps) ---
def tokenize_pl(text: str) -> list:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 2]


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
        for q in query_tokens:
            if q not in self.df:
                continue
            idf = math.log((self.corpus_size - self.df[q] + 0.5) / (self.df[q] + 0.5) + 1)
            for i, doc in enumerate(self.tokenized):
                tf = doc.count(q)
                if tf == 0:
                    continue
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * numerator / denominator
        return scores

    def search(self, query: str, top_k: int = 15) -> list:
        tokens = tokenize_pl(query)
        scores = self.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(idx, scores[idx]) for idx in ranked[:top_k] if scores[idx] > 0]


# --- Title match boost (simulates the hybrid re-ranking from app.py) ---
def title_boost_rerank(results: list, query: str, docs: list, top_k: int = 6) -> list:
    query_words = set(w for w in tokenize_pl(query) if len(w) > 3)
    boosted = []
    for idx, score in results:
        title = docs[idx].get("metadata", {}).get("title", "").lower()
        title_words = [w for w in title.split() if len(w) > 3]
        bonus = 0
        if title_words:
            matching = sum(1 for w in title_words if w in query.lower())
            bonus += (matching / len(title_words)) * 2.0
            reverse_match = sum(1 for w in query_words if w in title)
            if query_words:
                bonus += (reverse_match / len(query_words)) * 2.0
        boosted.append((idx, score + bonus))
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted[:top_k]


# --- Golden questions (same as benchmark.py) ---
GOLDEN_QUESTIONS = [
    {
        "id": "Q01",
        "question": "Jak wyrobić dowód osobisty w Lublinie?",
        "category": "HOW+WHERE",
        "difficulty": "easy",
        "expected_title_keywords": ["dowód osobisty"],
        "expected_department": "Wydział Spraw Administracyjnych",
        "expected_address": "Spokojna 2",
        "expected_content_keywords": ["wniosek", "zdjęcie", "osobiście"],
        "ground_truth_notes": "Usługa SA-025. Wydział Spraw Administracyjnych, ul. Spokojna 2. Wymagane: wniosek, zdjęcie 35x45mm, dowód tożsamości. Bezpłatne. Termin: 30 dni.",
    },
    {
        "id": "Q02",
        "question": "Ile kosztuje rejestracja samochodu z zagranicy?",
        "category": "HOW_MUCH+WHERE",
        "difficulty": "medium",
        "expected_title_keywords": ["rejestracja", "zagranicy"],
        "expected_department": "Wydział Komunikacji",
        "expected_address": "Czechowska 19",
        "expected_content_keywords": ["opłata", "rejestracyjn", "tablice"],
        "ground_truth_notes": "Usługa KM. Wydział Komunikacji, Czechowska 19A. Opłaty: 256.50 zł (tablice + dowód + nalepka + opłata ewidencyjna). Akcyza, badanie techniczne osobno.",
    },
    {
        "id": "Q03",
        "question": "Kto jest prezydentem Lublina?",
        "category": "WHO",
        "difficulty": "easy",
        "expected_title_keywords": ["Prezydent"],
        "expected_department": None,
        "expected_address": None,
        "expected_content_keywords": ["Krzysztof", "Żuk"],
        "ground_truth_notes": "Krzysztof Żuk, Prezydent Miasta Lublin od 2010 r. Plac Króla Władysława Łokietka 1.",
    },
    {
        "id": "Q04",
        "question": "Gdzie jest Biuro Rzeczy Znalezionych i jakie ma godziny otwarcia?",
        "category": "WHERE",
        "difficulty": "easy",
        "expected_title_keywords": ["Biuro Rzeczy Znalezionych"],
        "expected_department": "Wydział Organizacji Urzędu",
        "expected_address": "Dolna 3-Maja 5",
        "expected_content_keywords": ["Dolna", "7:30", "15:30"],
        "ground_truth_notes": "Wydział Organizacji Urzędu, ul. Dolna 3-Maja 5, pok. 3 (parter), tel. 81 466 1200. Pon-pt 07:30-15:30.",
    },
    {
        "id": "Q05",
        "question": "Jakie dokumenty potrzebuję do wymiany prawa jazdy po zmianie nazwiska?",
        "category": "HOW",
        "difficulty": "medium",
        "expected_title_keywords": ["prawa jazdy", "zmiany danych"],
        "expected_department": "Wydział Komunikacji",
        "expected_address": "Czechowska 19",
        "expected_content_keywords": ["wniosek", "zdjęcie", "prawo jazdy", "100"],
        "ground_truth_notes": "Usługa KM-024. Wydział Komunikacji. Dokumenty: wniosek, zdjęcie, dotychczasowe prawo jazdy, dowód osobisty. Opłata 100 zł + 0.50 zł.",
    },
    {
        "id": "Q06",
        "question": "Jak złożyć wniosek o dodatek mieszkaniowy?",
        "category": "HOW+WHERE",
        "difficulty": "medium",
        "expected_title_keywords": ["dodatek", "mieszkaniow"],
        "expected_department": "Wydział Świadczeń",
        "expected_address": None,
        "expected_content_keywords": ["wniosek", "dochód", "powierzchni"],
        "ground_truth_notes": "Wydział Świadczeń. Wymagane: wniosek + deklaracja o dochodach. Kryterium dochodowe i metrażowe. Decyzja w 30 dni.",
    },
    {
        "id": "Q07",
        "question": "Jak załatwić wypis z planu zagospodarowania przestrzennego?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "hard",
        "expected_title_keywords": ["Wypis", "wyrys", "Miejscowego Planu"],
        "expected_department": "Wydział Planowania",
        "expected_address": None,
        "expected_content_keywords": ["wniosek", "opłata", "skarbowa"],
        "ground_truth_notes": "Wydział Planowania. Opłata skarbowa: 30 zł za wypis do 5 stron, 50 zł powyżej. Wyrys 20 zł za każdą stronę A4. Termin: bez zbędnej zwłoki, max 30 dni.",
    },
    {
        "id": "Q08",
        "question": "Chcę zarejestrować działalność gospodarczą. Gdzie w urzędzie to załatwię?",
        "category": "WHERE+HOW",
        "difficulty": "hard",
        "expected_title_keywords": ["działaln", "gospodar", "CEIDG"],
        "expected_department": "Wydział Spraw Administracyjnych",
        "expected_address": None,
        "expected_content_keywords": ["CEIDG", "wniosek", "rejestr"],
        "ground_truth_notes": "Rejestracja poprzez CEIDG (online). W UM Lublin pomoc w Wydziale Działalności Gospodarczej lub Biurze Obsługi Mieszkańców. Bezpłatne.",
    },
    {
        "id": "Q09",
        "question": "Jakie są godziny pracy Urzędu Stanu Cywilnego i jak zarejestrować urodzenie dziecka?",
        "category": "WHERE+HOW",
        "difficulty": "medium",
        "expected_title_keywords": ["Stanu Cywilnego", "urodzen"],
        "expected_department": "Urząd Stanu Cywilnego",
        "expected_address": "Spokojna 2",
        "expected_content_keywords": ["7:45", "15:15", "akt urodz"],
        "ground_truth_notes": "USC, Spokojna 2, II piętro. Godziny: pon-pt 7:45-15:15. Rejestracja urodzenia: w ciągu 21 dni. Wymagane: karta urodzenia ze szpitala, dowody rodziców.",
    },
    {
        "id": "Q10",
        "question": "Zgłoszenie sprzedaży samochodu - co muszę zrobić i ile mam czasu?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "medium",
        "expected_title_keywords": ["zbyci", "pojazd"],
        "expected_department": "Wydział Komunikacji",
        "expected_address": "Czechowska 19",
        "expected_content_keywords": ["30 dni", "zawiadomieni", "umow"],
        "ground_truth_notes": "Usługa KM - Zgłoszenie zbycia pojazdu. Wydział Komunikacji. Termin: 30 dni od sprzedaży. Dokumenty: zawiadomienie + kopia umowy. Bezpłatne.",
    },
]


def run_benchmark():
    print(f"\n{'='*70}")
    print(f"  BENCHMARK OFFLINE - BM25 Retrieval Test")
    print(f"  Data: {DOCUMENTS_FILE}")
    print(f"{'='*70}\n")

    if not os.path.exists(DOCUMENTS_FILE):
        print("ERROR: documents.json not found!")
        return

    with open(DOCUMENTS_FILE) as f:
        docs = json.load(f)
    print(f"  Loaded {len(docs)} document chunks")

    corpus = [d["content"] for d in docs]
    print("  Building BM25 index...")
    t0 = time.time()
    bm25 = SimpleBM25(corpus)
    print(f"  BM25 index built in {time.time()-t0:.1f}s\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_dir = os.path.join(RESULTS_DIR, f"offline_{timestamp}")
    os.makedirs(run_dir)

    all_results = []
    total_title_hit = 0
    total_dept_hit = 0
    total_content_recall = 0

    print(f"  {'ID':<5} {'Diff':<7} {'Title':<7} {'Dept':<6} {'Content':<9} {'Time':<6} Question")
    print(f"  {'-'*5} {'-'*7} {'-'*7} {'-'*6} {'-'*9} {'-'*6} {'-'*45}")

    for q in GOLDEN_QUESTIONS:
        t0 = time.time()
        raw_results = bm25.search(q["question"], top_k=15)
        reranked = title_boost_rerank(raw_results, q["question"], docs, top_k=6)
        search_time = time.time() - t0

        # Evaluate retrieval
        top6_docs = [docs[idx] for idx, _ in reranked]
        top15_docs = [docs[idx] for idx, _ in raw_results]

        # 1. Title keyword hit in top-6
        title_hit = False
        for kw in q["expected_title_keywords"]:
            for d in top6_docs:
                if kw.lower() in d.get("metadata", {}).get("title", "").lower():
                    title_hit = True
                    break
            if title_hit:
                break

        # 2. Department hit in top-6
        dept_hit = False
        if q["expected_department"]:
            for d in top6_docs:
                dept = d.get("metadata", {}).get("department", "") or d.get("metadata", {}).get("title", "")
                if q["expected_department"].lower() in dept.lower():
                    dept_hit = True
                    break
        else:
            dept_hit = True  # N/A

        # 3. Content keyword recall in top-6
        content_hits = 0
        for kw in q["expected_content_keywords"]:
            for d in top6_docs:
                if kw.lower() in d["content"].lower():
                    content_hits += 1
                    break
        content_recall = content_hits / len(q["expected_content_keywords"]) if q["expected_content_keywords"] else 0

        total_title_hit += int(title_hit)
        total_dept_hit += int(dept_hit)
        total_content_recall += content_recall

        # Detailed result
        result = {
            "id": q["id"],
            "question": q["question"],
            "difficulty": q["difficulty"],
            "category": q["category"],
            "search_time_ms": round(search_time * 1000, 1),
            "title_hit": title_hit,
            "department_hit": dept_hit,
            "content_recall": round(content_recall, 3),
            "content_keywords_found": [],
            "content_keywords_missing": [],
            "top6_titles": [d.get("metadata", {}).get("title", "?")[:60] for d in top6_docs],
            "top6_types": [d.get("metadata", {}).get("type", "?") for d in top6_docs],
            "top6_departments": [d.get("metadata", {}).get("department", "?")[:40] for d in top6_docs],
            "top6_scores": [round(s, 3) for _, s in reranked],
            "top15_titles": [d.get("metadata", {}).get("title", "?")[:60] for d in top15_docs],
            "top6_content_preview": [d["content"][:200] for d in top6_docs],
            "ground_truth": q["ground_truth_notes"],
            "expected_department": q["expected_department"],
            "expected_address": q["expected_address"],
        }

        # Track which content keywords hit/miss
        for kw in q["expected_content_keywords"]:
            found = any(kw.lower() in d["content"].lower() for d in top6_docs)
            if found:
                result["content_keywords_found"].append(kw)
            else:
                result["content_keywords_missing"].append(kw)

        all_results.append(result)

        t_str = "HIT" if title_hit else "MISS"
        d_str = "HIT" if dept_hit else "MISS"
        c_str = f"{content_recall*100:.0f}%"
        print(f"  {q['id']:<5} {q['difficulty']:<7} {t_str:<7} {d_str:<6} {c_str:<9} {search_time*1000:.0f}ms  {q['question'][:45]}")

    # Summary
    n = len(GOLDEN_QUESTIONS)
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Title Hit Rate:     {total_title_hit}/{n} ({total_title_hit/n*100:.0f}%)")
    print(f"  Department Hit Rate: {total_dept_hit}/{n} ({total_dept_hit/n*100:.0f}%)")
    print(f"  Avg Content Recall:  {total_content_recall/n*100:.1f}%")

    # Failures
    print(f"\n  FAILURES (things to fix):")
    print(f"  {'─'*60}")
    for r in all_results:
        issues = []
        if not r["title_hit"]:
            issues.append(f"Title MISS - got: {r['top6_titles'][:3]}")
        if not r["department_hit"]:
            issues.append(f"Dept MISS - expected '{r['expected_department']}', got: {r['top6_departments'][:3]}")
        if r["content_keywords_missing"]:
            issues.append(f"Content keywords missing: {r['content_keywords_missing']}")
        if issues:
            print(f"\n  {r['id']} [{r['difficulty']}] {r['question'][:50]}")
            for issue in issues:
                print(f"    -> {issue}")

    # Save results
    full_path = os.path.join(run_dir, "full_results.json")
    with open(full_path, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    summary = {
        "timestamp": timestamp,
        "total_chunks": len(docs),
        "title_hit_rate": total_title_hit / n,
        "department_hit_rate": total_dept_hit / n,
        "avg_content_recall": total_content_recall / n,
        "per_question": [{
            "id": r["id"],
            "question": r["question"][:60],
            "title_hit": r["title_hit"],
            "dept_hit": r["department_hit"],
            "content_recall": r["content_recall"],
            "missing": r["content_keywords_missing"],
            "top3_titles": r["top6_titles"][:3],
        } for r in all_results],
    }
    summary_path = os.path.join(run_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  Results saved to: {run_dir}/")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_benchmark()
