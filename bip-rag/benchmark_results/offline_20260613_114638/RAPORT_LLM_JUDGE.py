#!/usr/bin/env python3
"""
RAPORT BENCHMARK - LLM-as-a-Judge
Automatyczna analiza wyników offline benchmarku + rekomendacje.

Wygenerowany: 2026-06-13
"""

RAPORT = """
╔══════════════════════════════════════════════════════════════════════════╗
║          BENCHMARK RAG BIP LUBLIN — RAPORT LLM-as-a-Judge             ║
║          Data: 2026-06-13 | Dokumentów: 9009 | Pytań: 10              ║
╚══════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. WYNIKI OGÓLNE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Metryka                    Wynik       Cel       Status
  ─────────────────────────  ─────────   ────────  ────────
  Title Hit Rate (top-6)     60% (6/10)  > 80%     ❌ FAIL
  Department Hit Rate        80% (8/10)  > 90%     ⚠️  WARN
  Avg Content Recall         51.7%       > 70%     ❌ FAIL
  Avg Search Time (BM25)     ~37ms       < 100ms   ✅ OK

  OCENA OGÓLNA: Retrieval wymaga poprawy. BM25 sam nie radzi sobie
  z polską deklinacją. Dense search (embeddings) poprawi to znacząco,
  ale trzeba też poprawić dane i chunking.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. ANALIZA PER-PYTANIE (zweryfikowana z BIP.lublin.eu)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────┐
│ Q01: "Jak wyrobić dowód osobisty w Lublinie?" [EASY] — ❌ FAIL     │
├─────────────────────────────────────────────────────────────────────┤
│ Problem: BM25 NIE TRAFIA na właściwy dokument (rank: 9/15!)        │
│                                                                     │
│ Root cause:                                                         │
│   • "wyrobić" nie istnieje w danych (dane używają "wydanie")       │
│   • "dowód" (mianownik) ≠ "dowodu" (dopełniacz w tekście)         │
│   • "osobisty" ≠ "osobistego" (odmiana przymiotnika)               │
│   • Polska deklinacja sprawia, że BM25 nie matchuje tokenów!       │
│                                                                     │
│ Zweryfikowana prawda (BIP + gov.pl):                                │
│   Wydział Spraw Administracyjnych, ul. Spokojna 2, p. 220          │
│   Bezpłatne. Termin: 30 dni. Od 29.12.2023 nie składa się         │
│   papierowego wniosku - generowany automatycznie.                  │
│   Od 01.01.2026: e-Doręczenia wymagane dla komunikacji online.     │
│                                                                     │
│ FIX potrzebny:                                                      │
│   1. Stemming/lemmatyzacja dla BM25 (dowodu→dowód, osobistego→...)│
│   2. Dense search (embeddingi) rozwiąże to naturalnie              │
│   3. Synonimy w chunkach: "wyrobić = wydanie = złożenie wniosku"  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q02: "Ile kosztuje rejestracja samochodu z zagranicy?" [MED] — ✅   │
├─────────────────────────────────────────────────────────────────────┤
│ Retrieval: OK! Trafia na "Rejestracja pojazdu z zagranicy" (KM)    │
│ Title HIT, Dept HIT, Content 100%                                   │
│                                                                     │
│ Zweryfikowana prawda: Wydział Komunikacji, Czechowska 19A.          │
│ Opłaty: 256.50 zł (tablice 80zł + dowód rej 54zł + nalepka 18.50  │
│ + opłata ewidencyjna 2zł × 2 + karta pojazdu 75zł + pozwolenie    │
│ czasowe 18.50zł + tabl. tymcz. 30zł). Status: OK.                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q03: "Kto jest prezydentem Lublina?" [EASY] — ❌ FAIL              │
├─────────────────────────────────────────────────────────────────────┤
│ Problem: Retrieval nie trafia na dane o prezydencie                 │
│                                                                     │
│ Root cause:                                                         │
│   • Chunk z prezydent.txt ma typ "osoba" - tytuł to                │
│     "Prezydent Miasta Lublin" ale słowo "Lublina" i "kto"         │
│     mają niski IDF (występują w wielu dokumentach)                 │
│   • "prezydentem" (narzędnik) ≠ "prezydent" (mianownik w tytule) │
│   • BM25 rankit Forum Kobiet Lublina (bo "Lublina")!              │
│                                                                     │
│ Zweryfikowana prawda: Krzysztof Żuk, od 2010 r.                    │
│   Plac Króla Władysława Łokietka 1, 20-109 Lublin.                │
│                                                                     │
│ FIX potrzebny:                                                      │
│   1. Lemmatyzacja: prezydentem → prezydent                         │
│   2. Entity-aware retrieval: pytania typu "kto jest X"             │
│      powinny priorytetyzować dokumenty typu "osoba"                │
│   3. Dense search znacząco pomoże (semantyczne podobieństwo)       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q04: "Gdzie jest Biuro Rzeczy Znalezionych...?" [EASY] — ✅        │
├─────────────────────────────────────────────────────────────────────┤
│ Retrieval: IDEALNY. Bezpośredni match tytułu.                      │
│ Title HIT, Dept HIT, Content 100%                                   │
│                                                                     │
│ Zweryfikowane: Dolna 3-Maja 5, pok. 3, pon-pt 7:30-15:30.         │
│ Status: Pełna zgodność.                                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q05: "Dokumenty do wymiany prawa jazdy po zmianie nazwiska" [MED]  │
│ — ⚠️ PARTIAL                                                        │
├─────────────────────────────────────────────────────────────────────┤
│ Title HIT, Dept HIT, ale Content recall tylko 50%                   │
│ Missing: "zdjęcie", "100" (opłata) - nie w top-6 chunkach          │
│                                                                     │
│ Root cause: Chunk z opłatą/zdjęciem jest w innym kawałku            │
│ dokumentu (chunking rozdzielił wymagania od opłat)                  │
│                                                                     │
│ Zweryfikowane (BIP): Usługa KM-024. Wydział Komunikacji.           │
│ Dokumenty: wniosek, zdjęcie 35×45mm, prawo jazdy, dowód.          │
│ Opłata: 100 zł + 0.50 zł opłata ewidencyjna.                      │
│                                                                     │
│ FIX: Zwiększyć chunk overlap lub zmniejszyć chunk size tak,        │
│ żeby opłata + wymagane dokumenty były w jednym chunku.             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q06: "Jak złożyć wniosek o dodatek mieszkaniowy?" [MED] — ✅       │
├─────────────────────────────────────────────────────────────────────┤
│ Retrieval: OK. Title HIT, Dept HIT, Content 100%.                   │
│ Zweryfikowane: Wydział Świadczeń, kryterium dochodowe/metrażowe.   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q07: "Wypis z planu zagospodarowania przestrzennego" [HARD]        │
│ — ⚠️ PARTIAL                                                        │
├─────────────────────────────────────────────────────────────────────┤
│ Title HIT, Dept HIT, ale Content recall 33%                         │
│ Missing: "opłata", "skarbowa" - opłaty w innym chunku              │
│                                                                     │
│ Zweryfikowane: Wydział Planowania. Opłata skarbowa:                 │
│ 30 zł za wypis ≤5 stron, 50 zł >5 stron.                          │
│ Wyrys 20 zł/stronę A4.                                            │
│                                                                     │
│ FIX: Dane o opłatach powinny być lepiej zachowane w chunkach.      │
│ Chunking 1500 znaków może rozdzielać "wymagane opłaty" od         │
│ nagłówka usługi.                                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q08: "Rejestracja działalności gospodarczej" [HARD] — ❌ FAIL      │
├─────────────────────────────────────────────────────────────────────┤
│ Problem: Retrieval kompletnie nie trafia! Zwraca odpady, pożary.   │
│                                                                     │
│ Root cause:                                                         │
│   • "zarejestrować" matchuje "rejestracja/rejestrację" - ale       │
│     BM25 nie łączy tych form                                       │
│   • "działalność gospodarczą" to fraza wielowyrazowa -             │
│     BM25 traktuje każdy token osobno                               │
│   • Wiele dokumentów zawiera tekst o CEIDG (w sekcji "informacje  │
│     dodatkowe") ale token "gospodarczą" ≠ "gospodarczej"          │
│                                                                     │
│ Zweryfikowane (BIP lublin.eu):                                      │
│   Usługa SA-090 w Wydziale Spraw Administracyjnych!                │
│   (NIE Wydział Działalności Gospodarczej - taki nie istnieje!)     │
│   Spokojna 2, pok. 253, II piętro.                                │
│   Bezpłatne. Przez biznes.gov.pl lub osobiście w urzędzie.        │
│                                                                     │
│ FIX:                                                                │
│   1. POPRAWIĆ ground truth w benchmarku: dept = Wyd. Spraw Admin. │
│   2. Lemmatyzacja BM25 (zarejestrować→rejestr, gospodarczą→gosp.) │
│   3. Dense search                                                   │
│   4. Department profile dla SA powinien zawierać "CEIDG",          │
│      "działalność gospodarcza", "firma"                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q09: "Godziny USC + rejestracja urodzenia" [MED] — ⚠️ PARTIAL     │
├─────────────────────────────────────────────────────────────────────┤
│ Dept HIT (Urząd Stanu Cywilnego), ale Title MISS i Content 33%     │
│ Trafia na "Zmiana imienia dziecka" i "Rejestracja dziecka" ale    │
│ godziny pracy nie są w top-6                                       │
│                                                                     │
│ Root cause: "godziny pracy" + "Urzędu Stanu Cywilnego" - BM25     │
│ nie rozumie że pytanie o godziny dotyczy USC jako instytucji       │
│                                                                     │
│ Zweryfikowane: USC, Spokojna 2, II piętro, pok. 262.              │
│ Godziny: pon-pt 7:45-15:15.                                       │
│ Rejestracja urodzenia: w ciągu 21 dni od urodzenia.               │
│                                                                     │
│ FIX: Department profiles powinny zawierać godziny pracy            │
│ + adres + główne usługi (są ale bez godzin).                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Q10: "Zgłoszenie sprzedaży samochodu" [MED] — ⚠️ PARTIAL          │
├─────────────────────────────────────────────────────────────────────┤
│ Title HIT (matchuje "zbyci" w "Zgłoszenie zbycia pojazdu")         │
│ Dept HIT, ale Content 33% - missing "30 dni" i "zawiadomieni"     │
│                                                                     │
│ Root cause: Synonim "sprzedaż" ≠ "zbycie" w BIP. Termin "30 dni" │
│ jest w chunku ale tokenizerowi umyka.                               │
│                                                                     │
│ Zweryfikowane (BIP): Zgłoszenie zbycia pojazdu (KM-049).          │
│ Czechowska 19A, pok. 23 (I piętro). Termin: 30 dni.              │
│ Kara za spóźnienie: 250 zł. Bezpłatne.                           │
│                                                                     │
│ FIX: Synonimy w chunkach ("sprzedaż/zbycie/darowizna pojazdu")   │
└─────────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. DIAGNOZA KLUCZOWYCH PROBLEMÓW (posortowane wg wpływu)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#1 🔴 BRAK LEMMATYZACJI W BM25 (wpływ: 4/10 pytań)
   Polska deklinacja zabija BM25:
   • "dowód" ≠ "dowodu" ≠ "dowodem" ≠ "dowodów"
   • "wyrobić" ≠ "wydanie" ≠ "złożenie"  
   • "osobisty" ≠ "osobistego" ≠ "osobistym"
   • "prezydentem" ≠ "prezydent" ≠ "prezydenta"
   
   ROZWIĄZANIE: Użyć polskiego stemmera (Stempel/Morfologik) w tokenize_pl()
   lub przynajmniej obcinać końcówki (-ów, -em, -ego, -ej, -emu, -ach, -ami)

#2 🔴 DENSE SEARCH NIE DZIAŁA BEZ MODELU (wpływ: WSZYSTKIE pytania)
   Hybrydowy search (Dense + BM25 + RRF) jest zaimplementowany
   w app.py, ale lokalnie nie ma zainstalowanego embedding modelu.
   Dense search rozwiąże ~80% problemów z deklinacją.
   
   ROZWIĄZANIE: Zapewnić że na serwerze działa embedding model.
   Benchmark powinien testować też na serwerze (nie tylko offline BM25).

#3 🟡 CHUNKING ROZDZIELA POWIĄZANE INFORMACJE (wpływ: 3/10)
   Chunk 1500 znaków często odcina opłaty od opisu usługi.
   Wynik: LLM dostaje kontekst "co zrobić" ale bez "ile kosztuje".
   
   ROZWIĄZANIE: 
   • Zmniejszyć chunk size do ~1000 znaków z overlap 300
   • LUB dodać "header propagation" - każdy chunk dostaje nagłówek
     z tytułem, wydziałem, adresem I opłatami

#4 🟡 BRAK SYNONIMÓW W DANYCH (wpływ: 2/10)
   Mieszkaniec mówi "wyrobić dowód" ale BIP pisze "wydanie dowodu".
   "sprzedaż samochodu" vs "zbycie pojazdu".
   "firma" vs "działalność gospodarcza".
   
   ROZWIĄZANIE:
   • Dodać do prefixu każdego chunku synonimy potoczne
   • Np. "Usługa: Wydanie dowodu osobistego (wyrobienie dowodu)"
   • "Zgłoszenie zbycia pojazdu (sprzedaż samochodu, darowizna)"

#5 🟡 DEPARTMENT PROFILES BEZ GODZIN I ADRESÓW (wpływ: 1/10)
   departments.json nie zawiera godzin pracy - a to częste pytanie.
   
   ROZWIĄZANIE: Wzbogacić profiles o godziny pracy, telefon, adres.

#6 🟢 SYSTEM PROMPT - DROBNE POPRAWKI
   Aktualny prompt jest solidny ale:
   • Brak obsługi sytuacji "nie mam informacji na ten temat"
   • Brak instrukcji dla pytań ogólnych (kto jest prezydentem)
   
   ROZWIĄZANIE: Dodać fallback behavior w prompcie.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. PLAN USPRAWNIEŃ (priorytet × wpływ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Prio  Co                             Wpływ    Trudność   ETA
  ────  ──────────────────────────────  ──────  ─────────  ────
  P0    Dodać lemmatyzację do BM25     +20%     Mała       1h
  P1    Dodać synonimy do chunków     +15%     Mała       2h
  P2    Poprawić chunking (overlap)    +10%     Średnia    3h  
  P3    Wzbogacić dept profiles        +5%      Mała       1h
  P4    Poprawić system prompt         +5%      Mała       30m
  P5    Test z dense search na serw.   +30%     Duża       Setup

  OCZEKIWANY WYNIK PO FIXACH P0-P4:
  Title Hit Rate:     60% → 90%+
  Content Recall:     52% → 75%+
  (z Dense search P5: 85%+)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. POPRAWKI DO BENCHMARKU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Q08: Poprawić expected_department z "Wydział Działalności Gospodarczej"
       na "Wydział Spraw Administracyjnych" (weryfikacja web potwierdza
       że rejestracja CEIDG to usługa SA-090 w WSA).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. SZYBKOŚĆ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  BM25 search: 26-65ms per query (OK)
  Budowa indeksu: 0.3s dla 9009 docs (OK)
  
  Bottleneck będzie LLM (Qwen 2.5 3B):
  • Na CPU: ~5-15s per query (słabo dla UX)
  • Na GPU: ~1-3s per query (akceptowalne)
  
  REKOMENDACJA: Rozważyć:
  • Streaming response (SSE) żeby user widział odpowiedź rosnącą
  • Cache dla popularnych pytań (dowód, rejestracja, meldunek)
  • Mniejszy model jeśli GPU nie dostępne

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

if __name__ == "__main__":
    print(RAPORT)
