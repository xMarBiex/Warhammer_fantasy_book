#!/usr/bin/env python3
"""Eksportuje warstwę strukturalną KOS (SQL+Graf) do samodzielnej strony HTML
do testów (offline w przeglądarce, wdrażalna na Cloudflare Pages).

Czyta data/kos/kos.db (węzły Profession + siatka rozwoju), wstrzykuje dane do
web/kos.template.html i zapisuje:
  web/kos.html      — bez <head> (do publikacji jako Artifact)
  dist/index.html   — pełny dokument z <meta charset> (Cloudflare/telefon)

    python kos/export_web.py
"""
import json
import os
import sqlite3
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "data", "kos", "kos.db")
TPL = os.path.join(ROOT, "web", "kos.template.html")

MAIN = ["WW", "US", "K", "Odp", "Zr", "Int", "SW", "Ogd"]
SEC = ["A", "Żyw", "S", "Wt", "Sz", "Mag", "PO", "PP"]
SECK = {"Żyw": "Zyw"}


def fold(s):
    s = (s or "").strip().lower().replace("ł", "l")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def split_names(field):
    if not field or field.strip().lower() == "brak":
        return []
    return [x.strip() for x in field.split(",") if x.strip()]


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id,name,name_fold,page,data FROM nodes WHERE type='Profession'"
    ).fetchall()
    exist = {r["name_fold"] for r in rows}

    profs, missing = [], set()
    for r in sorted(rows, key=lambda x: x["name"]):
        rec = json.loads(r["data"])

        def split(field):
            ok, miss = [], []
            for n in split_names(rec.get(field, "")):
                (ok if fold(n) in exist else miss).append(cap(n))
            for n in split_names(rec.get(field, "")):
                if fold(n) not in exist:
                    missing.add(cap(n))
            return ok, miss

        in_ok, in_miss = split("entries")
        out_ok, out_miss = split("exits")
        profs.append({
            "id": r["id"], "name": rec["name"], "kind": rec["type"], "page": rec["page"],
            "main": {k: rec["main"].get(k, "—") for k in MAIN},
            "sec": {SECK.get(k, k): rec["secondary"].get(k, "—") for k in SEC},
            "skills": rec.get("skills", ""), "talents": rec.get("talents", ""),
            "trappings": rec.get("trappings", ""),
            "inOk": in_ok, "inMiss": in_miss, "outOk": out_ok, "outMiss": out_miss,
        })

    src = con.execute("SELECT book,edition FROM sources LIMIT 1").fetchone()
    con.close()

    payload = {
        "source": f"{src['book']} (wyd. {src['edition']})" if src else "Księga Zasad 2e",
        "profs": profs,
        "missing": sorted(missing),
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    content = open(TPL, encoding="utf-8").read().replace("__DATA__", data)
    out = os.path.join(ROOT, "web", "kos.html")
    open(out, "w", encoding="utf-8").write(content)

    dist_dir = os.path.join(ROOT, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    full = ('<!doctype html>\n<html lang="pl">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '</head>\n<body>\n' + content + '\n</body>\n</html>\n')
    dist = os.path.join(dist_dir, "index.html")
    open(dist, "w", encoding="utf-8").write(full)

    print(f"Profesje: {len(profs)} · luki KOS: {len(payload['missing'])} "
          f"({', '.join(payload['missing'])})")
    print(f"  Artifact  -> {out} ({len(content.encode())/1024:.0f} KB)")
    print(f"  Cloudflare-> {dist} ({len(full.encode())/1024:.0f} KB)")


if __name__ == "__main__":
    main()
