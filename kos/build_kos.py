#!/usr/bin/env python3
"""Buduje bazę KOS (Warstwa 2 Graf + Warstwa 3 SQL + Metadane) z tabel źródłowych.

Materializuje `tables/professions.json` do SQLite `data/kos/kos.db`:
  • węzły Profession (+ węzeł Book)               → Warstwa 2 (Graf)
  • profession_stats (dokładne modyfikatory cech) → Warstwa 3 (SQL)
  • krawędzie ADVANCES_TO (siatka rozwoju profesji) + DEFINED_IN
  • każdy fakt ma źródło, stronę, edycję, pewność  → Metadata / Confidence Engine

Bez zależności zewnętrznych (stdlib sqlite3). Idempotentny: przebudowuje od zera.

    python kos/build_kos.py
"""
import json
import os
import sqlite3
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCHEMA = os.path.join(HERE, "schema.sql")
TABLES = os.path.join(ROOT, "tables")
DB_DIR = os.path.join(ROOT, "data", "kos")
DB_PATH = os.path.join(DB_DIR, "kos.db")

SOURCE = {
    "id": "ksiega-zasad-2e",
    "book": "Warhammer Fantasy Roleplay — Księga Zasad",
    "edition": "2",
    "system": "WFRP",
    "language": "pl",
    "author": None,
    "notes": "Skan OCR + ręczna ekstrakcja tabel.",
}

MAIN = ["WW", "US", "K", "Odp", "Zr", "Int", "SW", "Ogd"]
SEC = ["A", "Żyw", "S", "Wt", "Sz", "Mag", "PO", "PP"]
# klucze kolumn SQL (bez polskich znaków dla „Żyw")
SEC_COL = {"Żyw": "Zyw"}


def fold(s):
    """Nazwa → lowercase bez polskich znaków (do dopasowań i id węzłów)."""
    s = s.strip().lower().replace("ł", "l")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def node_id(prefix, name):
    return f"{prefix}:{fold(name).replace(' ', '_')}"


# Nazwy w polach wejść/wyjść, które NIE są profesjami (klimatyczne zakończenia
# kariery — np. „chwalebna śmierć!" jako jedyne wyjście Berserkera). Nie tworzą
# węzłów ani luk w grafie.
NON_ENTITIES = {"chwalebna śmierć!"}
_NON = {n.strip().lower().replace("ł", "l") for n in NON_ENTITIES}


def split_names(field):
    """'a, b, c' -> ['a','b','c']; 'brak'/'' -> []; pomija nie-encje."""
    if not field or field.strip().lower() == "brak":
        return []
    out = []
    for x in field.split(","):
        x = x.strip()
        if x and x.lower().replace("ł", "l") not in _NON:
            out.append(x)
    return out


