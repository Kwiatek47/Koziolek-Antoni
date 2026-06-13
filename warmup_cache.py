#!/usr/bin/env python3
"""
Cache warmup - pre-fills the response cache with top 20 most common questions.
Run after backend restart + indexing to get instant responses for popular queries.

Usage: python warmup_cache.py [backend_url]
"""
import sys
import time
import json
import requests

BACKEND_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

TOP_QUESTIONS = [
    # Dowody osobiste
    "Jak wyrobić dowód osobisty?",
    "Ile kosztuje wyrobienie dowodu osobistego?",
    "Ile się czeka na dowód osobisty?",
    "Zgubiony dowód osobisty co robić?",
    # Rejestracja pojazdów
    "Gdzie zarejestrować samochód?",
    "Ile kosztuje rejestracja samochodu?",
    "Przerejestrowanie auta z innego miasta",
    # Meldunek
    "Jak zameldować się w Lublinie?",
    "Meldunek czasowy – procedura",
    # Prawo jazdy
    "Jak wymienić prawo jazdy?",
    "Ile kosztuje wymiana prawa jazdy?",
    # Ślub / USC
    "Ile kosztuje ślub cywilny?",
    "Jak wziąć ślub cywilny w Lublinie?",
    # Inne popularne
    "Kto jest prezydentem Lublina?",
    "Pozwolenie na budowę",
    "Jak uzyskać pozwolenie na budowę?",
    "Jak złożyć wniosek o becikowe?",
    "Warunki zabudowy – procedura",
    "Gdzie zapłacić opłatę skarbową?",
    "Jak założyć działalność gospodarczą?",
]


def warmup():
    print(f"Cache warmup: {BACKEND_URL}")
    print(f"Questions: {len(TOP_QUESTIONS)}")
    print()

    # Check health first
    try:
        health = requests.get(f"{BACKEND_URL}/health", timeout=5).json()
        print(f"Backend: {health['status']} | Docs: {health['documents']} | Cache: {health['cache']['size']}/{health['cache']['max_size']}")
    except Exception as e:
        print(f"ERROR: Backend unavailable - {e}")
        sys.exit(1)

    print()
    success = 0
    total_time = 0

    for i, question in enumerate(TOP_QUESTIONS, 1):
        try:
            start = time.time()
            resp = requests.post(
                f"{BACKEND_URL}/query",
                json={"question": question},
                timeout=120,
            )
            elapsed = time.time() - start
            total_time += elapsed

            if resp.status_code == 200:
                data = resp.json()
                intent = data.get("intent", "procedure")
                summary = (data.get("summary") or "")[:60]
                print(f"  [{i:2d}/{len(TOP_QUESTIONS)}] {elapsed:5.1f}s | {intent:13s} | {question[:45]}")
                print(f"         -> {summary}...")
                success += 1
            else:
                print(f"  [{i:2d}/{len(TOP_QUESTIONS)}] ERROR {resp.status_code}: {question[:45]}")
        except Exception as e:
            print(f"  [{i:2d}/{len(TOP_QUESTIONS)}] TIMEOUT/ERROR: {question[:45]} - {e}")

    print()
    print(f"Done! {success}/{len(TOP_QUESTIONS)} cached in {total_time:.0f}s (avg {total_time/max(success,1):.1f}s/query)")

    # Show final cache stats
    try:
        health = requests.get(f"{BACKEND_URL}/health", timeout=5).json()
        print(f"Cache: {health['cache']['size']}/{health['cache']['max_size']}")
    except Exception:
        pass


if __name__ == "__main__":
    warmup()
