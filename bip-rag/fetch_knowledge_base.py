#!/usr/bin/env python3
"""
Pobieranie wiedzy bazowej z oficjalnych zrodel rzadowych.
ELI API (sejm.gov.pl) + gov.pl scraping.
"""
import json
import os
import re
import time
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "dane_bip", "wiedza_bazowa")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CONFIG_FILE = os.path.join(DATA_DIR, "config", "sources.json")
REPORT_FILE = os.path.join(DATA_DIR, "fetch_report.json")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "BIP-Lublin-RAG/1.0 (knowledge-base-builder)"
})

RATE_LIMIT = 0.5
MAX_RETRIES = 3


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", text).strip("_")


def fetch_url(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            time.sleep(RATE_LIMIT)
            resp = SESSION.get(url, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt+1}/{retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"    FAILED: {e}")
                return None


def clean_html(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", text)


def extract_main_content(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find(class_=re.compile(r"content|article|main"))
    if main:
        text = main.get_text(separator="\n")
    else:
        body = soup.find("body")
        text = body.get_text(separator="\n") if body else soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", text)


# --- ELI API: Ustawy ---

def fetch_ustawy(config):
    ustawy_dir = os.path.join(RAW_DIR, "ustawy")
    os.makedirs(ustawy_dir, exist_ok=True)
    results = []

    for i, ustawa in enumerate(config.get("ustawy_p0", [])):
        short_name = ustawa["short_name"]
        search_title = ustawa["search_title"]
        articles = ustawa["articles"]
        print(f"  [{i+1}/{len(config['ustawy_p0'])}] Ustawa: {short_name}")

        search_url = f"https://api.sejm.gov.pl/eli/acts/search?title={requests.utils.quote(search_title)}&limit=5"
        resp = fetch_url(search_url)
        if not resp:
            results.append({"name": short_name, "status": "error", "reason": "search failed"})
            continue

        try:
            acts = resp.json()
            if isinstance(acts, dict) and "items" in acts:
                acts = acts["items"]
        except (json.JSONDecodeError, KeyError):
            results.append({"name": short_name, "status": "error", "reason": "invalid search response"})
            continue

        if not acts:
            results.append({"name": short_name, "status": "error", "reason": "no acts found"})
            continue

        act = None
        for a in acts:
            if a.get("status") == "OBOWIAZUJACY" or a.get("inForce") == "IN_FORCE":
                act = a
                break
        if not act:
            act = acts[0]

        publisher = act.get("publisher", "DU")
        year = act.get("year")
        pos = act.get("pos")
        if not year or not pos:
            eli_id = act.get("ELI", "")
            parts = eli_id.strip("/").split("/")
            if len(parts) >= 3:
                publisher = parts[-3] if len(parts) > 3 else "DU"
                year = parts[-2]
                pos = parts[-1]
            else:
                results.append({"name": short_name, "status": "error", "reason": "cannot parse act reference"})
                continue

        ustawa_data = {
            "short_name": short_name,
            "full_title": act.get("title", search_title),
            "publisher": publisher,
            "year": year,
            "pos": pos,
            "articles": {}
        }

        fetched_count = 0
        for art_num in articles:
            art_url = f"https://api.sejm.gov.pl/eli/acts/{publisher}/{year}/{pos}/text.html?art={art_num}"
            art_resp = fetch_url(art_url)
            if art_resp and art_resp.text.strip():
                text = clean_html(art_resp.text)
                if text and len(text) > 10:
                    ustawa_data["articles"][art_num] = text
                    fetched_count += 1

        output_path = os.path.join(ustawy_dir, f"{slugify(short_name)}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ustawa_data, f, ensure_ascii=False, indent=2)

        print(f"    -> {fetched_count}/{len(articles)} artykulow")
        results.append({
            "name": short_name,
            "status": "ok",
            "articles_fetched": fetched_count,
            "articles_total": len(articles),
        })

    return results


# --- Gov.pl: Pojecia ---

FALLBACK_DEFINITIONS = {
    "decyzja administracyjna": {
        "definition": "Decyzja administracyjna to akt prawny wydawany przez organ administracji publicznej, który rozstrzyga sprawę co do jej istoty w całości lub w części albo w inny sposób kończy postępowanie w danej instancji. Decyzja musi zawierać: oznaczenie organu, datę wydania, oznaczenie strony, powołanie podstawy prawnej, rozstrzygnięcie, uzasadnienie, pouczenie o środkach odwoławczych, podpis pracownika. Od decyzji przysługuje odwołanie do organu wyższego stopnia w terminie 14 dni od doręczenia.",
        "legal_ref": "KPA art. 104-113",
        "source_type": "ustawa"
    },
    "postanowienie": {
        "definition": "Postanowienie to akt procesowy organu administracji publicznej wydawany w toku postępowania administracyjnego, dotyczący kwestii wynikających w toku postępowania, lecz nierozstrzygający o istocie sprawy (chyba że przepisy kodeksu stanowią inaczej). Na postanowienie przysługuje zażalenie, gdy kodeks tak stanowi.",
        "legal_ref": "KPA art. 123-126",
        "source_type": "ustawa"
    },
    "zaświadczenie": {
        "definition": "Zaświadczenie to dokument urzędowy potwierdzający określone fakty lub stan prawny. Organ administracji publicznej wydaje zaświadczenie na żądanie osoby ubiegającej się o nie. Zaświadczenie wydaje się, jeżeli urzędowego potwierdzenia określonych faktów lub stanu prawnego wymaga przepis prawa lub osoba ubiega się o zaświadczenie ze względu na swój interes prawny. Zaświadczenie powinno być wydane bez zbędnej zwłoki, nie później niż w terminie 7 dni.",
        "legal_ref": "KPA art. 217-220",
        "source_type": "ustawa"
    },
    "zażalenie": {
        "definition": "Zażalenie to środek zaskarżenia postanowienia wydanego w toku postępowania administracyjnego. Zażalenie wnosi się w terminie 7 dni od dnia doręczenia postanowienia stronie, a gdy postanowienie zostało ogłoszone ustnie - od dnia jego ogłoszenia stronie. Zażalenie wnosi się do właściwego organu odwoławczego za pośrednictwem organu, który wydał postanowienie.",
        "legal_ref": "KPA art. 141-144",
        "source_type": "ustawa"
    },
    "odwołanie": {
        "definition": "Odwołanie to środek prawny przysługujący stronie od decyzji administracyjnej wydanej w pierwszej instancji. Odwołanie wnosi się do właściwego organu odwoławczego za pośrednictwem organu, który wydał decyzję, w terminie 14 dni od dnia doręczenia decyzji stronie. Odwołanie nie wymaga szczegółowego uzasadnienia - wystarczy, jeżeli z odwołania wynika, że strona nie jest zadowolona z wydanej decyzji.",
        "legal_ref": "KPA art. 127-140",
        "source_type": "ustawa"
    },
    "tryb odwoławczy": {
        "definition": "Tryb odwoławczy to procedura zaskarżania decyzji administracyjnych. Od decyzji wydanej w pierwszej instancji służy stronie odwołanie do organu wyższej instancji (najczęściej Samorządowe Kolegium Odwoławcze). Termin na wniesienie odwołania wynosi 14 dni od doręczenia decyzji. Odwołanie wnosi się za pośrednictwem organu, który decyzję wydał. W trakcie biegu terminu do wniesienia odwołania strona może zrzec się prawa do wniesienia odwołania.",
        "legal_ref": "KPA art. 127-140",
        "source_type": "ustawa"
    },
    "akt urodzenia": {
        "definition": "Akt urodzenia to dokument stanu cywilnego potwierdzający fakt urodzenia dziecka. Sporządzany jest przez kierownika urzędu stanu cywilnego na podstawie karty urodzenia lub karty martwego urodzenia. Zgłoszenia urodzenia dokonuje się w terminie 21 dni od dnia sporządzenia karty urodzenia. Akt urodzenia zawiera m.in.: nazwisko i imię dziecka, datę i miejsce urodzenia, dane rodziców.",
        "legal_ref": "Prawo o aktach stanu cywilnego art. 52-60",
        "source_type": "ustawa"
    },
    "akt małżeństwa": {
        "definition": "Akt małżeństwa to dokument stanu cywilnego potwierdzający zawarcie związku małżeńskiego. Sporządzany jest przez kierownika urzędu stanu cywilnego niezwłocznie po zawarciu małżeństwa. Zawiera dane małżonków, datę i miejsce zawarcia małżeństwa, dane świadków. Odpis aktu małżeństwa jest potrzebny m.in. do zmiany dokumentów po ślubie.",
        "legal_ref": "Prawo o aktach stanu cywilnego art. 76-88",
        "source_type": "ustawa"
    },
    "akt zgonu": {
        "definition": "Akt zgonu to dokument stanu cywilnego potwierdzający fakt śmierci osoby. Zgon należy zgłosić w terminie 3 dni od dnia sporządzenia karty zgonu (1 dzień jeśli zgon nastąpił wskutek choroby zakaźnej). Zgłoszenia dokonuje się w urzędzie stanu cywilnego właściwym dla miejsca zgonu. Akt zgonu jest wymagany do spraw spadkowych, ubezpieczeniowych i meldunkowych.",
        "legal_ref": "Prawo o aktach stanu cywilnego art. 92-95",
        "source_type": "ustawa"
    },
    "podpis kwalifikowany": {
        "definition": "Podpis kwalifikowany (kwalifikowany podpis elektroniczny) to zaawansowany podpis elektroniczny składany za pomocą kwalifikowanego urządzenia i opierający się na kwalifikowanym certyfikacie. Ma moc prawną równoważną podpisowi własnoręcznemu. Wydawany jest przez kwalifikowanych dostawców usług zaufania. Służy do podpisywania dokumentów elektronicznych składanych do urzędów, sądów i innych instytucji.",
        "legal_ref": "Rozporządzenie eIDAS, Ustawa o usługach zaufania art. 3",
        "source_type": "ustawa"
    },
    "opłata skarbowa": {
        "definition": "Opłata skarbowa to danina publiczna pobierana od czynności urzędowych (wydanie zaświadczenia, zezwolenia, koncesji), złożenia dokumentu pełnomocnictwa oraz od niektórych dokumentów (np. odpis aktu stanu cywilnego). Opłata skarbowa za: pełnomocnictwo - 17 zł, wydanie zaświadczenia - 17 zł, wydanie zezwolenia - różne stawki. Zwolnione z opłaty są m.in.: sprawy związane z budownictwem mieszkaniowym, dokumenty w sprawach alimentacyjnych.",
        "legal_ref": "Ustawa o opłacie skarbowej z dnia 16 listopada 2006 r.",
        "source_type": "ustawa"
    },
    "KPA": {
        "definition": "KPA (Kodeks postępowania administracyjnego) to podstawowy akt prawny regulujący postępowanie przed organami administracji publicznej. Określa zasady wszczynania, prowadzenia i kończenia postępowań administracyjnych, wydawania decyzji i postanowień, tryb odwoławczy, terminy załatwiania spraw (1 miesiąc, 2 miesiące dla spraw skomplikowanych), prawa stron postępowania. Dotyczy wszystkich spraw załatwianych w urzędach.",
        "legal_ref": "Ustawa z dnia 14 czerwca 1960 r. - Kodeks postępowania administracyjnego",
        "source_type": "ustawa"
    },
    "wniosek": {
        "definition": "Wniosek to pisemne lub elektroniczne żądanie skierowane do organu administracji publicznej w celu wszczęcia postępowania lub uzyskania rozstrzygnięcia. Wniosek powinien zawierać: dane wnioskodawcy, oznaczenie organu, treść żądania, podpis. Może być złożony osobiście, listownie lub elektronicznie (ePUAP). Organ ma obowiązek potwierdzić przyjęcie wniosku.",
        "legal_ref": "KPA art. 63-64",
        "source_type": "ustawa"
    },
    "załącznik": {
        "definition": "Załącznik to dokument dołączany do wniosku lub podania, stanowiący dowód lub uzupełnienie informacji niezbędnych do rozpatrzenia sprawy. Może to być: zdjęcie, zaświadczenie, odpis aktu, kopia dokumentu, formularz. Organ nie może żądać dokumentów, które sam może uzyskać z rejestrów publicznych.",
        "legal_ref": "KPA art. 76-78",
        "source_type": "ustawa"
    },
    "termin załatwienia": {
        "definition": "Termin załatwienia sprawy administracyjnej wynika z KPA: sprawy wymagające postępowania wyjaśniającego - nie później niż w ciągu 1 miesiąca; sprawy szczególnie skomplikowane - nie później niż 2 miesiące od dnia wszczęcia postępowania. Organ jest obowiązany zawiadomić strony o każdym przypadku niezałatwienia sprawy w terminie, podając przyczyny i wskazując nowy termin.",
        "legal_ref": "KPA art. 35-38",
        "source_type": "ustawa"
    },
    "skarga": {
        "definition": "Skarga to środek prawny, za pomocą którego obywatel może zwrócić się do organu w sprawach dotyczących zaniedbania lub nienależytego wykonywania zadań przez organy lub pracowników, naruszenia praworządności, przewlekłego załatwiania spraw. Skargę można złożyć do organu wyższego stopnia lub Rady Miasta. Organ ma obowiązek załatwić skargę bez zbędnej zwłoki, nie później niż w ciągu 1 miesiąca.",
        "legal_ref": "KPA art. 227-240",
        "source_type": "ustawa"
    },
    "informacja publiczna": {
        "definition": "Informacja publiczna to każda informacja o sprawach publicznych, udostępniana na zasadach i w trybie określonym w ustawie o dostępie do informacji publicznej. Obejmuje m.in. informacje o władzach publicznych, zasadach funkcjonowania, danych publicznych, majątku publicznym. Każdy ma prawo do dostępu do informacji publicznej. Udostępnienie powinno nastąpić bez zbędnej zwłoki, nie później niż 14 dni.",
        "legal_ref": "Ustawa o dostępie do informacji publicznej z dnia 6 września 2001 r.",
        "source_type": "ustawa"
    },
    "dowód rejestracyjny": {
        "definition": "Dowód rejestracyjny to dokument stwierdzający dopuszczenie pojazdu do ruchu. Wydawany jest przez starostę (w miastach na prawach powiatu - prezydenta) właściwego ze względu na miejsce zamieszkania właściciela. Zawiera dane pojazdu (marka, model, VIN, pojemność silnika) i właściciela. Wymagany jest do poruszania się pojazdem po drogach publicznych.",
        "legal_ref": "Prawo o ruchu drogowym art. 71-72",
        "source_type": "ustawa"
    },
    "pozwolenie na budowę": {
        "definition": "Pozwolenie na budowę to decyzja administracyjna zezwalająca na rozpoczęcie i prowadzenie budowy lub wykonywanie robót budowlanych. Wydawane jest przez starostę (prezydenta miasta) na wniosek inwestora. Wymagane dokumenty: projekt budowlany, zaświadczenie o zgodności z planem zagospodarowania, oświadczenie o prawie do dysponowania nieruchomością. Organ wydaje decyzję w terminie 65 dni.",
        "legal_ref": "Prawo budowlane art. 28-40",
        "source_type": "ustawa"
    },
    "zezwolenie": {
        "definition": "Zezwolenie to akt administracyjny wydawany przez organ administracji, który uprawnia do wykonywania określonej działalności lub czynności. Rodzaje zezwoleń w urzędzie miasta: zezwolenie na sprzedaż alkoholu, zezwolenie na zajęcie pasa drogowego, zezwolenie na wycinkę drzew, zezwolenie na organizację imprezy masowej. Zezwolenie wydawane jest na wniosek, po spełnieniu wymagań określonych w przepisach.",
        "legal_ref": "Różne ustawy szczegółowe",
        "source_type": "ustawa"
    },
    "świadectwo": {
        "definition": "Świadectwo to dokument urzędowy poświadczający określony fakt lub uprawnienie. W kontekście urzędu miasta: świadectwo charakterystyki energetycznej budynku, świadectwo pracy, świadectwo szkolne. Świadectwo wydawane jest przez uprawniony organ lub instytucję po spełnieniu określonych wymagań.",
        "legal_ref": "Różne ustawy szczególowe",
        "source_type": "ustawa"
    },
}


def fetch_pojecia(config):
    pojecia_dir = os.path.join(RAW_DIR, "pojecia")
    os.makedirs(pojecia_dir, exist_ok=True)
    results = []

    pojecia = config.get("pojecia_p0", [])
    for i, item in enumerate(pojecia):
        term = item["term"]
        urls = item.get("urls", [])
        slug = slugify(term)
        print(f"  [{i+1}/{len(pojecia)}] Pobieranie: {term}...", end=" ")

        data = {"term": term, "definition": "", "source_url": "", "source_type": "", "legal_ref": ""}

        fetched = False
        if urls:
            for url in urls:
                resp = fetch_url(url)
                if resp:
                    content = extract_main_content(resp.text)
                    if content and len(content) > 50:
                        data["definition"] = content[:3000]
                        data["source_url"] = url
                        data["source_type"] = "gov_pl"
                        fetched = True
                        word_count = len(content.split())
                        print(f"OK ({word_count} slow)")
                        break

        if not fetched:
            term_ascii = unicodedata.normalize("NFKD", term).encode("ascii", "ignore").decode("ascii").lower()
            fallback = FALLBACK_DEFINITIONS.get(term) or FALLBACK_DEFINITIONS.get(term_ascii)
            if fallback:
                data["definition"] = fallback["definition"]
                data["legal_ref"] = fallback.get("legal_ref", "")
                data["source_type"] = fallback.get("source_type", "ustawa")
                print(f"FALLBACK ({len(data['definition'].split())} slow)")
                fetched = True
            else:
                print("SKIP (brak URL i fallback)")

        if fetched:
            output_path = os.path.join(pojecia_dir, f"{slug}.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        results.append({
            "term": term,
            "status": "ok" if fetched else "skipped",
            "source": data["source_type"] if fetched else "none",
            "words": len(data["definition"].split()) if fetched else 0,
        })

    return results


# --- E-uslugi ---

def fetch_e_uslugi(config):
    e_uslugi_dir = os.path.join(RAW_DIR, "e_uslugi")
    os.makedirs(e_uslugi_dir, exist_ok=True)
    results = []

    services = config.get("e_uslugi", [])
    for i, svc in enumerate(services):
        name = svc["name"]
        url = svc["url"]
        slug = slugify(name)
        print(f"  [{i+1}/{len(services)}] E-usluga: {name}...", end=" ")

        resp = fetch_url(url)
        if not resp:
            results.append({"name": name, "status": "error"})
            print("FAILED")
            continue

        content = extract_main_content(resp.text)
        if not content or len(content) < 30:
            results.append({"name": name, "status": "empty"})
            print("EMPTY")
            continue

        data = {
            "name": name,
            "url": url,
            "content": content[:5000],
        }

        output_path = os.path.join(e_uslugi_dir, f"{slug}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        word_count = len(content.split())
        print(f"OK ({word_count} slow)")
        results.append({"name": name, "status": "ok", "words": word_count})

    return results


def main():
    print("=" * 60)
    print("FETCH KNOWLEDGE BASE - BIP Lublin RAG")
    print(f"Start: {datetime.now().isoformat()}")
    print("=" * 60)

    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)

    report = {"timestamp": datetime.now().isoformat(), "sections": {}}

    print("\n[1/3] Pobieranie artykulow ustaw (ELI API)...")
    report["sections"]["ustawy"] = fetch_ustawy(config)

    print("\n[2/3] Pobieranie definicji pojec...")
    report["sections"]["pojecia"] = fetch_pojecia(config)

    print("\n[3/3] Pobieranie e-uslug...")
    report["sections"]["e_uslugi"] = fetch_e_uslugi(config)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("RAPORT:")
    for section, items in report["sections"].items():
        ok_count = sum(1 for x in items if x.get("status") == "ok")
        print(f"  {section}: {ok_count}/{len(items)} OK")
    print(f"\nRaport zapisany: {REPORT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
