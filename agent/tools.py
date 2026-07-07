#!/usr/bin/env python3
"""Narzędzia agenta KOS = dostęp do warstw wiedzy (spec: model NIE jest bazą wiedzy).

Trzy narzędzia odpowiadają warstwom architektury:
  • profesja_szczegoly  → Warstwa 3 (SQL) + Warstwa 2 (Graf): dokładne cechy + kariera
  • porownaj_ceche      → Warstwa 3 (SQL): ekstremum liczbowe (nigdy z modelu)
  • szukaj_zasad        → Warstwa 4 (Wektory): proza/lore/interpretacje z ChromaDB

Każdy wynik niesie ŹRÓDŁO i POZIOM PEWNOŚCI (Confidence Engine).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from kos.query import KOS  # noqa: E402

_kos = None
_embedder = None
_collection = None


def _get_kos():
    global _kos
    if _kos is None:
        _kos = KOS()
    return _kos


def _get_vectors():
    """Leniwe ładowanie modelu e5 + kolekcji ChromaDB (ciężkie — raz na proces)."""
    global _embedder, _collection
    if _collection is None:
        import chromadb
        from embedder import load_embedder
        _embedder = load_embedder()
        client = chromadb.PersistentClient(path=os.path.join(ROOT, "data", "chroma"))
        _collection = client.get_collection("warhammer")
    return _embedder, _collection


# ── Warstwa 3+2: profesja ──────────────────────────────────────────────────
def profesja_szczegoly(nazwa: str) -> dict:
    kos = _get_kos()
    nid = kos.resolve_profession(nazwa)
    if not nid:
        return {"znaleziono": False,
                "info": f"Profesji «{nazwa}» nie ma w warstwie strukturalnej. "
                        "Sprawdź pisownię lub użyj szukaj_zasad dla prozy.",
                "pewnosc": None}
    stats = kos.profession_stats(nid)
    entries, exits = kos.career_neighbors(nid)
    return {
        "znaleziono": True,
        "nazwa": stats["name"], "rodzaj": stats["kind"], "strona": stats["page"],
        "cechy_glowne": {k: v for k, v in stats["main"].items() if v != "—"},
        "cechy_drugorzedne": {k: v for k, v in stats["secondary"].items() if v != "—"},
        "umiejetnosci": stats["skills"], "zdolnosci": stats["talents"],
        "wyposazenie": stats["trappings"],
        "wejscie_z": [e["name"] for e in entries],
        "wyjscie_do": [e["name"] for e in exits],
        "zrodlo": stats["source"], "pewnosc": stats["confidence"],
    }


# ── Warstwa 3: porównanie liczbowe ─────────────────────────────────────────
def porownaj_ceche(cecha: str, tryb: str = "max") -> dict:
    kos = _get_kos()
    col = kos.find_stat_col(cecha) or cecha
    res = kos.stat_extreme(col, biggest=(tryb != "min"))
    if not res:
        return {"znaleziono": False,
                "info": f"Nie rozpoznano cechy «{cecha}».", "pewnosc": None}
    return {
        "znaleziono": True, "cecha": col, "tryb": tryb,
        "wynik": [{"profesja": r["name"], "wartosc": r["value"], "strona": r["page"]}
                  for r in res],
        "zrodlo": "Księga Zasad 2e (tabele cech)", "pewnosc": 0.95,
    }


# ── Warstwa 3: oręż ────────────────────────────────────────────────────────
def bron_szczegoly(nazwa: str) -> dict:
    kos = _get_kos()
    wid = kos.resolve_weapon(nazwa)
    if not wid:
        return {"znaleziono": False,
                "info": f"Oręża «{nazwa}» nie ma w tabeli broni (str. 110). "
                        "Sprawdź nazwę lub użyj szukaj_zasad dla opisu.",
                "pewnosc": None}
    d = kos.weapon_details(wid)
    out = {
        "znaleziono": True, "nazwa": d["name"], "klasa": d["klasa"],
        "obrazenia": d["sila_broni"], "cena": d["cena"],
        "obciazenie": d["obciazenie"], "kategoria": d["kategoria"],
        "cechy_oreza": d["cechy"], "dostepnosc": d["dostepnosc"],
        "dwureczna": d["dwureczna"], "strona": d["page"],
        "zrodlo": d["source"], "pewnosc": d["confidence"],
    }
    if d["klasa"] == "strzelecka":
        out["zasieg"] = d["zasieg"]
        out["przeladowanie"] = d["przeladowanie"]
    return out


# ── Warstwa 3: pancerz ─────────────────────────────────────────────────────
def pancerz_szczegoly(nazwa: str) -> dict:
    kos = _get_kos()
    ids = kos.resolve_armour(nazwa)
    if not ids:
        return {"znaleziono": False,
                "info": f"Pancerza «{nazwa}» nie ma w Tabeli 5-6 (str. 114).",
                "pewnosc": None}
    elementy = []
    for nid in ids:
        d = kos.armour_details(nid)
        elementy.append({
            "nazwa": d["name"], "material": d["material"], "PZ": d["pz"],
            "cena": d["cena"], "obciazenie": d["obciazenie"],
            "chronione_lokacje": d["lokacje"], "dostepnosc": d["dostepnosc"],
        })
    return {"znaleziono": True, "elementy": elementy,
            "zrodlo": "Księga Zasad 2e (Tabela 5-6, str. 114)", "pewnosc": 0.95}


# ── Warstwa 3+2: czary ─────────────────────────────────────────────────────
def czar_szczegoly(nazwa: str) -> dict:
    kos = _get_kos()
    sid = kos.resolve_spell(nazwa)
    if not sid:
        return {"znaleziono": False,
                "info": f"Czaru «{nazwa}» nie ma jeszcze w bazie (na razie wpisana "
                        "jest Magia powszechna; kolejne tradycje w toku).",
                "pewnosc": None}
    d = kos.spell_details(sid)
    return {"znaleziono": True, "nazwa": d["name"], "tradycja": d["tradycja"],
            "poziom_mocy": d["pm"], "czas_rzucania": d["czas_rzucania"],
            "zasieg": d["zasieg"] or "—", "czas_trwania": d["czas_trwania"] or "—",
            "skladnik": d["skladnik"], "opis": d["opis"],
            "strona": d["page"], "zrodlo": d["source"], "pewnosc": d["confidence"]}


def czary_tradycji(tradycja: str) -> dict:
    kos = _get_kos()
    match, spells = kos.spells_by_tradition(tradycja)
    if not match:
        return {"znaleziono": False,
                "info": f"Nie znam tradycji «{tradycja}». Dostępne: "
                        f"{', '.join(kos.list_traditions())}.", "pewnosc": None}
    return {"znaleziono": True, "tradycja": match, "liczba": len(spells),
            "czary": [{"nazwa": s["name"], "poziom_mocy": s["pm"], "strona": s["page"]}
                      for s in spells],
            "zrodlo": "Księga Zasad 2e (Rozdział VII: Magia)", "pewnosc": 0.95}


# ── Warstwa 4: proza / lore / zasady ───────────────────────────────────────
def szukaj_zasad(pytanie: str, k: int = 5) -> dict:
    embedder, col = _get_vectors()
    from embedder import embed_query
    qemb = embed_query(embedder, pytanie).tolist()
    res = col.query(query_embeddings=[qemb], n_results=k,
                    include=["documents", "metadatas", "distances"])
    fragmenty = []
    for doc, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        sim = 1 - dist
        a, b = m["page_start"], m["page_end"]
        fragmenty.append({
            "strona": f"str. {a}" if a == b else f"str. {a}–{b}",
            "podobienstwo": round(sim, 3),
            "tekst": " ".join(doc.split())[:700],
            # pewność ~ podobieństwo (proza = interpretacja, nie twarda tabela)
            "pewnosc": round(min(0.9, max(0.3, sim)), 2),
        })
    return {"pytanie": pytanie, "fragmenty": fragmenty,
            "zrodlo": "Księga Zasad 2e (OCR)"}


# schematy narzędzi dla Claude API (tool use)
TOOLS = [
    {
        "name": "profesja_szczegoly",
        "description": "Zwraca DOKŁADNE dane profesji (klasy) z tabel Księgi Zasad: "
                       "modyfikatory cech głównych i drugorzędnych, umiejętności, "
                       "zdolności, wyposażenie oraz siatkę rozwoju (z jakich profesji "
                       "można wejść i do jakich wyjść). Używaj ZAWSZE gdy pytanie dotyczy "
                       "statystyk/cech/rozwoju konkretnej profesji — nie zgaduj liczb.",
        "input_schema": {
            "type": "object",
            "properties": {"nazwa": {"type": "string",
                           "description": "nazwa profesji, np. «Akolita», «Zabójca demonów»"}},
            "required": ["nazwa"],
        },
    },
    {
        "name": "porownaj_ceche",
        "description": "Znajduje profesję(-e) z największą lub najmniejszą modyfikacją danej "
                       "cechy (WW, US, K, Odp, Zr, Int, SW, Ogd, A, Żyw, S, Wt, Sz, Mag, PO, PP). "
                       "Liczone z tabel SQL. Używaj do pytań «która profesja ma największą…».",
        "input_schema": {
            "type": "object",
            "properties": {
                "cecha": {"type": "string", "description": "nazwa cechy, np. «WW», «Krzepa»"},
                "tryb": {"type": "string", "enum": ["max", "min"],
                         "description": "max = największa, min = najmniejsza"},
            },
            "required": ["cecha"],
        },
    },
    {
        "name": "bron_szczegoly",
        "description": "Zwraca DOKŁADNE dane oręża z Tabeli 5-4/5-5 Księgi Zasad "
                       "(str. 110): obrażenia (Siła broni, np. «S+1», «4»), cena, "
                       "obciążenie, kategoria/grupa, cechy oręża, dostępność, a dla "
                       "broni strzeleckiej także zasięg i przeładowanie. Używaj do "
                       "pytań «ile obrażeń zadaje…», «ile kosztuje…», «jaki zasięg ma…».",
        "input_schema": {
            "type": "object",
            "properties": {"nazwa": {"type": "string",
                           "description": "nazwa broni, np. «Halabarda», «Pistolet», «Rapier»"}},
            "required": ["nazwa"],
        },
    },
    {
        "name": "pancerz_szczegoly",
        "description": "Zwraca dane pancerza z Tabeli 5-6 (str. 114): Punkty Zbroi "
                       "(PZ), cena, obciążenie, chronione lokacje, dostępność. Nazwy "
                       "powtarzają się między materiałami (skórzana/kolcza/płytowa) — "
                       "narzędzie zwraca wszystkie pasujące elementy. Doprecyzuj "
                       "materiał w nazwie, by zawęzić (np. «hełm płytowy»).",
        "input_schema": {
            "type": "object",
            "properties": {"nazwa": {"type": "string",
                           "description": "nazwa pancerza, np. «Kolczuga», «hełm płytowy», «napierśnik»"}},
            "required": ["nazwa"],
        },
    },
    {
        "name": "czar_szczegoly",
        "description": "Zwraca dane konkretnego czaru: Poziom Mocy (liczba do "
                       "rzucenia), czas rzucania, zasięg, czas trwania, składnik i "
                       "opis efektu. Używaj do «jak działa czar…», «jaki poziom mocy "
                       "ma…». (Na razie w bazie Magia powszechna; kolejne tradycje w toku.)",
        "input_schema": {
            "type": "object",
            "properties": {"nazwa": {"type": "string",
                           "description": "nazwa czaru, np. «Pancerz Eteru», «Uciszenie»"}},
            "required": ["nazwa"],
        },
    },
    {
        "name": "czary_tradycji",
        "description": "Zwraca LISTĘ czarów danej tradycji/dziedziny magii wraz z "
                       "Poziomem Mocy. Używaj do pytań «jakie czary są w danej magii», "
                       "«lista zaklęć tradycji…».",
        "input_schema": {
            "type": "object",
            "properties": {"tradycja": {"type": "string",
                           "description": "nazwa tradycji, np. «Magia powszechna»"}},
            "required": ["tradycja"],
        },
    },
    {
        "name": "szukaj_zasad",
        "description": "Wyszukiwanie semantyczne w treści Księgi Zasad (proza, opisy, "
                       "zasady, lore). Używaj do pytań o mechaniki, opisy, tło świata, "
                       "wyjaśnienia zasad — wszystko, co nie jest twardą tabelą liczb. "
                       "Zwraca fragmenty z numerami stron.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pytanie": {"type": "string", "description": "zapytanie po polsku"},
                "k": {"type": "integer", "description": "ile fragmentów (domyślnie 5)"},
            },
            "required": ["pytanie"],
        },
    },
]

DISPATCH = {
    "profesja_szczegoly": profesja_szczegoly,
    "porownaj_ceche": porownaj_ceche,
    "bron_szczegoly": bron_szczegoly,
    "pancerz_szczegoly": pancerz_szczegoly,
    "czar_szczegoly": czar_szczegoly,
    "czary_tradycji": czary_tradycji,
    "szukaj_zasad": szukaj_zasad,
}


def run_tool(name: str, args: dict) -> dict:
    fn = DISPATCH.get(name)
    if not fn:
        return {"blad": f"nieznane narzędzie: {name}"}
    try:
        return fn(**args)
    except Exception as e:  # noqa: BLE001
        return {"blad": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    import json
    print("profesja_szczegoly('akolita'):")
    print(json.dumps(profesja_szczegoly("akolita"), ensure_ascii=False, indent=1))
    print("\nporownaj_ceche('WW','max'):")
    print(json.dumps(porownaj_ceche("WW", "max"), ensure_ascii=False, indent=1))
