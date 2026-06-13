#!/usr/bin/env python3
"""
Generate department profile documents for RAG.
Creates an anchor document per department listing what it handles,
its services, and key info - so RAG correctly routes questions.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dane_bip")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "departments.json")

# Manual enrichment: short description + key responsibilities
DEPT_PROFILES = {
    "Wydział Spraw Administracyjnych": {
        "description": "Wydział odpowiedzialny za sprawy obywatelskie i administracyjne mieszkańców.",
        "handles": [
            "Dowody osobiste (wydanie, wymiana, utrata, zgłoszenie uszkodzenia)",
            "PESEL (nadanie numeru, zmiany danych)",
            "Ewidencja ludności (zameldowanie, wymeldowanie, meldunek czasowy i stały)",
            "Rejestr wyborców",
            "Zgromadzenia publiczne",
            "Zezwolenia na alkohol",
            "Kwalifikacja wojskowa",
            "Uznanie za obywatela polskiego",
            "E-dowód (PIN, certyfikaty, zawieszenie)",
        ],
        "address": "ul. Spokojna 2, 20-074 Lublin",
        "note": "UWAGA: Dowody osobiste i meldunek to ten wydział, NIE Wydział Komunikacji!",
    },
    "Wydział Komunikacji": {
        "description": "Wydział odpowiedzialny za sprawy związane z pojazdami i kierowcami.",
        "handles": [
            "Rejestracja pojazdów (nowych, używanych, importowanych)",
            "Wyrejestrowanie pojazdu",
            "Dowody rejestracyjne (wydanie, wymiana, wtórnik)",
            "Tablice rejestracyjne (nowe, wtórnik, indywidualne)",
            "Prawa jazdy (wydanie, wymiana, międzynarodowe, zatrzymanie)",
            "Karty parkingowe dla osób niepełnosprawnych",
            "Licencje na transport",
            "Ośrodki szkolenia kierowców",
            "Stacje kontroli pojazdów",
        ],
        "address": "ul. Czechowska 19A, 20-072 Lublin",
        "note": "UWAGA: Dowody rejestracyjne i prawa jazdy to ten wydział, NIE Wydział Spraw Administracyjnych!",
    },
    "Urząd Stanu Cywilnego": {
        "description": "Urząd odpowiedzialny za rejestrację stanu cywilnego.",
        "handles": [
            "Ślub cywilny (zawarcie małżeństwa)",
            "Akty urodzenia, małżeństwa, zgonu (odpisy, duplikaty)",
            "Rejestracja urodzenia dziecka",
            "Zmiana imienia i nazwiska",
            "Rozwód - transkrypcja wyroku",
            "Odtworzenie aktów zagranicznych",
            "Medale za długoletnie pożycie małżeńskie",
            "Zaświadczenia o zdolności prawnej do zawarcia małżeństwa za granicą",
        ],
        "address": "ul. Spokojna 2, 20-074 Lublin",
    },
    "Wydział Geodezji": {
        "description": "Wydział odpowiedzialny za geodezję, kartografię, gospodarkę nieruchomościami i ochronę środowiska.",
        "handles": [
            "Wypisy i wyrysy z ewidencji gruntów",
            "Podział nieruchomości",
            "Rozgraniczenie nieruchomości",
            "Klasyfikacja gruntów",
            "Koordynacja sieci uzbrojenia terenu",
            "Mapy do celów projektowych",
            "Numeracja porządkowa (nadanie adresu)",
            "Karty wędkarskie",
            "Decyzje środowiskowe",
        ],
        "address": "ul. Spokojna 2, 20-074 Lublin",
    },
    "Wydział Spraw Mieszkaniowych": {
        "description": "Wydział zajmujący się sprawami lokalowymi i mieszkaniowymi.",
        "handles": [
            "Przydział mieszkań komunalnych",
            "Najem lokali socjalnych",
            "Zamiana mieszkań",
            "Dodatki mieszkaniowe",
            "Dodatki energetyczne",
            "Obniżka czynszu",
            "Repatrianci - aktywizacja zawodowa",
            "TBS Nowy Dom - najem",
        ],
        "address": "ul. Peowiaków 13, 20-007 Lublin",
    },
    "Wydział Podatków": {
        "description": "Wydział odpowiedzialny za podatki lokalne i opłaty.",
        "handles": [
            "Podatek od nieruchomości (deklaracje, wymiar, ulgi)",
            "Podatek rolny",
            "Podatek leśny",
            "Podatek od środków transportowych",
            "Opłata skarbowa",
            "Zaświadczenia o niezaleganiu w podatkach",
            "Umorzenia, odroczenia, rozłożenie na raty",
            "Zwrot nadpłaty podatku",
        ],
        "address": "ul. Wieniawska 14, 20-071 Lublin",
    },
    "Wydział Architektury i Budownictwa": {
        "description": "Wydział odpowiedzialny za sprawy budowlane i architektoniczne.",
        "handles": [
            "Pozwolenie na budowę",
            "Pozwolenie na rozbiórkę",
            "Zgłoszenie budowy/robót budowlanych",
            "Przeniesienie pozwolenia na budowę",
            "Zmiana pozwolenia na budowę",
            "Zaświadczenie o samodzielności lokalu",
        ],
        "address": "ul. Wieniawska 14, 20-071 Lublin",
    },
    "Wydział Zieleni i Gospodarki Komunalnej": {
        "description": "Wydział odpowiedzialny za zieleń miejską, ochronę środowiska i gospodarkę komunalną.",
        "handles": [
            "Zezwolenia na usunięcie drzew i krzewów",
            "Decyzje środowiskowe",
            "Rejestracja zwierząt egzotycznych (CITES)",
            "Cmentarze komunalne",
            "Retencja terenowa",
            "Zezwolenia na prowadzenie działalności w zakresie odpadów",
        ],
        "address": "ul. Tomasza Zana 38, 20-601 Lublin",
    },
    "Wydział Gospodarowania Mieniem i Energią": {
        "description": "Wydział zarządzający mieniem komunalnym i sprawami energetycznymi.",
        "handles": [
            "Dzierżawa gruntów miejskich",
            "Użytkowanie wieczyste (opłaty, przekształcenie)",
            "Sprzedaż garaży i lokali komunalnych",
            "Nabywanie nieruchomości na rzecz gminy",
            "Bonifikaty od opłat za użytkowanie wieczyste",
        ],
        "address": "ul. Spokojna 2, 20-074 Lublin",
    },
    "Wydział Sportu i Turystyki": {
        "description": "Wydział odpowiedzialny za sport, turystykę i rekreację.",
        "handles": [
            "Ewidencja klubów sportowych i UKS",
            "Obiekty hotelarskie (wpis, wykreślenie, zmiana)",
            "Organizatorzy turystyki",
            "Dotacje na sport",
        ],
        "address": "ul. Filaretów 44, 20-609 Lublin",
    },
}


def generate_department_docs():
    """Generate RAG documents for each department."""
    uslugi_path = os.path.join(DATA_DIR, "uslugi.json")
    if not os.path.exists(uslugi_path):
        print("uslugi.json not found!")
        return

    with open(uslugi_path) as f:
        services = json.load(f)

    # Load organizational structure for hours/phones
    struktura_path = os.path.join(DATA_DIR, "struktura_organizacyjna_full.json")
    dept_info_extra = {}
    if os.path.exists(struktura_path):
        with open(struktura_path) as f:
            struktura = json.load(f)
        for entry in struktura:
            title = entry.get("title", "")
            content = entry.get("content", "")
            if not content:
                continue
            info = {}
            if "Telefon" in content:
                import re
                phone_match = re.search(r"Telefon\n(.+?)(?:\n|$)", content)
                if phone_match:
                    info["phone"] = phone_match.group(1).strip()
            if "Godziny pracy" in content:
                hours_match = re.search(r"od poniedziałku do piątku w godzinach (\d+[:.]\d+\s*[-–]\s*\d+[:.]\d+)", content)
                if hours_match:
                    info["hours"] = f"pon-pt {hours_match.group(1)}"
                else:
                    hours_match = re.search(r"poniedziałek.*?(\d+[:.]\d+)", content)
                    if hours_match:
                        info["hours"] = "Zróżnicowane godziny - sprawdź na BIP"
            if "Kierownik komórki organizacyjnej" in content:
                head_match = re.search(r"Kierownik komórki organizacyjnej\n(.+?)(?:\n|$)", content)
                if head_match:
                    info["head"] = head_match.group(1).strip()
            if info:
                dept_info_extra[title] = info

    # Group services by department
    dept_services = {}
    for svc in services:
        dept = svc.get("sections", {}).get("Komórka organizacyjna załatwiająca sprawę", "")
        if not dept:
            continue
        if dept not in dept_services:
            dept_services[dept] = []
        dept_services[dept].append(svc.get("title", ""))

    docs = []

    for dept_name, svc_titles in dept_services.items():
        profile = DEPT_PROFILES.get(dept_name, {})
        description = profile.get("description", f"Jednostka organizacyjna Urzędu Miasta Lublin.")
        handles = profile.get("handles", [])
        address = profile.get("address", "")
        note = profile.get("note", "")

        extra = dept_info_extra.get(dept_name, {})
        phone = extra.get("phone", "")
        hours = extra.get("hours", "pon-pt 7:30-15:30")
        head = extra.get("head", "")

        lines = [
            f"# {dept_name}",
            f"",
            f"{description}",
            f"",
        ]

        if address:
            lines.append(f"Adres: {address}")
        if phone:
            lines.append(f"Telefon: {phone}")
        if hours:
            lines.append(f"Godziny pracy: {hours}")
        if head:
            lines.append(f"Kierownik: {head}")
        if address or phone or hours:
            lines.append("")

        if note:
            lines.append(f"WAŻNE: {note}")
            lines.append("")

        if handles:
            lines.append("## Główne zadania i sprawy do załatwienia:")
            for h in handles:
                lines.append(f"- {h}")
            lines.append("")

        lines.append(f"## Lista usług ({len(svc_titles)} w BIP):")
        for title in sorted(svc_titles):
            lines.append(f"- {title}")

        content = "\n".join(lines)

        docs.append({
            "id": f"dept_{dept_name.replace(' ', '_')[:40]}",
            "content": content,
            "metadata": {
                "source_url": "https://bip.lublin.eu/urzad-miasta-lublin/struktura-organizacyjna/",
                "title": dept_name,
                "type": "department_profile",
                "category": "struktura organizacyjna",
                "department": dept_name,
            },
        })

    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(docs)} department profiles -> {OUTPUT_FILE}")
    return docs


if __name__ == "__main__":
    generate_department_docs()
