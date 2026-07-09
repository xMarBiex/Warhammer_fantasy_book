#!/usr/bin/env python3
"""Zamienia WSZYSTKIE strukturalne tabele (tables/*.json) na „fakt-karty":
  - `fact`  : zdanie po polsku z dokładnymi liczbami (do embeddingu w ChromaDB),
  - `search`: słowa kluczowe do dopasowania w wyszukiwarce mobilnej,
  - pola strukturalne do renderu (dla profesji karta cech).

Dzięki temu proza (chunki) i tabele są SPÓJNIE przeszukiwalne semantycznie:
wyszukiwarka/agent trafi na fakt tabelaryczny tak samo jak na fragment prozy.

Wynik: data/tables/facts.json  (wstrzykiwany do strony mobilnej i do bazy wektorowej).

    python scripts/build_facts.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TABLES = os.path.join(ROOT, "tables")
OUT = os.path.join(ROOT, "data", "tables", "facts.json")

MAIN_ORDER = ["WW", "US", "K", "Odp", "Zr", "Int", "SW", "Ogd"]
SEC_ORDER = ["A", "Żyw", "S", "Wt", "Sz", "Mag", "PO", "PP"]


def _load(name):
    path = os.path.join(TABLES, name)
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []


def stat_phrase(stats, order):
    return ", ".join(f"{k} {stats[k]}" for k in order if stats.get(k, "—") not in ("—", ""))


# ── Profesje ────────────────────────────────────────────────────────────────
def profession_fact(p):
    parts = [f"{p['name']} — profesja {p['type']} (str. {p['page']})."]
    mp = stat_phrase(p["main"], MAIN_ORDER)
    sp = stat_phrase(p["secondary"], SEC_ORDER)
    if mp:
        parts.append(f"Modyfikatory cech głównych: {mp}.")
    if sp:
        parts.append(f"Cechy drugorzędne: {sp}.")
    for label, key in [("Umiejętności", "skills"), ("Zdolności", "talents"),
                       ("Wyposażenie", "trappings"), ("Profesje wstępne", "entries"),
                       ("Profesje wyjściowe", "exits")]:
        if p.get(key):
            parts.append(f"{label}: {p[key]}.")
    return " ".join(parts)


def build_professions():
    out = []
    for p in _load("professions.json"):
        out.append({
            "type": "profesja", "cat": p["type"], "name": p["name"], "page": p["page"],
            "search": f"{p['name']} profesja klasa cechy statystyki statystyk "
                      f"umiejętności zdolności wyposażenie {p['type']}",
            "fact": profession_fact(p),
            "main": p["main"], "secondary": p["secondary"],
            "skills": p.get("skills", ""), "talents": p.get("talents", ""),
            "trappings": p.get("trappings", ""), "entries": p.get("entries", ""),
            "exits": p.get("exits", ""),
        })
    return out


# ── Oręż ──────────────────────────────────────────────────────────────────--
def build_weapons():
    out = []
    for w in _load("weapons.json"):
        seg = [f"{w['name']} — broń ({w['klasa']}), str. {w['page']}.",
               f"Obrażenia (siła broni): {w['sila_broni']}.",
               f"Cena: {w['cena']}. Obciążenie: {w['obciazenie']}. "
               f"Kategoria: {w['kategoria']}. Dostępność: {w['dostepnosc']}."]
        if w["klasa"] == "strzelecka":
            seg.append(f"Zasięg: {w['zasieg']}. Przeładowanie: {w['przeladowanie']}.")
        if w.get("cechy") and w["cechy"] != "brak":
            seg.append(f"Cechy oręża: {w['cechy']}.")
        out.append({"type": "broń", "name": w["name"], "page": w["page"],
                    "search": f"{w['name']} broń oręż obrażenia cena zasięg cechy",
                    "fact": " ".join(seg)})
    return out


# ── Pancerz ─────────────────────────────────────────────────────────────────
def build_armour():
    out = []
    for a in _load("armour.json"):
        out.append({"type": "pancerz", "name": f"{a['name']} ({a['material']})",
                    "page": a["page"],
                    "search": f"{a['name']} pancerz zbroja PZ punkty zbroi cena {a['material']}",
                    "fact": f"{a['name']} — pancerz {a['material']} (str. {a['page']}). "
                            f"Punkty Zbroi: {a['pz']}. Cena: {a['cena']}. "
                            f"Obciążenie: {a['obciazenie']}. Chronione lokacje: {a['lokacje']}. "
                            f"Dostępność: {a['dostepnosc']}."})
    return out


# ── Czary ─────────────────────────────────────────────────────────────────--
def build_spells():
    out = []
    for s in _load("spells.json"):
        seg = [f"{s['name']} — czar ({s['tradycja']}), str. {s['page']}.",
               f"Wymagany poziom mocy: {s['pm']}. Czas rzucania: {s['czas_rzucania']}."]
        if s.get("zasieg"):
            seg.append(f"Zasięg: {s['zasieg']}.")
        if s.get("czas_trwania"):
            seg.append(f"Czas trwania: {s['czas_trwania']}.")
        if s.get("skladnik"):
            seg.append(f"Składnik: {s['skladnik']}.")
        if s.get("opis"):
            seg.append(f"Efekt: {s['opis']}")
        out.append({"type": "czar", "name": s["name"], "page": s["page"],
                    "search": f"{s['name']} czar zaklęcie magia {s['tradycja']} "
                              f"poziom mocy składnik efekt",
                    "fact": " ".join(seg)})
    return out


# ── Ekwipunek i usługi ────────────────────────────────────────────────────--
def build_items():
    out = []
    for it in _load("items.json"):
        out.append({"type": "ekwipunek", "name": it["name"], "page": it["page"],
                    "search": f"{it['name']} cena koszt {it['kategoria']} ekwipunek",
                    "fact": f"{it['name']} — {it['kategoria']} (str. {it['page']}). "
                            f"Cena: {it['cena']}. Obciążenie: {it['obciazenie']}. "
                            f"Dostępność: {it['dostepnosc']}."})
    return out


# ── Bestiariusz ─────────────────────────────────────────────────────────────
def build_bestiary():
    out = []
    for c in _load("bestiary.json"):
        seg = [f"{c['name']} — profil z bestiariusza (str. {c['page']})."]
        mp = stat_phrase(c["main"], MAIN_ORDER)
        sp = stat_phrase(c["secondary"], SEC_ORDER)
        if mp:
            seg.append(f"Cechy główne: {mp}.")
        if sp:
            seg.append(f"Cechy drugorzędne: {sp}.")
        for label, key in [("Umiejętności", "skills"), ("Zdolności", "talents"),
                           ("Zasady specjalne", "special"), ("Zbroja", "armour"),
                           ("Punkty Zbroi", "armour_points"), ("Uzbrojenie", "weapons")]:
            if c.get(key):
                seg.append(f"{label}: {c[key]}.")
        out.append({"type": "potwór", "name": c["name"], "page": c["page"],
                    "search": f"{c['name']} potwór stwór bestiariusz cechy statystyki "
                              f"żywotność profil",
                    "fact": " ".join(seg)})
    return out


# ── Zasady (czysty tekst mechanik — obejście zaszumionej kursywy w OCR) ─────
def build_rules():
    out = []
    for r in _load("rules.json"):
        out.append({"type": "zasada", "name": r["name"], "page": r["page"],
                    "search": f"{r['name']} zasada mechanika {r['kategoria']}",
                    "fact": f"{r['name']} ({r['kategoria']}, str. {r['page']}). {r['text']}"})
    return out


def main():
    facts = []
    facts += build_professions()
    facts += build_rules()
    facts += build_weapons()
    facts += build_armour()
    facts += build_spells()
    facts += build_items()
    facts += build_bestiary()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(facts, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    by_type = {}
    for f in facts:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1
    print(f"Fakt-kart: {len(facts)}  {by_type}  -> {OUT}")


if __name__ == "__main__":
    main()
