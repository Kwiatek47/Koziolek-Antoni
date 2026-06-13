#!/usr/bin/env python3
"""
Scraper kart usług BIP Lublin.
Pobiera pełne karty usług ze wszystkimi sekcjami i metadanymi.
"""
import subprocess
import json
import time
import re
import os
from bs4 import BeautifulSoup

BASE = "https://bip.lublin.eu"
OUTPUT_DIR = "/Users/antoni.kwiatek/Documents/urbanlab lublin/dane_bip"
LINKS_FILE = os.path.join(OUTPUT_DIR, "all_service_links.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "uslugi.json")

KNOWN_SECTIONS = [
    "Numer karty informacyjnej",
    "Komórka organizacyjna załatwiająca sprawę",
    "Status",
    "Wymagane wnioski",
    "Wymagane załączniki",
    "Dokumenty do wglądu",
    "Sposób i miejsce składania dokumentów",
    "Wymagane opłaty",
    "Sposób i miejsce odbioru dokumentów",
    "Termin złożenia",
    "Termin załatwienia sprawy",
    "Tryb odwoławczy",
    "Informacje dodatkowe",
    "Podstawa prawna",
    "Kategoria sprawy",
    "Uwagi",
]

def fetch(url):
    result = subprocess.run(['curl', '-sL', '-m', '30', url], capture_output=True)
    return result.stdout.decode('utf-8', errors='replace')


def extract_service_card(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', id='content')
    if not content:
        return None

    text = content.get_text(separator='\n', strip=True)
    idx = text.find('Drukuj stronę\n')
    if idx > 0:
        text = text[idx + len('Drukuj stronę\n'):]

    for marker in ['Podmiot udostępniający informację']:
        end_idx = text.find(marker)
        if end_idx > 0:
            text = text[:end_idx]

    title_match = soup.find('title')
    title = title_match.get_text(strip=True).split('/')[0].strip() if title_match else ""

    card = {
        "url": url,
        "title": title,
        "data_utworzenia": "",
        "sections": {},
        "full_text": text.strip(),
    }

    date_match = re.search(r'Data utworzenia:\s*(.+)', text)
    if date_match:
        card["data_utworzenia"] = date_match.group(1).strip()

    for section_name in KNOWN_SECTIONS:
        pattern = re.escape(section_name) + r'\n(.+?)(?=' + '|'.join(re.escape(s) for s in KNOWN_SECTIONS if s != section_name) + r'|Podmiot udostępniający|Załączniki|$)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            card["sections"][section_name] = match.group(1).strip()

    # Extract PDF attachments
    attachments = []
    for a in content.find_all('a', href=True):
        href = a['href']
        if '.pdf' in href.lower():
            if href.startswith('/'):
                href = BASE + href
            attachments.append({
                "name": a.get_text(strip=True),
                "url": href,
            })
    card["attachments"] = attachments

    return card


def main():
    with open(LINKS_FILE, 'r') as f:
        links = json.load(f)

    print(f"Processing {len(links)} service cards...")

    results = []
    errors = []

    for i, item in enumerate(links):
        url = item['url']
        title = item['title']

        if i > 0 and i % 20 == 0:
            print(f"  [{i}/{len(links)}] {title[:50]}...")
            # Save progress
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        try:
            html = fetch(url)
            card = extract_service_card(html, url)
            if card:
                results.append(card)
            else:
                errors.append({"url": url, "error": "Could not extract content"})
        except Exception as e:
            errors.append({"url": url, "error": str(e)})

        time.sleep(0.2)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if errors:
        with open(os.path.join(OUTPUT_DIR, "uslugi_errors.json"), 'w') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Saved {len(results)} service cards to {OUTPUT_FILE}")
    if errors:
        print(f"Errors: {len(errors)}")


if __name__ == '__main__':
    main()
