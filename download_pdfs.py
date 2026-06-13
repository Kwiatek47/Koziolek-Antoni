#!/usr/bin/env python3
"""
Download PDF attachments from BIP Lublin services.
Saves to dane_bip/pdf_uslugi/
"""
import json
import os
import sys
import time
import requests
from urllib.parse import unquote

DATA_DIR = os.path.join(os.path.dirname(__file__), "dane_bip")
OUTPUT_DIR = os.path.join(DATA_DIR, "pdf_uslugi")
USLUGI_FILE = os.path.join(DATA_DIR, "uslugi.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BIP-Lublin-RAG/1.0)"
}

TIMEOUT = 30
DELAY = 0.3  # polite crawling


def download_pdfs():
    if not os.path.exists(USLUGI_FILE):
        print(f"ERROR: {USLUGI_FILE} not found")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(USLUGI_FILE) as f:
        services = json.load(f)

    urls = []
    for svc in services:
        for att in svc.get("attachments", []):
            url = att.get("url", "")
            if url.lower().endswith(".pdf"):
                urls.append(url)

    print(f"Found {len(urls)} PDF attachments to download")
    print(f"Output: {OUTPUT_DIR}")
    print()

    already = 0
    downloaded = 0
    failed = 0

    for i, url in enumerate(urls):
        filename = unquote(url.split("/")[-1])[:120]
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            already += 1
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200 and len(resp.content) > 100:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                downloaded += 1
                if downloaded % 50 == 0:
                    print(f"  [{i+1}/{len(urls)}] Downloaded {downloaded} so far...")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  FAIL: {filename[:50]} - {e}")

        time.sleep(DELAY)

    print()
    print(f"Done! Downloaded: {downloaded}, Already existed: {already}, Failed: {failed}")
    print(f"Total PDFs in {OUTPUT_DIR}: {len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.pdf')])}")


if __name__ == "__main__":
    download_pdfs()
