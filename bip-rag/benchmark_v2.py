#!/usr/bin/env python3
"""
Benchmark RAG BIP Lublin v2 - OFFLINE (no server needed).
Nowy zestaw 10 pytań testujących inne usługi i trudniejsze przypadki.

Uruchom:
    cd bip-rag && python3 benchmark_v2.py
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
PL_NORMALIZE = str.maketrans("óąęćśźżłń", "oaecszzln")


def tokenize_pl(text: str) -> list:
    text = text.lower().translate(PL_NORMALIZE)
    text = re.sub(r"[^\w\s]", " ", text)
    return [t[:5] for t in text.split() if len(t) > 2]


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

    def search(self, query: str, top_k: int = 50) -> list:
        tokens = tokenize_pl(query)
        scores = self.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(idx, scores[idx]) for idx in ranked[:top_k] if scores[idx] > 0]


def title_boost_rerank(results: list, query: str, docs: list, top_k: int = 6) -> list:
    query_tokens = set(tokenize_pl(query))
    boosted = []
    for idx, score in results:
        title = docs[idx].get("metadata", {}).get("title", "")
        title_tokens = set(tokenize_pl(title))
        bonus = 0
        if title_tokens:
            overlap = query_tokens & title_tokens
            bonus = (len(overlap) / max(len(query_tokens), 1)) * 3.0

        content = docs[idx].get("content", "")
        header = content[:300]
        if "Szukaj też:" in header:
            synonym_line = header[header.index("Szukaj też:"):].split("\n")[0]
            syn_tokens = set(tokenize_pl(synonym_line))
            syn_overlap = query_tokens & syn_tokens
            syn_ratio = len(syn_overlap) / max(len(query_tokens), 1)
            bonus += syn_ratio * 4.0

        boosted.append((idx, score + bonus))
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted[:top_k]


# --- Benchmark v2: 10 nowych pytań ---
GOLDEN_QUESTIONS_V2 = [
    {
        "id": "V01",
        "question": "Jak uzyskać Kartę Dużej Rodziny w Lublinie?",
        "category": "HOW+WHERE",
        "difficulty": "medium",
        "expected_title_keywords": ["Karta", "Dużej Rodziny"],
        "expected_department": "Wydział Inicjatyw i Programów Społecznych",
        "expected_address": None,
        "expected_content_keywords": ["wniosek", "troje", "oświadczen"],
        "ground_truth_notes": "Wydział Inicjatyw i Programów Społecznych. Wniosek przez Emp@tia lub osobiście. Rodzina z min. 3 dzieci. Duplikat 17 zł.",
    },
    {
        "id": "V02",
        "question": "Chcę wziąć ślub cywilny w Lublinie. Ile to kosztuje i jakie dokumenty?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "medium",
        "expected_title_keywords": ["małżeństwo", "ślub", "USC"],
        "expected_department": "Urząd Stanu Cywilnego",
        "expected_address": None,
        "expected_content_keywords": ["84 zł", "zapewnieni", "dowod"],
        "ground_truth_notes": "USC Lublin, Rynek 1. Opłata 84 zł za akt małżeństwa. Wymagane: dowody osobiste, zapewnienie o braku przeszkód. Miesiąc oczekiwania.",
    },
    {
        "id": "V03",
        "question": "Ile kosztuje becikowe i gdzie złożyć wniosek?",
        "category": "HOW_MUCH+WHERE",
        "difficulty": "easy",
        "expected_title_keywords": ["zapomog", "urodzeni", "becikow"],
        "expected_department": "Wydział Świadczeń",
        "expected_address": None,
        "expected_content_keywords": ["1000", "wniosek", "urodzeni"],
        "ground_truth_notes": "Becikowe = 1000 zł. Kryterium dochodu 1922 zł/os. Wniosek w 12 mies. od urodzenia. Wydział Świadczeń.",
    },
    {
        "id": "V04",
        "question": "Gdzie i jak wyrobić kartę wędkarską w Lublinie?",
        "category": "HOW+WHERE",
        "difficulty": "easy",
        "expected_title_keywords": ["wędkars"],
        "expected_department": "Wydział Geodezji",
        "expected_address": None,
        "expected_content_keywords": ["10 zł", "wniosek", "egzamin"],
        "ground_truth_notes": "Wydział Geodezji, ul. Spokojna 2. Opłata 10 zł. Wymagane: wniosek + zaświadczenie o zdaniu egzaminu PZW.",
    },
    {
        "id": "V05",
        "question": "Jak uzyskać pozwolenie na budowę domu w Lublinie?",
        "category": "HOW+WHERE",
        "difficulty": "hard",
        "expected_title_keywords": ["Pozwolenie", "budow"],
        "expected_department": "Wydział Architektury i Budownictwa",
        "expected_address": None,
        "expected_content_keywords": ["wniosek", "projekt", "decyzj"],
        "ground_truth_notes": "Wydział Architektury i Budownictwa, Wieniawska 14. Wniosek + 4 egz. projektu + opinia ZUD + decyzja WZ. Opłata: 47 zł za każdy obiekt.",
    },
    {
        "id": "V06",
        "question": "Jak zameldować się na stałe w Lublinie?",
        "category": "HOW+WHERE",
        "difficulty": "easy",
        "expected_title_keywords": ["Zameldowanie", "pobyt stały"],
        "expected_department": "Wydział Spraw Administracyjnych",
        "expected_address": "Spokojna 2",
        "expected_content_keywords": ["zgłoszenie", "pełnomocnictw", "SA-007"],
        "ground_truth_notes": "Wydział Spraw Administracyjnych, Spokojna 2. Bezpłatne. Formularz SA-007-01 zgłoszenie pobytu stałego + pełnomocnictwo.",
    },
    {
        "id": "V07",
        "question": "Ile kosztuje karta parkingowa dla osoby niepełnosprawnej?",
        "category": "HOW_MUCH+HOW",
        "difficulty": "medium",
        "expected_title_keywords": ["parkingowa", "niepełnospraw"],
        "expected_department": "Miejski Zespół do Spraw Orzekania o Niepełnosprawności",
        "expected_address": None,
        "expected_content_keywords": ["21 zł", "wniosek", "orzeczeni"],
        "ground_truth_notes": "Miejski Zespół ds. Orzekania o Niepełnosprawności. Opłata 21 zł. Wymagane: wniosek + orzeczenie + zdjęcie.",
    },
    {
        "id": "V08",
        "question": "Jak zarejestrować żłobek w Lublinie i ile to kosztuje?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "hard",
        "expected_title_keywords": ["żłobk", "rejestr", "klub"],
        "expected_department": "Wydział Zdrowia i Profilaktyki",
        "expected_address": None,
        "expected_content_keywords": ["1000", "wniosek", "rejestr"],
        "ground_truth_notes": "Wydział Zdrowia i Profilaktyki. Opłata 1000 zł za wpis. Wniosek przez portal elektroniczny.",
    },
    {
        "id": "V09",
        "question": "Czy potrzebuję zezwolenia na posiadanie psa rasy agresywnej w Lublinie?",
        "category": "HOW",
        "difficulty": "hard",
        "expected_title_keywords": ["hodowani", "psa", "zezwoleni"],
        "expected_department": "Wydział Zieleni i Gospodarki Komunalnej",
        "expected_address": None,
        "expected_content_keywords": ["zezwoleni", "opłata", "skarbowa"],
        "ground_truth_notes": "Wydział Zieleni i Gospodarki Komunalnej. Wymagane zezwolenie. Opłata skarbowa. Zana 38.",
    },
    {
        "id": "V10",
        "question": "Jak uzyskać zasiłek pielęgnacyjny i ile wynosi?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "medium",
        "expected_title_keywords": ["zasiłek", "pielęgnacyjn"],
        "expected_department": "Wydział Świadczeń",
        "expected_address": None,
        "expected_content_keywords": ["wniosek", "orzeczeni", "niepełnospraw"],
        "ground_truth_notes": "Wydział Świadczeń. Zasiłek pielęgnacyjny 215.84 zł/mies. Wniosek + orzeczenie o niepełnosprawności. Brak kryterium dochodu.",
    },
]


def run_benchmark():
    print(f"\n{'='*70}")
    print(f"  BENCHMARK v2 OFFLINE - BM25 Retrieval Test (nowe pytania)")
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
    run_dir = os.path.join(RESULTS_DIR, f"v2_offline_{timestamp}")
    os.makedirs(run_dir)

    all_results = []
    total_title_hit = 0
    total_dept_hit = 0
    total_content_recall = 0

    print(f"  {'ID':<5} {'Diff':<7} {'Title':<7} {'Dept':<6} {'Content':<9} {'Time':<6} Question")
    print(f"  {'-'*5} {'-'*7} {'-'*7} {'-'*6} {'-'*9} {'-'*6} {'-'*45}")

    for q in GOLDEN_QUESTIONS_V2:
        t0 = time.time()
        raw_results = bm25.search(q["question"], top_k=50)
        reranked = title_boost_rerank(raw_results, q["question"], docs, top_k=6)
        search_time = time.time() - t0

        top6_docs = [docs[idx] for idx, _ in reranked]

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
            dept_hit = True

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
            "top6_departments": [d.get("metadata", {}).get("department", "?")[:40] for d in top6_docs],
            "expected_department": q["expected_department"] or "N/A",
        }

        for kw in q["expected_content_keywords"]:
            found = False
            for d in top6_docs:
                if kw.lower() in d["content"].lower():
                    found = True
                    break
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
    n = len(GOLDEN_QUESTIONS_V2)
    print(f"\n{'='*70}")
    print(f"  SUMMARY (Benchmark v2)")
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
    with open(os.path.join(run_dir, "full_results.json"), "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    summary = {
        "timestamp": timestamp,
        "version": "v2",
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
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  Results saved to: {run_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_benchmark()
