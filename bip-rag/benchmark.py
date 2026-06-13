#!/usr/bin/env python3
"""
Benchmark RAG BIP Lublin - 10 pytań walidacyjnych.

Uruchom serwer przed benchmarkiem:
    cd bip-rag && python app.py

Następnie:
    python benchmark.py [--url http://localhost:8000]

Generuje szczegółowe logi do `benchmark_results/` z metrykami:
- Retrieval: trafność źródeł, pokrycie tematyczne
- Generation: poprawność JSON, kompletność pól, zgodność z expected
- Timing: czas odpowiedzi per pytanie
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import requests

BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), "benchmark_results")

# --- GOLDEN DATASET: 10 pytań benchmarkowych ---
# Każde pytanie ma:
#   - question: naturalne pytanie mieszkańca
#   - category: typ pytania (WHERE/HOW/HOW_MUCH/WHO/MIXED)
#   - difficulty: easy/medium/hard
#   - expected: oczekiwane wartości kluczowe w odpowiedzi
#   - expected_sources: fragmenty tytułów/URL-i, które powinny się pojawić w retrieval
#   - tests: lista testów do wykonania na odpowiedzi

GOLDEN_QUESTIONS = [
    {
        "id": "Q01",
        "question": "Jak wyrobić dowód osobisty w Lublinie?",
        "category": "HOW+WHERE",
        "difficulty": "easy",
        "description": "Najpopularniejsza usługa - dowód osobisty. Testuje czy RAG trafia na Wydział Spraw Administracyjnych i Spokojna 2.",
        "expected": {
            "department": "Wydział Spraw Administracyjnych",
            "address_fragment": "Spokojna 2",
            "has_steps": True,
            "booking": True,
        },
        "expected_sources_keywords": ["dowód osobisty", "Spraw Administracyjnych"],
        "tests": [
            "response.get('where', {}).get('department') powinien zawierać 'Spraw Administracyjnych'",
            "response.get('where', {}).get('address') powinien zawierać 'Spokojna'",
            "response.get('how', {}).get('steps') powinien być niepustą listą",
        ],
    },
    {
        "id": "Q02",
        "question": "Ile kosztuje rejestracja samochodu z zagranicy?",
        "category": "HOW_MUCH+WHERE",
        "difficulty": "medium",
        "description": "Testuje retrieval usługi rejestracji pojazdu z zagranicy + ekstrakcję opłat.",
        "expected": {
            "department": "Wydział Komunikacji",
            "address_fragment": "Czechowska 19",
            "has_cost": True,
        },
        "expected_sources_keywords": ["rejestracja", "zagranicy", "Komunikacji"],
        "tests": [
            "response.get('where', {}).get('department') powinien zawierać 'Komunikacji'",
            "response.get('how_much', {}).get('cost') powinien być niepusty",
            "response.get('where', {}).get('address') powinien zawierać 'Czechowska'",
        ],
    },
    {
        "id": "Q03",
        "question": "Kto jest prezydentem Lublina?",
        "category": "WHO",
        "difficulty": "easy",
        "description": "Testuje retrieval danych o osobach (prezydent). Odpowiedź: Krzysztof Żuk.",
        "expected": {
            "who_name": "Krzysztof Żuk",
            "who_role": "Prezydent",
        },
        "expected_sources_keywords": ["Prezydent", "Krzysztof"],
        "tests": [
            "response.get('who', {}).get('name') powinien zawierać 'Żuk' lub 'Krzysztof'",
            "'prezydent' powinien pojawić się w summary lub who.role",
        ],
    },
    {
        "id": "Q04",
        "question": "Gdzie jest Biuro Rzeczy Znalezionych i jakie ma godziny otwarcia?",
        "category": "WHERE",
        "difficulty": "easy",
        "description": "Proste pytanie lokalizacyjne. Dolna 3-Maja 5, 07:30-15:30.",
        "expected": {
            "address_fragment": "Dolna 3-Maja",
            "hours_fragment": "7:30",
            "department": "Wydział Organizacji Urzędu",
        },
        "expected_sources_keywords": ["Biuro Rzeczy Znalezionych", "Organizacji"],
        "tests": [
            "response.get('where', {}).get('address') powinien zawierać 'Dolna' lub '3-Maja'",
            "response.get('where', {}).get('hours') powinien zawierać '7:30' lub '07:30'",
        ],
    },
    {
        "id": "Q05",
        "question": "Jakie dokumenty potrzebuję do wymiany prawa jazdy po zmianie nazwiska?",
        "category": "HOW",
        "difficulty": "medium",
        "description": "Testuje ekstrakcję wymaganych dokumentów z karty usługi KM.",
        "expected": {
            "department": "Wydział Komunikacji",
            "has_required_documents": True,
            "has_steps": True,
        },
        "expected_sources_keywords": ["prawa jazdy", "zmiany danych", "Komunikacji"],
        "tests": [
            "response.get('how', {}).get('required_documents') powinien być niepustą listą",
            "response.get('where', {}).get('department') powinien zawierać 'Komunikacji'",
        ],
    },
    {
        "id": "Q06",
        "question": "Jak złożyć wniosek o dodatek mieszkaniowy?",
        "category": "HOW+WHERE",
        "difficulty": "medium",
        "description": "Usługa z Wydziału Świadczeń - testuje trafność retrieval dla specyficznej usługi.",
        "expected": {
            "department_keyword": "Świadczeń",
            "has_steps": True,
            "has_required_documents": True,
        },
        "expected_sources_keywords": ["dodatek", "mieszkaniow"],
        "tests": [
            "response.get('how', {}).get('steps') powinien być niepustą listą",
            "'świadczeń' lub 'mieszkaniow' powinien pojawić się w sources lub where.department (case insensitive)",
        ],
    },
    {
        "id": "Q07",
        "question": "Jak załatwić wypis z planu zagospodarowania przestrzennego?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "hard",
        "description": "Usługa z Wydziału Planowania - testuje retrieval mniej popularnej usługi.",
        "expected": {
            "department_keyword": "Planowania",
            "has_cost": True,
        },
        "expected_sources_keywords": ["Wypis", "wyrys", "Planu", "Planowania"],
        "tests": [
            "sources powinny zawierać coś o planowaniu przestrzennym",
            "response.get('how_much') powinien być niepusty",
        ],
    },
    {
        "id": "Q08",
        "question": "Chcę zarejestrować działalność gospodarczą. Gdzie w urzędzie to załatwię?",
        "category": "WHERE+HOW",
        "difficulty": "hard",
        "description": "Testuje edge-case: rejestracja działalności może nie być w BIP Lublin (robi się w CEIDG). Sprawdzamy jak RAG reaguje gdy nie ma idealnej odpowiedzi.",
        "expected": {
            "may_not_have_direct_answer": True,
            "possible_department": "Działalności Gospodarczej",
        },
        "expected_sources_keywords": ["działaln", "gospodar"],
        "tests": [
            "Odpowiedź powinna być sensowna - albo kierować do CEIDG, albo do odpowiedniego wydziału",
            "response.get('summary') powinien być niepusty i zawierać więcej niż 20 znaków",
        ],
    },
    {
        "id": "Q09",
        "question": "Jakie są godziny pracy Urzędu Stanu Cywilnego i jak zarejestrować urodzenie dziecka?",
        "category": "WHERE+HOW",
        "difficulty": "medium",
        "description": "Pytanie wieloaspektowe: lokalizacja + procedura. USC, Spokojna 2.",
        "expected": {
            "department": "Urząd Stanu Cywilnego",
            "address_fragment": "Spokojna 2",
            "has_hours": True,
        },
        "expected_sources_keywords": ["Stanu Cywilnego", "urodzen"],
        "tests": [
            "response.get('where', {}).get('department') powinien zawierać 'Stanu Cywilnego' lub 'USC'",
            "response.get('where', {}).get('address') powinien zawierać 'Spokojna'",
            "response.get('where', {}).get('hours') powinien być niepusty",
        ],
    },
    {
        "id": "Q10",
        "question": "Zgłoszenie sprzedaży samochodu - co muszę zrobić i ile mam czasu?",
        "category": "HOW+HOW_MUCH",
        "difficulty": "medium",
        "description": "Usługa 'Zgłoszenie zbycia pojazdu' - testuje synonim (sprzedaż vs zbycie) i ekstrakcję terminów.",
        "expected": {
            "department": "Wydział Komunikacji",
            "has_steps": True,
            "time_limit_keyword": "30 dni",
        },
        "expected_sources_keywords": ["zbyci", "pojazd"],
        "tests": [
            "response.get('where', {}).get('department') powinien zawierać 'Komunikacji'",
            "response.get('how', {}).get('steps') powinien być niepustą listą",
            "'30' powinien pojawić się w how_much.time_estimate lub summary (termin zgłoszenia)",
        ],
    },
]


def run_query(base_url: str, question: str) -> tuple[dict, float]:
    """Send query to RAG API and return response + elapsed time."""
    start = time.time()
    resp = requests.post(
        f"{base_url}/query",
        json={"question": question},
        timeout=120,
    )
    elapsed = time.time() - start
    resp.raise_for_status()
    return resp.json(), elapsed


def run_search(base_url: str, question: str) -> tuple[dict, float]:
    """Search-only (no LLM) to inspect retrieval quality."""
    start = time.time()
    resp = requests.post(
        f"{base_url}/search",
        json={"question": question, "top_k": 15},
        timeout=60,
    )
    elapsed = time.time() - start
    resp.raise_for_status()
    return resp.json(), elapsed


def evaluate_retrieval(search_results: dict, expected_keywords: list[str]) -> dict:
    """Evaluate retrieval quality by checking if expected keywords appear in results."""
    results = search_results.get("results", [])
    total = len(results)
    hits = []
    misses = []

    for kw in expected_keywords:
        found = False
        for r in results:
            content = r.get("content", "").lower()
            title = r.get("metadata", {}).get("title", "").lower()
            if kw.lower() in content or kw.lower() in title:
                found = True
                break
        if found:
            hits.append(kw)
        else:
            misses.append(kw)

    recall = len(hits) / len(expected_keywords) if expected_keywords else 0
    return {
        "total_chunks_retrieved": total,
        "expected_keywords": expected_keywords,
        "keywords_found": hits,
        "keywords_missing": misses,
        "keyword_recall": recall,
        "top_3_titles": [r.get("metadata", {}).get("title", "?") for r in results[:3]],
        "all_titles": [r.get("metadata", {}).get("title", "?") for r in results],
    }


def evaluate_generation(response: dict, question_config: dict) -> dict:
    """Evaluate the generated structured response against expected values."""
    expected = question_config["expected"]
    checks = []

    # JSON structure valid
    checks.append({
        "check": "valid_json_structure",
        "passed": isinstance(response.get("summary"), str) and len(response.get("summary", "")) > 0,
        "detail": f"summary length: {len(response.get('summary', ''))}",
    })

    # Check department
    if "department" in expected:
        where = response.get("where") or {}
        dept = (where.get("department") or "").lower()
        exp_dept = expected["department"].lower()
        passed = exp_dept in dept or any(w in dept for w in exp_dept.split())
        checks.append({
            "check": "correct_department",
            "passed": passed,
            "expected": expected["department"],
            "got": where.get("department"),
        })

    if "department_keyword" in expected:
        where = response.get("where") or {}
        dept = (where.get("department") or "").lower()
        summary = (response.get("summary") or "").lower()
        sources_text = " ".join(s.get("department", "") + s.get("title", "") for s in response.get("sources", [])).lower()
        kw = expected["department_keyword"].lower()
        passed = kw in dept or kw in summary or kw in sources_text
        checks.append({
            "check": "department_keyword_present",
            "passed": passed,
            "expected_keyword": expected["department_keyword"],
            "searched_in": f"where.department='{where.get('department')}', summary snippet, sources",
        })

    # Check address
    if "address_fragment" in expected:
        where = response.get("where") or {}
        addr = (where.get("address") or "").lower()
        exp_addr = expected["address_fragment"].lower()
        passed = exp_addr in addr
        checks.append({
            "check": "correct_address",
            "passed": passed,
            "expected_fragment": expected["address_fragment"],
            "got": where.get("address"),
        })

    # Check has_steps
    if expected.get("has_steps"):
        how = response.get("how") or {}
        steps = how.get("steps") or []
        passed = len(steps) > 0
        checks.append({
            "check": "has_steps",
            "passed": passed,
            "num_steps": len(steps),
            "steps_preview": steps[:3] if steps else [],
        })

    # Check has_cost
    if expected.get("has_cost"):
        how_much = response.get("how_much") or {}
        cost = how_much.get("cost") or ""
        passed = len(cost) > 0
        checks.append({
            "check": "has_cost",
            "passed": passed,
            "cost_value": cost,
        })

    # Check has_required_documents
    if expected.get("has_required_documents"):
        how = response.get("how") or {}
        docs = how.get("required_documents") or []
        passed = len(docs) > 0
        checks.append({
            "check": "has_required_documents",
            "passed": passed,
            "num_docs": len(docs),
            "docs_preview": docs[:3] if docs else [],
        })

    # Check who
    if "who_name" in expected:
        who = response.get("who") or {}
        name = (who.get("name") or "").lower()
        exp_name_parts = expected["who_name"].lower().split()
        passed = any(part in name for part in exp_name_parts)
        checks.append({
            "check": "correct_who_name",
            "passed": passed,
            "expected": expected["who_name"],
            "got": who.get("name"),
        })

    # Check booking
    if "booking" in expected:
        passed = response.get("booking") == expected["booking"]
        checks.append({
            "check": "booking_flag",
            "passed": passed,
            "expected": expected["booking"],
            "got": response.get("booking"),
        })

    # Check hours
    if expected.get("has_hours") or "hours_fragment" in expected:
        where = response.get("where") or {}
        hours = where.get("hours") or ""
        if "hours_fragment" in expected:
            passed = expected["hours_fragment"].lower() in hours.lower()
        else:
            passed = len(hours) > 0
        checks.append({
            "check": "has_hours",
            "passed": passed,
            "got": hours,
        })

    # Check time keyword
    if "time_limit_keyword" in expected:
        how_much = response.get("how_much") or {}
        time_est = (how_much.get("time_estimate") or "").lower()
        summary = (response.get("summary") or "").lower()
        kw = expected["time_limit_keyword"].lower()
        passed = kw in time_est or kw in summary
        checks.append({
            "check": "time_limit_keyword",
            "passed": passed,
            "expected_keyword": expected["time_limit_keyword"],
            "searched_in": f"time_estimate='{how_much.get('time_estimate')}', summary",
        })

    total_checks = len(checks)
    passed_checks = sum(1 for c in checks if c["passed"])
    score = passed_checks / total_checks if total_checks > 0 else 0

    return {
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "score": score,
        "checks": checks,
    }


def evaluate_response_structure(response: dict) -> dict:
    """Check structural completeness of the JSON response."""
    fields = {
        "summary": response.get("summary"),
        "where": response.get("where"),
        "how": response.get("how"),
        "how_much": response.get("how_much"),
        "who": response.get("who"),
        "booking": response.get("booking"),
        "sources": response.get("sources"),
    }
    non_null = {k: v for k, v in fields.items() if v is not None}
    return {
        "fields_present": list(non_null.keys()),
        "fields_null": [k for k, v in fields.items() if v is None],
        "num_sources": len(response.get("sources", [])),
        "has_suggestions": "suggestions" in response,
        "raw_fallback": response.get("raw_fallback", False),
    }


def run_benchmark(base_url: str):
    """Run the full benchmark suite."""
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(BENCHMARK_DIR, f"run_{timestamp}")
    os.makedirs(run_dir)

    print(f"\n{'='*70}")
    print(f"  BENCHMARK RAG BIP LUBLIN - {timestamp}")
    print(f"  Server: {base_url}")
    print(f"  Output: {run_dir}")
    print(f"{'='*70}\n")

    # Check server health
    try:
        health = requests.get(f"{base_url}/health", timeout=10).json()
        print(f"  Server status: {health.get('status')}")
        print(f"  Documents indexed: {health.get('documents')}")
        print(f"  BM25 ready: {health.get('bm25_ready')}")
        print(f"  Model: {health.get('model')}")
        print()
    except Exception as e:
        print(f"  ERROR: Cannot reach server at {base_url}: {e}")
        sys.exit(1)

    results = []
    total_retrieval_recall = 0
    total_generation_score = 0

    for i, q in enumerate(GOLDEN_QUESTIONS):
        print(f"  [{i+1}/10] {q['id']} ({q['difficulty']}) - {q['question'][:60]}...")

        result = {
            "id": q["id"],
            "question": q["question"],
            "category": q["category"],
            "difficulty": q["difficulty"],
            "description": q["description"],
        }

        # 1. Search-only (retrieval evaluation)
        try:
            search_resp, search_time = run_search(base_url, q["question"])
            retrieval_eval = evaluate_retrieval(search_resp, q["expected_sources_keywords"])
            result["retrieval"] = {
                "time_seconds": round(search_time, 3),
                **retrieval_eval,
            }
            total_retrieval_recall += retrieval_eval["keyword_recall"]
            recall_str = f"{retrieval_eval['keyword_recall']*100:.0f}%"
        except Exception as e:
            result["retrieval"] = {"error": str(e)}
            recall_str = "ERR"

        # 2. Full query (generation evaluation)
        try:
            query_resp, query_time = run_query(base_url, q["question"])
            generation_eval = evaluate_generation(query_resp, q)
            structure_eval = evaluate_response_structure(query_resp)
            result["generation"] = {
                "time_seconds": round(query_time, 3),
                "evaluation": generation_eval,
                "structure": structure_eval,
                "full_response": query_resp,
            }
            total_generation_score += generation_eval["score"]
            gen_str = f"{generation_eval['score']*100:.0f}%"
        except Exception as e:
            result["generation"] = {"error": str(e)}
            gen_str = "ERR"

        print(f"         Retrieval recall: {recall_str} | Generation score: {gen_str}")
        results.append(result)

    # Summary
    avg_retrieval = total_retrieval_recall / len(GOLDEN_QUESTIONS)
    avg_generation = total_generation_score / len(GOLDEN_QUESTIONS)

    summary = {
        "timestamp": timestamp,
        "server_url": base_url,
        "server_health": health,
        "num_questions": len(GOLDEN_QUESTIONS),
        "avg_retrieval_recall": round(avg_retrieval, 4),
        "avg_generation_score": round(avg_generation, 4),
        "per_question_summary": [
            {
                "id": r["id"],
                "question": r["question"][:80],
                "difficulty": r["difficulty"],
                "retrieval_recall": r.get("retrieval", {}).get("keyword_recall", 0),
                "retrieval_top3": r.get("retrieval", {}).get("top_3_titles", []),
                "generation_score": r.get("generation", {}).get("evaluation", {}).get("score", 0),
                "generation_checks_passed": r.get("generation", {}).get("evaluation", {}).get("passed_checks", 0),
                "generation_checks_total": r.get("generation", {}).get("evaluation", {}).get("total_checks", 0),
                "query_time_s": r.get("generation", {}).get("time_seconds", 0),
            }
            for r in results
        ],
    }

    # Write results
    full_log_path = os.path.join(run_dir, "full_results.json")
    with open(full_log_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    summary_path = os.path.join(run_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Failures log - most actionable for debugging
    failures = []
    for r in results:
        q_failures = []
        retrieval = r.get("retrieval", {})
        if retrieval.get("keywords_missing"):
            q_failures.append({
                "type": "retrieval_miss",
                "missing_keywords": retrieval["keywords_missing"],
                "top_titles_retrieved": retrieval.get("all_titles", [])[:5],
            })

        gen_eval = r.get("generation", {}).get("evaluation", {})
        for check in gen_eval.get("checks", []):
            if not check.get("passed"):
                q_failures.append({
                    "type": "generation_fail",
                    "check": check["check"],
                    "detail": {k: v for k, v in check.items() if k != "passed"},
                })

        if q_failures:
            failures.append({
                "id": r["id"],
                "question": r["question"],
                "difficulty": r["difficulty"],
                "failures": q_failures,
            })

    failures_path = os.path.join(run_dir, "failures.json")
    with open(failures_path, "w") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  Avg Retrieval Recall:    {avg_retrieval*100:.1f}%")
    print(f"  Avg Generation Score:    {avg_generation*100:.1f}%")
    print(f"  Questions with failures: {len(failures)}/{len(GOLDEN_QUESTIONS)}")
    print(f"\n  Per-question breakdown:")
    print(f"  {'ID':<5} {'Difficulty':<10} {'Retr%':<8} {'Gen%':<8} {'Time(s)':<8} Question")
    print(f"  {'-'*5} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*40}")
    for qs in summary["per_question_summary"]:
        print(f"  {qs['id']:<5} {qs['difficulty']:<10} {qs['retrieval_recall']*100:>5.0f}%  {qs['generation_score']*100:>5.0f}%  {qs['query_time_s']:>6.1f}s  {qs['question'][:40]}")

    print(f"\n  Failures detail:")
    if not failures:
        print("    None! All checks passed.")
    else:
        for f_item in failures:
            print(f"\n    {f_item['id']} - {f_item['question'][:60]}")
            for fail in f_item["failures"]:
                if fail["type"] == "retrieval_miss":
                    print(f"      [RETRIEVAL] Missing keywords: {fail['missing_keywords']}")
                    print(f"                  Retrieved titles: {fail['top_titles_retrieved'][:3]}")
                else:
                    print(f"      [GENERATION] Check '{fail['check']}' failed: {fail.get('detail', {})}")

    print(f"\n  Full logs saved to: {run_dir}/")
    print(f"    - full_results.json  (complete responses + evaluations)")
    print(f"    - summary.json       (aggregated metrics)")
    print(f"    - failures.json      (only failures - best for debugging)")
    print(f"{'='*70}\n")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark RAG BIP Lublin")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of RAG server")
    args = parser.parse_args()
    run_benchmark(args.url)
