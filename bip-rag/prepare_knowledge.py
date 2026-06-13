#!/usr/bin/env python3
"""
Przetwarzanie pobranej wiedzy bazowej do formatu RAG (documents.json).
Produkuje chunki kompatybilne z istniejacym prepare_dataset.py.
"""
import json
import os
import re
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "..", "dane_bip", "wiedza_bazowa", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "..", "dane_bip", "wiedza_bazowa", "processed")


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", text).strip("_")


def chunk_text_kb(text, max_chars=1200, overlap=150):
    """Split text into overlapping chunks for knowledge base."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", ", "]:
                last_sep = text.rfind(sep, start + max_chars // 2, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def process_pojecia():
    """Process concept definitions into RAG chunks."""
    docs = []
    pojecia_dir = os.path.join(RAW_DIR, "pojecia")
    if not os.path.exists(pojecia_dir):
        return docs

    for filename in sorted(os.listdir(pojecia_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(pojecia_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        term = data.get("term", "")
        definition = data.get("definition", "")
        source_url = data.get("source_url", "")
        source_type = data.get("source_type", "")
        legal_ref = data.get("legal_ref", "")

        if not definition or len(definition) < 20:
            continue

        prefix = (
            f"Typ: wiedza_bazowa\n"
            f"Kategoria: pojecie\n"
            f"Pojecie: {term}\n"
            f"Zrodlo: {source_type or 'gov.pl'}\n"
            f"Zasieg: ogolnopolski\n\n"
        )

        content = f"# {term}\n\n{definition}"

        if legal_ref:
            content += f"\n\nPodstawa prawna: {legal_ref}"

        slug = slugify(term)
        doc_id = f"kb_pojecie_{slug}_0"

        docs.append({
            "id": doc_id,
            "content": prefix + content,
            "metadata": {
                "source_url": source_url,
                "title": term,
                "type": "wiedza_bazowa",
                "kb_category": "pojecie",
                "scope": "ogolnopolski",
                "legal_ref": legal_ref,
                "source_type": source_type,
            }
        })

    return docs


def process_ustawy():
    """Process law articles into RAG chunks."""
    docs = []
    ustawy_dir = os.path.join(RAW_DIR, "ustawy")
    if not os.path.exists(ustawy_dir):
        return docs

    for filename in sorted(os.listdir(ustawy_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(ustawy_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        short_name = data.get("short_name", "")
        publisher = data.get("publisher", "DU")
        year = data.get("year", "")
        pos = data.get("pos", "")
        articles = data.get("articles", {})

        for art_num, art_text in articles.items():
            if not art_text or len(art_text) < 10:
                continue

            prefix = (
                f"Typ: wiedza_bazowa\n"
                f"Kategoria: ustawa\n"
                f"Ustawa: {short_name}\n"
                f"Artykul: {art_num}\n"
                f"Zasieg: ogolnopolski\n\n"
            )

            header = f"# {short_name} - Art. {art_num}\n\n"
            full_text = header + art_text

            source_url = f"https://api.sejm.gov.pl/eli/acts/{publisher}/{year}/{pos}/text.html?art={art_num}"
            legal_ref = f"{short_name} art. {art_num}"
            slug = slugify(short_name)

            chunks = chunk_text_kb(full_text, max_chars=1200, overlap=100)
            for i, chunk in enumerate(chunks):
                doc_id = f"kb_ustawa_{slug}_art{art_num}_{i}"
                docs.append({
                    "id": doc_id,
                    "content": prefix + chunk,
                    "metadata": {
                        "source_url": source_url,
                        "title": f"{short_name} art. {art_num}",
                        "type": "wiedza_bazowa",
                        "kb_category": "ustawa",
                        "scope": "ogolnopolski",
                        "legal_ref": legal_ref,
                        "source_type": "ustawa",
                    }
                })

    return docs


def process_e_uslugi():
    """Process e-service descriptions into RAG chunks."""
    docs = []
    e_uslugi_dir = os.path.join(RAW_DIR, "e_uslugi")
    if not os.path.exists(e_uslugi_dir):
        return docs

    for filename in sorted(os.listdir(e_uslugi_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(e_uslugi_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", "")
        url = data.get("url", "")
        content = data.get("content", "")

        if not content or len(content) < 30:
            continue

        prefix = (
            f"Typ: wiedza_bazowa\n"
            f"Kategoria: e_usluga\n"
            f"Nazwa: {name}\n"
            f"Zasieg: ogolnopolski\n\n"
        )

        full_text = f"# {name}\n\n{content}"
        slug = slugify(name)

        chunks = chunk_text_kb(full_text, max_chars=1200, overlap=150)
        for i, chunk in enumerate(chunks):
            doc_id = f"kb_eusluga_{slug}_{i}"
            docs.append({
                "id": doc_id,
                "content": prefix + chunk,
                "metadata": {
                    "source_url": url,
                    "title": name,
                    "type": "wiedza_bazowa",
                    "kb_category": "e_usluga",
                    "scope": "ogolnopolski",
                    "legal_ref": "",
                    "source_type": "gov_pl",
                }
            })

    return docs


def process_knowledge():
    """Main entry point - process all knowledge base sources."""
    all_docs = []

    print("    Pojecia...")
    pojecia = process_pojecia()
    all_docs.extend(pojecia)
    print(f"      -> {len(pojecia)} chunks")

    print("    Ustawy...")
    ustawy = process_ustawy()
    all_docs.extend(ustawy)
    print(f"      -> {len(ustawy)} chunks")

    print("    E-uslugi...")
    e_uslugi = process_e_uslugi()
    all_docs.extend(e_uslugi)
    print(f"      -> {len(e_uslugi)} chunks")

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    output = os.path.join(PROCESSED_DIR, "knowledge_items.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)
    print(f"    Zapisano: {output} ({len(all_docs)} chunks)")

    return all_docs


if __name__ == "__main__":
    print("Processing knowledge base...")
    docs = process_knowledge()
    print(f"\nTotal knowledge base chunks: {len(docs)}")
