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
import unicodedata
from collections import OrderedDict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "dane_bip")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data", "documents.json")
RAG_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEPARTMENTS_CONTACT_FILE = os.path.join(RAG_DATA_DIR, "departments_contact.json")

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


def slugify(text):
    """ASCII-safe slug for deterministic document ids."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", text).strip("_")


def load_json_file(filename, default):
    """Load curated JSON from dane_bip/ with a safe fallback."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return default
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def clean_lines(text):
    return [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines() if line.strip()]


def load_service_synonyms():
    """Load code + curated synonym mapping. Values are returned as comma-separated strings."""
    merged = dict(SYNONYMS)
    external = load_json_file("service_synonyms.json", {})
    for title, aliases in external.items():
        if isinstance(aliases, list):
            external_value = ", ".join(a.strip() for a in aliases if a.strip())
        else:
            external_value = str(aliases).strip()
        if not external_value:
            continue
        if title in merged and merged[title]:
            merged[title] = f"{merged[title]}, {external_value}"
        else:
            merged[title] = external_value
    return merged


def get_synonyms_for_title(title: str) -> str:
    """Find matching synonyms for a service title."""
    for key, synonyms in load_service_synonyms().items():
        if key.lower() in title.lower() or title.lower() in key.lower():
            return synonyms
    return ""


STREET_PATTERN = re.compile(
    r"(?P<street>(?:ul\.|al\.|pl\.|plac)\s+[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż0-9 .'\-]+?\s+\d+[A-Za-z]?)"
)
POSTAL_PATTERN = re.compile(r"(?P<postal>\d{2}-\d{3}\s+Lublin)")
PHONE_PATTERN = re.compile(r"(?:tel\.?|telefon(?:y)?|nr tel\.?)\s*[:.]?\s*(?P<phone>(?:\+48\s*)?81[\d\s-]{7,})", re.I)
HOURS_PATTERN = re.compile(r"\d{1,2}[:.]\d{2}\s*(?:-|–|do)\s*\d{1,2}[:.]\d{2}")
ROOM_PATTERN = re.compile(
    r"\b(?:(?:pok[oó]j|sala)\s*(?:nr|numer)?\s*[\w/-]+(?:\s*\([^)]*\))?|stanowisk[oa]\s*(?:nr|numer)?\s*[\w/-]+)",
    re.I,
)


def normalize_phone(phone):
    return re.sub(r"\s+", " ", (phone or "").replace("-", " ")).strip()


def normalize_hours(lines, start_index):
    """Collect a compact hours sentence starting at or after a 'Godziny' line."""
    collected = []
    for line in lines[start_index:start_index + 5]:
        if re.search(r"za pośrednictwem|elektronicznie|listownie|poczt", line, re.I) and collected:
            break
        if "godzin" in line.lower() or HOURS_PATTERN.search(line) or re.search(r"poniedzia|wtorek|środa|czwartek|piątek|sobota", line, re.I):
            collected.append(line)
    return " ".join(collected).strip()


def extract_contact_from_text(text, department=""):
    """Extract a factual contact record from a service-card free-text section."""
    lines = clean_lines(text)
    if not lines:
        return {
            "department": department,
            "address": "",
            "room": "",
            "phone": "",
            "hours": "",
        }

    address = ""
    room = ""
    phone = ""
    hours = ""

    for idx, line in enumerate(lines):
        street_match = STREET_PATTERN.search(line)
        if street_match and not address:
            street = street_match.group("street").strip(" ,.;")
            postal = ""
            for next_line in lines[idx:idx + 3]:
                postal_match = POSTAL_PATTERN.search(next_line)
                if postal_match:
                    postal = postal_match.group("postal")
                    break
            address = f"{street}, {postal}" if postal else street

            suffix = line[street_match.end():].strip(" ,.;")
            room_match = ROOM_PATTERN.search(suffix)
            if room_match:
                room = room_match.group(0).strip(" ,.;")

        if not room:
            room_match = ROOM_PATTERN.search(line)
            if room_match:
                room = room_match.group(0).strip(" ,.;")

        if not phone:
            phone_match = PHONE_PATTERN.search(line)
            if phone_match:
                phone = normalize_phone(phone_match.group("phone"))

        if not hours and ("godzin" in line.lower() or HOURS_PATTERN.search(line)):
            hours = normalize_hours(lines, idx)

    if not phone:
        phone_match = re.search(r"(?:\+48\s*)?81[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}", text or "")
        if phone_match:
            phone = normalize_phone(phone_match.group(0))

    if not hours:
        for idx, line in enumerate(lines):
            if re.search(r"poniedzia|wtorek|środa|czwartek|piątek|sobota", line, re.I) and HOURS_PATTERN.search(line):
                hours = normalize_hours(lines, idx)
                break

    return {
        "department": department,
        "address": address,
        "room": room,
        "phone": phone,
        "hours": hours,
    }


