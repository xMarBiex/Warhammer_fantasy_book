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


def split_names(field):
    """'a, b, c' -> ['a','b','c']; 'brak'/'' -> []."""
    if not field or field.strip().lower() == "brak":
        return []
    return [x.strip() for x in field.split(",") if x.strip()]


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
    print(f"  węzły:      {n_nodes}  (Book + {n_stats} profesji)")
    print(f"  krawędzie:  {n_edges}  (ADVANCES_TO + DEFINED_IN)")
    print(f"  statystyki: {n_stats} profesji (Warstwa SQL)")
    if missing:
        names = ", ".join(m[0] for m in missing)
        print(f"  ⚠ Validation Agent: {len(missing)} profesji wskazywanych w siatce "
              f"rozwoju, których BRAK w tabeli: {names}")


if __name__ == "__main__":
    build()
