#!/usr/bin/env python3
"""Zamienia strukturalne tabele (tables/*.json) na „fakt-karty":
  - `fact`  : zdanie po polsku z dokładnymi liczbami (do embeddingu w ChromaDB i do prozy),
  - `search`: słowa kluczowe do dopasowania w wyszukiwarce,
  - pola strukturalne do ładnego renderu (karta cech).

Wynik: data/tables/facts.json  (wstrzykiwany do strony mobilnej i bazy wektorowej).

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


def stat_phrase(stats, order):
    return ", ".join(f"{k} {stats[k]}" for k in order if stats.get(k, "—") != "—")


def profession_fact(p):
    parts = [f"{p['name']} — profesja {p['type']} (str. {p['page']})."]
    mp = stat_phrase(p["main"], MAIN_ORDER)
    sp = stat_phrase(p["secondary"], SEC_ORDER)
    if mp:
        parts.append(f"Modyfikatory cech głównych: {mp}.")
    if sp:
        parts.append(f"Cechy drugorzędne: {sp}.")
    if p.get("skills"):
        parts.append(f"Umiejętności: {p['skills']}.")
    if p.get("talents"):
        parts.append(f"Zdolności: {p['talents']}.")
    if p.get("trappings"):
        parts.append(f"Wyposażenie: {p['trappings']}.")
    if p.get("entries"):
        parts.append(f"Profesje wstępne: {p['entries']}.")
    if p.get("exits"):
        parts.append(f"Profesje wyjściowe: {p['exits']}.")
    return " ".join(parts)


def build_professions():
    path = os.path.join(TABLES, "professions.json")
    if not os.path.exists(path):
        return []
    facts = []
    for p in json.load(open(path, encoding="utf-8")):
        facts.append({
            "type": "profesja",
            "cat": p["type"],
            "name": p["name"],
            "page": p["page"],
            "search": f"{p['name']} profesja klasa cechy statystyki statystyk "
                      f"umiejętności zdolności wyposażenie {p['type']}",
            "fact": profession_fact(p),
            "main": p["main"],
            "secondary": p["secondary"],
            "skills": p.get("skills", ""),
            "talents": p.get("talents", ""),
            "trappings": p.get("trappings", ""),
            "entries": p.get("entries", ""),
            "exits": p.get("exits", ""),
        })
    return facts


def main():
    facts = []
    facts += build_professions()
    # tu dojdą: weapons, armour, items, spells, criticals, bestiary

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(facts, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    by_type = {}
    for f in facts:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1
    print(f"Fakt-kart: {len(facts)}  {by_type}  -> {OUT}")


if __name__ == "__main__":
    main()