def generate_department_contact_records():
    """Parse contact details from service cards and save a structured contact lookup."""
    filepath = os.path.join(DATA_DIR, "uslugi.json")
    if not os.path.exists(filepath):
        return []

    with open(filepath, encoding="utf-8") as f:
        services = json.load(f)

    grouped = OrderedDict()
    contact_sections = [
        "Sposób i miejsce składania dokumentów",
        "Sposób i miejsce odbioru dokumentów",
    ]

    for svc in services:
        sections = svc.get("sections", {})
        department = sections.get("Komórka organizacyjna załatwiająca sprawę", "")
        if not department:
            continue

        for section_name in contact_sections:
            contact = extract_contact_from_text(sections.get(section_name, ""), department=department)
            if not any(contact.get(k) for k in ("address", "phone", "hours")):
                continue
            key = (
                contact.get("department", ""),
                contact.get("address", ""),
                contact.get("room", ""),
                contact.get("phone", ""),
            )
            if key not in grouped:
                grouped[key] = {
                    **contact,
                    "source": "BIP karta usługi",
                    "source_section": section_name,
                    "services": [],
                    "service_urls": [],
                    "card_numbers": [],
                }
            record = grouped[key]
            title = svc.get("title", "")
            url = svc.get("url", "")
            card_number = sections.get("Numer karty informacyjnej", "")
            if title and title not in record["services"]:
                record["services"].append(title)
            if url and url not in record["service_urls"]:
                record["service_urls"].append(url)
            if card_number and card_number not in record["card_numbers"]:
                record["card_numbers"].append(card_number)

    records = list(grouped.values())
    records.sort(key=lambda r: (r.get("department", ""), r.get("address", ""), r.get("room", "")))

    os.makedirs(RAG_DATA_DIR, exist_ok=True)
    with open(DEPARTMENTS_CONTACT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return records


def process_department_contacts():
    """Create high-precision contact chunks from parsed service-card contact blocks."""
    records = generate_department_contact_records()
    docs = []

    for idx, rec in enumerate(records):
        department = rec.get("department", "")
        services_preview = rec.get("services", [])[:12]
        source_url = (rec.get("service_urls") or [""])[0]
        lines = [
            f"# Kontakt: {department}",
            "Typ informacji: dane kontaktowe wydziału z kart usług BIP",
            f"Wydział: {department}",
        ]
        if rec.get("address"):
            lines.append(f"Adres: {rec['address']}")
        if rec.get("room"):
            lines.append(f"Pokój/stanowisko: {rec['room']}")
        if rec.get("phone"):
            lines.append(f"Telefon: {rec['phone']}")
        if rec.get("hours"):
            lines.append(f"Godziny przyjęć: {rec['hours']}")
        if services_preview:
            lines.append("")
            lines.append("Sprawy obsługiwane w tym kontakcie:")
            lines.extend(f"- {title}" for title in services_preview)

        docs.append({
            "id": f"department_contact_{slugify(department)}_{idx}",
            "content": "\n".join(lines),
            "metadata": {
                "source_url": source_url,
                "title": f"Kontakt: {department}",
                "type": "department_contact",
                "department": department,
                "address": rec.get("address", ""),
                "phone": rec.get("phone", ""),
                "service_count": len(rec.get("services", [])),
            },
        })

    return docs


def load_services():
    filepath = os.path.join(DATA_DIR, "uslugi.json")
    if not os.path.exists(filepath):
        return []
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def find_service_by_title(services, title):
    if not title:
        return None
    title_lower = title.lower()
    for svc in services:
        if svc.get("title", "").lower() == title_lower:
            return svc
    for svc in services:
        svc_title = svc.get("title", "").lower()
        if title_lower in svc_title or svc_title in title_lower:
            return svc
    return None


def short_section(sections, name, max_chars=500):
    value = re.sub(r"\s+", " ", sections.get(name, "") or "").strip()
    if len(value) > max_chars:
        return value[:max_chars].rsplit(" ", 1)[0] + "..."
    return value


def build_faq_answer(item, service):
    if item.get("answer"):
        return item["answer"]
    if not service:
        return "Sprawdź wskazane źródło BIP lub zadaj pytanie dokładniej, aby dopasować właściwą kartę usługi."

    sections = service.get("sections", {})
    parts = []
    department = sections.get("Komórka organizacyjna załatwiająca sprawę", "")
    if department:
        parts.append(f"Sprawę prowadzi: {department}.")
    cost = short_section(sections, "Wymagane opłaty", max_chars=220)
    if cost:
        parts.append(f"Opłaty: {cost}.")
    deadline = short_section(sections, "Termin załatwienia sprawy", max_chars=220)
    if deadline:
        parts.append(f"Termin: {deadline}.")
    documents = short_section(sections, "Wymagane załączniki", max_chars=260)
    if documents and documents.lower() != "brak":
        parts.append(f"Dokumenty: {documents}.")
    where = short_section(sections, "Sposób i miejsce składania dokumentów", max_chars=320)
    if where:
        parts.append(f"Gdzie/jak złożyć: {where}.")
    return " ".join(parts) if parts else "Szczegóły znajdują się w karcie usługi BIP."


def process_faq():
    """Create FAQ chunks mapping colloquial resident questions to formal BIP services."""
    faq_items = load_json_file("faq.json", [])
    services = load_services()
    docs = []

    for idx, item in enumerate(faq_items):
        service = find_service_by_title(services, item.get("service_title", ""))
        sections = service.get("sections", {}) if service else {}
        title = item.get("question", "")
        aliases = item.get("aliases", [])
        answer = build_faq_answer(item, service)
        source_url = item.get("source_url") or (service or {}).get("url", "")
        department = item.get("department") or sections.get("Komórka organizacyjna załatwiająca sprawę", "")
        service_title = item.get("service_title") or (service or {}).get("title", "")

        lines = [
            f"# FAQ: {title}",
            "Typ informacji: najczęstsze pytanie mieszkańca",
            f"Pytanie: {title}",
        ]
        if aliases:
            lines.append("Pytania podobne: " + "; ".join(aliases))
        if service_title:
            lines.append(f"Formalna karta usługi: {service_title}")
        if department:
            lines.append(f"Wydział: {department}")
        lines.extend(["", "Odpowiedź:", answer])

        docs.append({
            "id": f"faq_{item.get('id') or idx}",
            "content": "\n".join(lines),
            "metadata": {
                "source_url": source_url,
                "title": title,
                "type": "faq",
                "category": item.get("category", ""),
                "department": department,
                "service_title": service_title,
            },
        })

    return docs


def process_fee_tables():
    """Create focused fee chunks from curated common fees and service-card fee sections."""
    docs = []
    fees = load_json_file("fees.json", {})
    source_url = fees.get("source_url", "")

    for idx, item in enumerate(fees.get("items", [])):
        title = item.get("title", "")
        lines = [
            f"# Opłata skarbowa: {title}",
            "Typ informacji: tabela opłat",
            f"Czynność: {title}",
            f"Kwota: {item.get('amount', '')}",
        ]
        if item.get("when"):
            lines.append(f"Kiedy pobierana: {item['when']}")
        if item.get("exemptions"):
            lines.append(f"Zwolnienia/uwagi: {item['exemptions']}")
        if item.get("legal_basis"):
            lines.append(f"Podstawa: {item['legal_basis']}")

        docs.append({
            "id": f"fee_common_{item.get('id') or idx}",
            "content": "\n".join(lines),
            "metadata": {
                "source_url": item.get("source_url") or source_url,
                "title": title,
                "type": "fee_table",
                "category": "common_fee",
                "amount": item.get("amount", ""),
            },
        })

    for svc in load_services():
        sections = svc.get("sections", {})
        fee_text = sections.get("Wymagane opłaty", "")
        if not fee_text or re.fullmatch(r"\s*Brak\s*", fee_text, re.I):
            continue
        if not re.search(r"zł|PLN|opłat|bezpłat|rachunek|konto|przelew", fee_text, re.I):
            continue

        title = svc.get("title", "")
        department = sections.get("Komórka organizacyjna załatwiająca sprawę", "")
        card_number = sections.get("Numer karty informacyjnej", "")
        content = "\n".join([
            f"# Opłaty w usłudze: {title}",
            "Typ informacji: opłaty z karty usługi BIP",
            f"Usługa: {title}",
            f"Wydział: {department}",
            f"Karta: {card_number}",
            "",
            short_section(sections, "Wymagane opłaty", max_chars=1200),
        ])
        docs.append({
            "id": f"fee_service_{card_number or slugify(title)}",
            "content": content,
            "metadata": {
                "source_url": svc.get("url", ""),
                "title": title,
                "type": "fee_table",
                "category": "service_fee",
                "department": department,
                "card_number": card_number,
            },
        })

    return docs


def detect_online_channels(text):
    channels = []
    checks = [
        ("ePUAP", r"epuap|/UMLublin/SkrytkaESP"),
        ("pismo ogólne do podmiotu publicznego", r"pismo og[oó]lne"),
        ("Profil Zaufany / podpis zaufany", r"profil zaufany|podpis zaufany"),
        ("e-dowód", r"e-dow[oó]d"),
        ("podpis kwalifikowany", r"podpis kwalifikowany"),
        ("CEIDG online", r"ceidg"),
        ("mObywatel", r"mobywatel"),
        ("e-Doręczenia", r"e-?dor[eę]cze"),
    ]
    for label, pattern in checks:
        if re.search(pattern, text or "", re.I):
            channels.append(label)
    if not channels and re.search(r"elektronicznie|internet|online", text or "", re.I):
        channels.append("elektronicznie")
    return channels


def process_online_services():
    """Create an online-services map from service-card submission instructions."""
    docs = []
    online_services = []

    for svc in load_services():
        sections = svc.get("sections", {})
        submission = sections.get("Sposób i miejsce składania dokumentów", "")
        channels = detect_online_channels(submission)
        if not channels:
            continue
        title = svc.get("title", "")
        department = sections.get("Komórka organizacyjna załatwiająca sprawę", "")
        card_number = sections.get("Numer karty informacyjnej", "")
        online_services.append(title)

        lines = [
            f"# Usługa online: {title}",
            "Typ informacji: mapa usług online/ePUAP",
            f"Usługa: {title}",
            f"Wydział: {department}",
            f"Karta: {card_number}",
            "Kanały elektroniczne: " + ", ".join(channels),
            "",
            "Instrukcja z karty BIP:",
            short_section(sections, "Sposób i miejsce składania dokumentów", max_chars=1000),
        ]
        docs.append({
            "id": f"online_service_{card_number or slugify(title)}",
            "content": "\n".join(lines),
            "metadata": {
                "source_url": svc.get("url", ""),
                "title": title,
                "type": "online_service",
                "category": "service_online",
                "department": department,
                "channels": ", ".join(channels),
            },
        })

    overview = [
        "# Co można załatwić online w Urzędzie Miasta Lublin",
        "Typ informacji: mapa usług online/ePUAP",
        f"Liczba kart usług z kanałem elektronicznym: {len(online_services)}",
        "Najczęstsze kanały: ePUAP, pismo ogólne do podmiotu publicznego, Profil Zaufany, e-dowód, podpis kwalifikowany, CEIDG, mObywatel.",
        "",
        "Przykładowe usługi online:",
    ]
    overview.extend(f"- {title}" for title in sorted(online_services)[:80])
    docs.insert(0, {
        "id": "online_service_overview",
        "content": "\n".join(overview),
        "metadata": {
            "source_url": "https://bip.lublin.eu/e-urzad/opisy-uslug/",
            "title": "Mapa usług online/ePUAP",
            "type": "online_service",
            "category": "overview",
            "department": "",
            "channels": "ePUAP, Profil Zaufany, CEIDG, mObywatel",
        },
    })

    return docs


def process_practical_info():
    """Create chunks for practical office info from curated official-source records."""
    data = load_json_file("practical_info.json", {"items": []})
    docs = []

    for idx, item in enumerate(data.get("items", [])):
        title = item.get("title", "")
        location = item.get("location", "")
        lines = [
            f"# {title}",
            "Typ informacji: praktyczne informacje dla mieszkańca",
        ]
        if location:
            lines.append(f"Lokalizacja: {location}")
        for key, label in [
            ("address", "Adres"),
            ("public_transport", "Dojazd komunikacją"),
            ("parking", "Parking"),
            ("queue_system", "System kolejkowy"),
            ("accessibility", "Dostępność"),
            ("notes", "Uwagi"),
        ]:
            value = item.get(key)
            if isinstance(value, list):
                value = "; ".join(value)
            if value:
                lines.append(f"{label}: {value}")

        docs.append({
            "id": f"practical_info_{item.get('id') or idx}",
            "content": "\n".join(lines),
            "metadata": {
                "source_url": item.get("source_url", ""),
                "title": title,
                "type": "practical_info",
                "category": item.get("category", ""),
                "location": location,
            },
        })

    return docs


def process_office_calendar():
    """Create chunks for closures, holiday rules, and predictable high-traffic periods."""
    data = load_json_file("office_calendar.json", {"items": []})
    docs = []

    for idx, item in enumerate(data.get("items", [])):
        title = item.get("title", "")
        lines = [
            f"# {title}",
            "Typ informacji: kalendarz i terminy urzędowe",
        ]
        for key, label in [
            ("period", "Okres"),
            ("status", "Status"),
            ("details", "Szczegóły"),
            ("resident_advice", "Wskazówka dla mieszkańca"),
        ]:
            value = item.get(key)
            if isinstance(value, list):
                value = "; ".join(value)
            if value:
                lines.append(f"{label}: {value}")

        docs.append({
            "id": f"office_calendar_{item.get('id') or idx}",
            "content": "\n".join(lines),
            "metadata": {
                "source_url": item.get("source_url", ""),
                "title": title,
                "type": "office_calendar",
                "category": item.get("category", ""),
                "period": item.get("period", ""),
            },
        })

    return docs


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

    print("  Processing department contacts...")
    prev = len(all_docs)
    all_docs.extend(process_department_contacts())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing FAQ...")
    prev = len(all_docs)
    all_docs.extend(process_faq())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing fee tables...")
    prev = len(all_docs)
    all_docs.extend(process_fee_tables())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing online services map...")
    prev = len(all_docs)
    all_docs.extend(process_online_services())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing practical info...")
    prev = len(all_docs)
    all_docs.extend(process_practical_info())
    print(f"    -> {len(all_docs) - prev} chunks")

    print("  Processing office calendar...")
    prev = len(all_docs)
    all_docs.extend(process_office_calendar())
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
