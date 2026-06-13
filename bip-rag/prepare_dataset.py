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
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "documents.json")

def extract_pdf_text(pdf_path):
    """Extract text from PDF using pdftotext or python fallback."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = []
            for page in reader.pages:
                text.append(page.extract_text() or "")
            return "\n".join(text).strip()
    except Exception:
        pass

    return ""


def chunk_text(text, max_chars=1500, overlap=200):
    """Split text into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        # Try to break at paragraph or sentence boundary
        if end < len(text):
            for sep in ['\n\n', '\n', '. ', ', ']:
                last_sep = text.rfind(sep, start + max_chars // 2, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


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

        # Build a clean document from sections
        content_parts = [f"# {title}\n"]
        for sec_name, sec_content in sections.items():
            content_parts.append(f"## {sec_name}\n{sec_content}\n")

        full_content = "\n".join(content_parts)

        metadata = {
            "source_url": url,
            "title": title,
            "type": "usluga",
            "category": sections.get("Kategoria sprawy", ""),
            "department": sections.get("Komórka organizacyjna załatwiająca sprawę", ""),
            "card_number": sections.get("Numer karty informacyjnej", ""),
        }

        chunks = chunk_text(full_content)
        for i, chunk in enumerate(chunks):
            docs.append({
                "id": f"usluga_{svc.get('title', '').replace(' ', '_')[:50]}_{i}",
                "content": chunk,
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

    for filename, title, doc_type, url in files_config:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath) as f:
            content = f.read().strip()

        metadata = {
            "source_url": url,
            "title": title,
            "type": doc_type,
        }

        chunks = chunk_text(f"# {title}\n\n{content}")
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

    for pdf_dir in pdf_dirs:
        if not os.path.exists(pdf_dir):
            continue
        for filename in os.listdir(pdf_dir):
            if not filename.endswith('.pdf'):
                continue
            filepath = os.path.join(pdf_dir, filename)
            text = extract_pdf_text(filepath)
            if not text or len(text) < 50:
                continue

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

    return docs


def main():
    print("Preparing RAG dataset from BIP Lublin data...")

    all_docs = []

    print("  Processing usługi...")
    all_docs.extend(process_uslugi())
    print(f"    -> {len(all_docs)} chunks")

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

    print(f"\nTotal documents/chunks: {len(all_docs)}")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"Saved to {OUTPUT_FILE} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    main()