def build():
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.executescript(open(SCHEMA, encoding="utf-8").read())

    # Źródło + węzeł Book
    con.execute(
        "INSERT INTO sources(id,book,edition,system,language,author,notes) "
        "VALUES(:id,:book,:edition,:system,:language,:author,:notes)", SOURCE)
    book_id = node_id("book", SOURCE["id"])
    con.execute(
        "INSERT INTO nodes(id,type,name,name_fold,data,source_id,page,confidence) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (book_id, "Book", SOURCE["book"], fold(SOURCE["book"]),
         json.dumps(SOURCE, ensure_ascii=False), SOURCE["id"], None, 1.0))

    profs = json.load(open(os.path.join(TABLES, "professions.json"), encoding="utf-8"))

    # 1) Węzły + statystyki (Warstwa 2 + 3)
    for p in profs:
        nid = node_id("prof", p["name"])
        con.execute(
            "INSERT OR REPLACE INTO nodes"
            "(id,type,name,name_fold,data,source_id,page,confidence) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (nid, "Profession", p["name"], fold(p["name"]),
             json.dumps(p, ensure_ascii=False), SOURCE["id"], p["page"], 0.95))

        cols = ["node_id", "name", "kind", "page"]
        vals = [nid, p["name"], p["type"], p["page"]]
        for k in MAIN:
            cols.append(k); vals.append(p["main"].get(k, "—"))
        for k in SEC:
            cols.append(SEC_COL.get(k, k)); vals.append(p["secondary"].get(k, "—"))
        for k in ("skills", "talents", "trappings"):
            cols.append(k); vals.append(p.get(k, ""))
        cols += ["source_id", "confidence"]; vals += [SOURCE["id"], 0.95]
        con.execute(
            f"INSERT OR REPLACE INTO profession_stats({','.join(cols)}) "
            f"VALUES({','.join('?' * len(vals))})", vals)

        # DEFINED_IN  (profesja -> książka)
        con.execute(
            "INSERT OR IGNORE INTO edges(src,rel,dst,source_id,page,confidence) "
            "VALUES(?,?,?,?,?,?)",
            (nid, "DEFINED_IN", book_id, SOURCE["id"], p["page"], 1.0))

    # ── Oręż (Warstwa 2 węzły + Warstwa 3 SQL) ─────────────────────────────
    wpath = os.path.join(TABLES, "weapons.json")
    n_weapons = 0
    if os.path.exists(wpath):
        wcols = ["node_id", "name", "klasa", "page", "cena", "obciazenie",
                 "kategoria", "sila_broni", "zasieg", "przeladowanie", "cechy",
                 "dostepnosc", "dwureczna", "source_id", "confidence"]
        for w in json.load(open(wpath, encoding="utf-8")):
            wid = node_id("bron", w["name"])
            con.execute(
                "INSERT OR REPLACE INTO nodes"
                "(id,type,name,name_fold,data,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (wid, "Weapon", w["name"], fold(w["name"]),
                 json.dumps(w, ensure_ascii=False), SOURCE["id"], w["page"], 0.95))
            con.execute(
                f"INSERT OR REPLACE INTO weapon_stats({','.join(wcols)}) "
                f"VALUES({','.join('?' * len(wcols))})",
                (wid, w["name"], w["klasa"], w["page"], w["cena"], w["obciazenie"],
                 w["kategoria"], w["sila_broni"], w["zasieg"], w["przeladowanie"],
                 w["cechy"], w["dostepnosc"], 1 if w.get("dwureczna") else 0,
                 SOURCE["id"], 0.95))
            con.execute(
                "INSERT OR IGNORE INTO edges(src,rel,dst,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?)",
                (wid, "DEFINED_IN", book_id, SOURCE["id"], w["page"], 1.0))
            n_weapons += 1

    # ── Pancerz (Warstwa 2 węzły + Warstwa 3 SQL) ──────────────────────────
    apath = os.path.join(TABLES, "armour.json")
    n_armour = 0
    if os.path.exists(apath):
        acols = ["node_id", "name", "material", "page", "cena", "obciazenie",
                 "lokacje", "pz", "dostepnosc", "source_id", "confidence"]
        for a in json.load(open(apath, encoding="utf-8")):
            # nazwy powtarzają się między materiałami -> id zawiera materiał
            aid = node_id("pancerz", f"{a['name']} {a['material']}")
            disp = f"{a['name']} ({a['material']})"
            con.execute(
                "INSERT OR REPLACE INTO nodes"
                "(id,type,name,name_fold,data,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (aid, "Armour", disp, fold(a["name"]),
                 json.dumps(a, ensure_ascii=False), SOURCE["id"], a["page"], 0.95))
            con.execute(
                f"INSERT OR REPLACE INTO armour_stats({','.join(acols)}) "
                f"VALUES({','.join('?' * len(acols))})",
                (aid, a["name"], a["material"], a["page"], a["cena"],
                 a["obciazenie"], a["lokacje"], a["pz"], a["dostepnosc"],
                 SOURCE["id"], 0.95))
            con.execute(
                "INSERT OR IGNORE INTO edges(src,rel,dst,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?)",
                (aid, "DEFINED_IN", book_id, SOURCE["id"], a["page"], 1.0))
            n_armour += 1

    # ── Czary (Warstwa 2 węzły Spell + MagicLore + BELONGS_TO; Warstwa 3 SQL) ─
    spath = os.path.join(TABLES, "spells.json")
    n_spells = 0
    lore_ids = set()
    if os.path.exists(spath):
        scols = ["node_id", "name", "tradycja", "pm", "czas_rzucania", "zasieg",
                 "czas_trwania", "skladnik", "opis", "page", "source_id", "confidence"]
        for s in json.load(open(spath, encoding="utf-8")):
            sid = node_id("czar", s["name"])
            lid = node_id("magia", s["tradycja"])
            if lid not in lore_ids:  # węzeł tradycji magii
                con.execute(
                    "INSERT OR REPLACE INTO nodes"
                    "(id,type,name,name_fold,data,source_id,page,confidence) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (lid, "MagicLore", s["tradycja"], fold(s["tradycja"]),
                     json.dumps({"tradycja": s["tradycja"]}, ensure_ascii=False),
                     SOURCE["id"], s["page"], 0.95))
                lore_ids.add(lid)
            con.execute(
                "INSERT OR REPLACE INTO nodes"
                "(id,type,name,name_fold,data,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (sid, "Spell", s["name"], fold(s["name"]),
                 json.dumps(s, ensure_ascii=False), SOURCE["id"], s["page"], 0.95))
            con.execute(
                f"INSERT OR REPLACE INTO spell_stats({','.join(scols)}) "
                f"VALUES({','.join('?' * len(scols))})",
                (sid, s["name"], s["tradycja"], s["pm"], s["czas_rzucania"],
                 s["zasieg"], s["czas_trwania"], s["skladnik"], s["opis"],
                 s["page"], SOURCE["id"], 0.95))
            con.execute(  # czar -> tradycja
                "INSERT OR IGNORE INTO edges(src,rel,dst,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?)",
                (sid, "BELONGS_TO", lid, SOURCE["id"], s["page"], 0.95))
            con.execute(  # czar -> książka
                "INSERT OR IGNORE INTO edges(src,rel,dst,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?)",
                (sid, "DEFINED_IN", book_id, SOURCE["id"], s["page"], 1.0))
            n_spells += 1

    # ── Ekwipunek i usługi (Warstwa 2 węzły + Warstwa 3 SQL) ───────────────
    ipath = os.path.join(TABLES, "items.json")
    n_items = 0
    if os.path.exists(ipath):
        icols = ["node_id", "name", "kategoria", "cena", "obciazenie",
                 "dostepnosc", "page", "source_id", "confidence"]
        for it in json.load(open(ipath, encoding="utf-8")):
            iid = node_id("ekw", f"{it['name']} {it['kategoria']}")
            con.execute(
                "INSERT OR REPLACE INTO nodes"
                "(id,type,name,name_fold,data,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (iid, "Item", it["name"], fold(it["name"]),
                 json.dumps(it, ensure_ascii=False), SOURCE["id"], it["page"], 0.95))
            con.execute(
                f"INSERT OR REPLACE INTO item_costs({','.join(icols)}) "
                f"VALUES({','.join('?' * len(icols))})",
                (iid, it["name"], it["kategoria"], it["cena"], it["obciazenie"],
                 it["dostepnosc"], it["page"], SOURCE["id"], 0.95))
            con.execute(
                "INSERT OR IGNORE INTO edges(src,rel,dst,source_id,page,confidence) "
                "VALUES(?,?,?,?,?,?)",
                (iid, "DEFINED_IN", book_id, SOURCE["id"], it["page"], 1.0))
            n_items += 1

    # indeks nazwa-fold -> id (do rozwiązywania krawędzi po nazwie)
    idx = {fold(p["name"]): node_id("prof", p["name"]) for p in profs}

    # 2) Krawędzie ADVANCES_TO — siatka rozwoju profesji (Warstwa 2, sedno grafu)
    #    exits:   A -> B   (z A można awansować do B)
    #    entries: C -> A   (do A wchodzi się z C)  [wiedza z drugiej strony tabeli]
    def add_edge(s, d, dname, page):
        con.execute(
            "INSERT OR IGNORE INTO edges"
            "(src,rel,dst,dst_name,source_id,page,confidence) VALUES(?,?,?,?,?,?,?)",
            (s, "ADVANCES_TO", d, dname, SOURCE["id"], page, 0.9))

    for p in profs:
        src = node_id("prof", p["name"])
        # exits: current -> B  (B może być spoza tabeli -> dst_name)
        for name in split_names(p.get("exits", "")):
            dst = idx.get(fold(name))
            add_edge(src, dst or "", "" if dst else name, p["page"])
        # entries: A -> current  (tylko gdy A jest w tabeli; brakujące złapią się
        # jako exit z A po jej ekstrakcji — nie tworzymy węzłów-widm)
        for name in split_names(p.get("entries", "")):
            other = idx.get(fold(name))
            if other:
                add_edge(other, src, "", p["page"])

    con.commit()

    n_nodes = con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    n_edges = con.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    n_stats = con.execute("SELECT COUNT(*) FROM profession_stats").fetchone()[0]
    missing = con.execute(
        "SELECT DISTINCT dst_name FROM edges "
        "WHERE rel='ADVANCES_TO' AND dst='' AND dst_name<>'' ORDER BY dst_name"
    ).fetchall()
    con.close()

    print(f"KOS zbudowany -> {DB_PATH}")
    print(f"  węzły:      {n_nodes}  (Book + {n_stats} prof. + {n_weapons} oręża + "
          f"{n_armour} pancerzy + {n_spells} czarów + {len(lore_ids)} tradycji + {n_items} ekw.)")
    print(f"  krawędzie:  {n_edges}  (ADVANCES_TO + DEFINED_IN + BELONGS_TO)")
    print(f"  SQL:        {n_stats} profesji, {n_weapons} oręża, {n_armour} pancerzy, "
          f"{n_spells} czarów, {n_items} ekwipunku (Warstwa 3)")
    if missing:
        names = ", ".join(m[0] for m in missing)
        print(f"  ⚠ Validation Agent: {len(missing)} profesji wskazywanych w siatce "
              f"rozwoju, których BRAK w tabeli: {names}")


if __name__ == "__main__":
    build()
