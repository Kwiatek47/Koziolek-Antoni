#!/usr/bin/env python3
"""
Przygotowanie datasetu RAG z danych BIP Lublin.
Tworzy ujednolicone dokumenty z metadanymi do indeksowania.
"""
import json
import os
import re
import subprocess
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "dane_bip")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data", "documents.json")

def extract_pdf_text(pdf_path):
    """Extract text from PDF using pymupdf (best), pdftotext, or PyPDF2 fallback."""
    # Method 1: PyMuPDF (fitz) - no system deps, best quality
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        text = []
        for page in doc:
            text.append(page.get_text())
        doc.close()
        result = "\n".join(text).strip()
        if result:
            return result
    except ImportError:
        pass
    except Exception as e:
        print(f"    [pymupdf error] {os.path.basename(pdf_path)}: {e}")

    # Method 2: pdftotext (requires poppler-utils)
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Method 3: PyPDF2 (pure Python fallback)
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = []
            for page in reader.pages:
                text.append(page.extract_text() or "")
            return "\n".join(text).strip()
    except ImportError:
        pass
    except Exception as e:
        print(f"    [PyPDF2 error] {os.path.basename(pdf_path)}: {e}")

    return ""


def chunk_text(text, max_chars=1000, overlap=300):
    """Split text into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            for sep in ['\n\n', '\n', '. ', ', ']:
                last_sep = text.rfind(sep, start + max_chars // 2, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


SYNONYMS = {
    "Wydanie dowodu osobistego": "wyrobienie dowodu, nowy dowód, wymiana dowodu, jak wyrobić dowód, wyrobienie dowodu osobistego, zdjęcie do dowodu, wniosek o dowód",
    "Zgłoszenie zbycia pojazdu": "sprzedaż samochodu, sprzedaż auta, zgłoszenie sprzedaży pojazdu, sprzedałem samochód, ile czasu na zgłoszenie sprzedaży, 30 dni na zgłoszenie",
    "Rejestracja działalności gospodarczej (wpis do CEIDG)": "założenie firmy, wpis CEIDG, otwarcie działalności, zarejestrować firmę",
    "Rejestracja pojazdu z zagranicy": "rejestracja samochodu z importu, auto z zagranicy, sprowadzenie auta",
    "Wypis i wyrys z Miejscowego Planu Zagospodarowania Przestrzennego lub Studium Uwarunkowań i Kierunków Zagospodarowania Przestrzennego": "plan zagospodarowania, MPZP, wypis z planu, wyrys z planu",
    "Wymiana prawa jazdy z powodu zmiany danych": "wymiana prawka, nowe prawo jazdy po zmianie nazwiska, zmiana danych w prawie jazdy",
    "Wymiana prawa jazdy z powodu upływu terminu ważności": "przedłużenie prawa jazdy, odnowienie prawka",
    "Rejestracja nowego pojazdu": "rejestracja nowego samochodu, rejestracja nowego auta",
    "Rejestracja pojazdu zarejestrowanego na terenie RP": "przerejestrowanie samochodu, przerejestrowanie auta",
    "Wydanie międzynarodowego prawa jazdy": "międzynarodowe prawo jazdy, prawko za granicę",
    "Profil kandydata na kierowcę": "prawo jazdy po raz pierwszy, kurs na prawo jazdy, PKK",
    "Dodatki mieszkaniowe": "dopłata do czynszu, dofinansowanie mieszkania, dodatek na mieszkanie",
    "Ustalenie warunków zabudowy": "warunki zabudowy, WZ, decyzja o warunkach zabudowy",
    "Zameldowanie na pobyt stały": "meldunek stały, zameldować się na stałe",
    "Zameldowanie na pobyt czasowy": "meldunek czasowy, zameldować się tymczasowo",
    "Wymeldowanie z pobytu stałego": "wymeldowanie, wypisanie z meldunku",
    "Biuro Rzeczy Znalezionych": "rzeczy zgubione, znalezione przedmioty, zgubiony portfel",
    "Zasiłek rodzinny i dodatki do zasiłku rodzinnego": "zasiłek na dziecko, świadczenia rodzinne",
    "Jednorazowa zapomoga z tytułu urodzenia się dziecka": "becikowe, ile kosztuje becikowe, gdzie złożyć wniosek o becikowe, zapomoga na dziecko, świadczenie za urodzenie, 1000 zł na dziecko",
    "Zgłoszenie utraty lub uszkodzenia dowodu osobistego": "zgubiony dowód, utrata dowodu, zniszczony dowód",
}


def get_synonyms_for_title(title: str) -> str:
    """Find matching synonyms for a service title."""
    for key, synonyms in SYNONYMS.items():
        if key.lower() in title.lower() or title.lower() in key.lower():
            return synonyms
    return ""


def process_uslugi():
    """Process service cards into RAG documents."""
    docs = []
    filepath = os.path.join(DATA_DIR, "uslugi.json")
    if not os.path.exists(filepath):
        return docs

    with open(filepath) as f:
        services = json.load(f)

    for svc in services:
        url = svc.get("url", "")
        title = svc.get("title", "")
        sections = svc.get("sections", {})
        department = sections.get("Komórka organizacyjna załatwiająca sprawę", "")
        card_number = sections.get("Numer karty informacyjnej", "")

        address_raw = sections.get("Sposób i miejsce składania dokumentów", "")
        address_short = address_raw[:100].split('\n')[0] if address_raw else ""
        cost_raw = sections.get("Wymagane opłaty", "Brak")
        cost_short = cost_raw[:80].split('\n')[0] if cost_raw else "Brak"

        synonyms = get_synonyms_for_title(title)
        synonym_line = f"Szukaj też: {synonyms}\n" if synonyms else ""

        prefix = (
            f"Usługa: {title}\n"
            f"Wydział: {department}\n"
            f"Numer karty: {card_number}\n"
            f"Adres: {address_short}\n"
            f"Opłata: {cost_short}\n"
            f"{synonym_line}\n"
        )

        content_parts = [f"# {title}\n"]
        for sec_name, sec_content in sections.items():
            content_parts.append(f"## {sec_name}\n{sec_content}\n")

        full_content = "\n".join(content_parts)

        metadata = {
            "source_url": url,
            "title": title,
            "type": "usluga",
            "category": sections.get("Kategoria sprawy", ""),
            "department": department,
            "card_number": card_number,
        }

        # Create a compact summary chunk with all key info in one place
        key_sections = [
            ("Sposób i miejsce składania dokumentów", "GDZIE I JAK ZŁOŻYĆ"),
            ("Wymagane załączniki", "WYMAGANE DOKUMENTY"),
            ("Wymagane wnioski", "FORMULARZE"),
            ("Dokumenty do wglądu", "DOKUMENTY DO WGLĄDU"),
            ("Wymagane opłaty", "OPŁATY"),
            ("Termin załatwienia sprawy", "CZAS ZAŁATWIENIA"),
            ("Podstawa prawna", "PODSTAWA PRAWNA"),
        ]
        summary_parts = [f"# {title}", f"Wydział: {department}", f"Karta: {card_number}", ""]
        for sec_key, label in key_sections:
            val = sections.get(sec_key, "")
            if val:
                summary_parts.append(f"{label}: {val[:400]}")
        compact_summary = "\n".join(summary_parts)

        # Always add the compact summary as first chunk (no splitting)
        docs.append({
            "id": f"usluga_{card_number}_summary" if card_number else f"usluga_{title.replace(' ', '_')[:50]}_summary",
            "content": prefix + compact_summary,
            "metadata": metadata,
        })

        # Then add detailed chunks for full content
        chunks = chunk_text(full_content)
        for i, chunk in enumerate(chunks):
            docs.append({
                "id": f"usluga_{card_number}_{i}" if card_number else f"usluga_{svc.get('title', '').replace(' ', '_')[:50]}_{i}",
                "content": prefix + chunk,
                "metadata": metadata,
            })

    return docs


def process_struktura():
    """Process organizational structure into RAG documents."""
    docs = []
    filepath = os.path.join(DATA_DIR, "struktura_organizacyjna_full.json")
    if not os.path.exists(filepath):
        return docs

    with open(filepath) as f:
        entries = json.load(f)

    for entry in entries:
        url = entry.get("url", "")
        title = entry.get("title", "")
        content = entry.get("content", "")

        if not content:
            continue

        metadata = {
            "source_url": url,
            "title": title,
            "type": "struktura_organizacyjna",
        }

        chunks = chunk_text(f"# {title}\n\n{content}")
        for i, chunk in enumerate(chunks):
            docs.append({
                "id": f"struktura_{title.replace(' ', '_')[:50]}_{i}",
                "content": chunk,
                "metadata": metadata,
            })

    return docs


def process_organy():
    """Process advisory bodies into RAG documents."""
    docs = []
    filepath = os.path.join(DATA_DIR, "organy_doradcze_full.json")
    if not os.path.exists(filepath):
        return docs

    with open(filepath) as f:
        entries = json.load(f)

    for entry in entries:
        url = entry.get("url", "")
        title = entry.get("title", "")
        content = entry.get("content", "")

        if not content:
            continue

        metadata = {
            "source_url": url,
            "title": title,
            "type": "organ_doradczy",
        }

        chunks = chunk_text(f"# {title}\n\n{content}")
        for i, chunk in enumerate(chunks):
            docs.append({
                "id": f"organ_{title.replace(' ', '_')[:50]}_{i}",
                "content": chunk,
                "metadata": metadata,
            })

    return docs


def process_osoby():
    """Process president, deputies, proxies."""
    docs = []

    files_config = [
        ("prezydent.txt", "Prezydent Miasta Lublin", "osoba",
         "https://bip.lublin.eu/prezydent-zastepcy-pelnomocnicy/prezydent/krzysztof-zuk-prezydent-miasta-lublin,1,14981,2.html"),
        ("pelnomocnicy.txt", "Pełnomocnicy Prezydenta Miasta Lublin", "osoba",
         "https://bip.lublin.eu/prezydent-zastepcy-pelnomocnicy/pelnomocnicy/pelnomocnicy-prezydenta-miasta-lublin,1,14983,2.html"),
        ("zastepcy_prezydenta.txt", "Zastępcy Prezydenta Miasta Lublin", "osoba",
         "https://bip.lublin.eu/prezydent-zastepcy-pelnomocnicy/zastepcy-prezydenta/"),
    ]

    osoby_synonyms = {
        "prezydent.txt": "Kto jest prezydentem Lublina? Kto rządzi miastem? Prezydent Krzysztof Żuk.",
        "pelnomocnicy.txt": "Kto jest pełnomocnikiem prezydenta? Pełnomocnicy miasta Lublin.",
        "zastepcy_prezydenta.txt": "Kto jest zastępcą prezydenta? Wiceprezydent Lublina.",
    }

    for filename, title, doc_type, url in files_config:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath) as f:
            content = f.read().strip()

        prefix = f"# {title}\nSzukaj też: {osoby_synonyms.get(filename, '')}\n\n"

        metadata = {
            "source_url": url,
            "title": title,
            "type": doc_type,
        }

        chunks = chunk_text(prefix + content)
        for i, chunk in enumerate(chunks):
            docs.append({
                "id": f"osoba_{filename.replace('.txt', '')}_{i}",
                "content": chunk,
                "metadata": metadata,
            })

    return docs


def process_pdfs():
    """Extract text from PDFs and create documents."""
    docs = []

    pdf_dirs = [
        os.path.join(DATA_DIR, "pdf"),
        os.path.join(DATA_DIR, "pdf_uslugi"),
    ]

    # Build a mapping from PDF filename to source URL
    pdf_url_map = {}
    uslugi_path = os.path.join(DATA_DIR, "uslugi.json")
    if os.path.exists(uslugi_path):
        with open(uslugi_path) as f:
            services = json.load(f)
        for svc in services:
            for att in svc.get("attachments", []):
                fname = att["url"].split("/")[-1][:120]
                pdf_url_map[fname] = {
                    "pdf_url": att["url"],
                    "service_url": svc.get("url", ""),
                    "service_title": svc.get("title", ""),
                }

    total_found = 0
    total_extracted = 0
    errors = []

    for pdf_dir in pdf_dirs:
        if not os.path.exists(pdf_dir):
            print(f"    [!] PDF dir not found: {pdf_dir}")
            continue
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        print(f"    Found {len(pdf_files)} PDFs in {os.path.basename(pdf_dir)}/")
        total_found += len(pdf_files)

        for filename in pdf_files:
            filepath = os.path.join(pdf_dir, filename)
            text = extract_pdf_text(filepath)
            if not text or len(text) < 50:
                errors.append(f"      SKIP (empty/too short): {filename} ({len(text) if text else 0} chars)")
                continue

            total_extracted += 1
            info = pdf_url_map.get(filename, {})
            metadata = {
                "source_url": info.get("pdf_url", ""),
                "parent_url": info.get("service_url", ""),
                "title": info.get("service_title", filename),
                "type": "pdf_attachment",
                "filename": filename,
            }

            chunks = chunk_text(f"# Załącznik: {filename}\n\n{text}")
            for i, chunk in enumerate(chunks):
                docs.append({
                    "id": f"pdf_{filename.replace('.pdf', '').replace(' ', '_')[:50]}_{i}",
                    "content": chunk,
                    "metadata": metadata,
                })

    if errors:
        for e in errors[:5]:
            print(e)
        if len(errors) > 5:
            print(f"      ... and {len(errors) - 5} more")

    print(f"    Extracted text from {total_extracted}/{total_found} PDFs")
    return docs


def process_departments():
    """Load pre-generated department profile documents."""
    dept_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "departments.json")
    if not os.path.exists(dept_file):
        # Try generating them
        try:
            from generate_departments import generate_department_docs
            return generate_department_docs() or []
        except Exception:
            return []
    with open(dept_file) as f:
        return json.load(f)


def main():
    print("Preparing RAG dataset from BIP Lublin data...")
    print(f"  Data dir: {os.path.abspath(DATA_DIR)}")

    # PDF extractor diagnostics
    try:
        import fitz
        print(f"  PDF extractor: PyMuPDF {fitz.version[0]} (fitz)")
    except ImportError:
        try:
            import PyPDF2
            print(f"  PDF extractor: PyPDF2 {PyPDF2.__version__} (fallback)")
        except ImportError:
            print("  [WARNING] No PDF library available! Install: pip install pymupdf")

    all_docs = []

    print("  Processing usługi...")
    all_docs.extend(process_uslugi())
    print(f"    -> {len(all_docs)} chunks")

    print("  Processing department profiles...")
    prev = len(all_docs)
    all_docs.extend(process_departments())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing struktura organizacyjna...")
    prev = len(all_docs)
    all_docs.extend(process_struktura())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing organy doradcze...")
    prev = len(all_docs)
    all_docs.extend(process_organy())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing osoby (prezydent, zastępcy, pełnomocnicy)...")
    prev = len(all_docs)
    all_docs.extend(process_osoby())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing PDFs...")
    prev = len(all_docs)
    all_docs.extend(process_pdfs())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing wiedza bazowa...")
    prev = len(all_docs)
    try:
        from prepare_knowledge import process_knowledge
        all_docs.extend(process_knowledge())
    except Exception as e:
        print(f"    WARNING: wiedza bazowa skipped: {e}")
    print(f"    -> {len(all_docs) - prev} chunks")

    print(f"\nTotal documents/chunks: {len(all_docs)}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"Saved to {OUTPUT_FILE} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    main()
