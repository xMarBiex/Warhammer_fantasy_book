#!/usr/bin/env python3
"""Eksportuje CAŁĄ warstwę strukturalną KOS (SQL + Graf) do samodzielnej strony
HTML do testów (offline w przeglądarce, wdrażalna na Cloudflare Pages).

Obejmuje: profesje (z siatką rozwoju), broń, pancerz, czary (z tradycjami),
ekwipunek/usługi, bestiariusz oraz graf zależności (umiejętność/zdolność ->
kto ją posiada). Czyta data/kos/kos.db, wstrzykuje dane do web/kos.template.html.

Wynik:
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
    return [x.strip() for x in field.split(",")
            if x.strip() and fold(x) != "chwalebna smierc!"]


def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    q = lambda sql: [dict(r) for r in con.execute(sql).fetchall()]

    # ── Profesje (+ siatka rozwoju z grafu) ───────────────────────────────
    prof_rows = con.execute(
        "SELECT id,name,name_fold,page,data FROM nodes WHERE type='Profession'").fetchall()
    exist = {r["name_fold"] for r in prof_rows}
    profs, missing = [], set()
    for r in sorted(prof_rows, key=lambda x: x["name"]):
        rec = json.loads(r["data"])

        def split(field):
            ok, miss = [], []
            for n in split_names(rec.get(field, "")):
                (ok if fold(n) in exist else miss).append(n[:1].upper() + n[1:])
            for n in split_names(rec.get(field, "")):
                if fold(n) not in exist:
                    missing.add(n[:1].upper() + n[1:])
            return ok, miss

        in_ok, in_miss = split("entries")
        out_ok, out_miss = split("exits")
        profs.append({
            "name": rec["name"], "kind": rec["type"], "page": rec["page"],
            "main": {k: rec["main"].get(k, "—") for k in MAIN},
            "sec": {SECK.get(k, k): rec["secondary"].get(k, "—") for k in SEC},
            "skills": rec.get("skills", ""), "talents": rec.get("talents", ""),
            "trappings": rec.get("trappings", ""),
            "inOk": in_ok, "inMiss": in_miss, "outOk": out_ok, "outMiss": out_miss,
        })

    # ── Broń / pancerz / ekwipunek ────────────────────────────────────────
    weapons = q("SELECT name,klasa,page,cena,obciazenie,kategoria,sila_broni,"
                "zasieg,przeladowanie,cechy,dostepnosc,dwureczna FROM weapon_stats "
                "ORDER BY name")
    armour = q("SELECT name,material,page,cena,obciazenie,lokacje,pz,dostepnosc "
               "FROM armour_stats ORDER BY name")
    items = q("SELECT name,kategoria,cena,obciazenie,dostepnosc,page FROM item_costs "
              "ORDER BY name")

    # ── Czary (+ mapa tradycja -> [{name,pm}]) ─────────────────────────────
    spells = q("SELECT name,tradycja,pm,czas_rzucania,zasieg,czas_trwania,skladnik,"
               "opis,page FROM spell_stats ORDER BY name")
    traditions = {}
    for s in sorted(spells, key=lambda x: (x["tradycja"], x["pm"])):
        traditions.setdefault(s["tradycja"], []).append(
            {"name": s["name"], "pm": s["pm"]})

    # ── Bestiariusz ───────────────────────────────────────────────────────
    best = []
    for r in con.execute("SELECT * FROM bestiary_profiles ORDER BY name"):
        d = dict(r)
        best.append({
            "name": d["name"], "page": d["page"],
            "main": {k: d[k] for k in MAIN},
            "sec": {SECK.get(k, k): d[SECK.get(k, k)] for k in SEC},
            "skills": d["skills"], "talents": d["talents"], "special": d["special"],
            "armour": d["armour"], "pz": d["armour_points"], "weapons": d["weapons"],
        })

    # ── Graf zależności: umiejętność/zdolność -> kto ją ma ─────────────────
    def who(typ, rel):
        out = {}
        rows = con.execute("SELECT id,name FROM nodes WHERE type=?", (typ,)).fetchall()
        for n in rows:
            src = con.execute(
                "SELECT s.name AS name, s.type AS type FROM edges e "
                "JOIN nodes s ON s.id=e.src WHERE e.dst=? AND e.rel=? "
                "ORDER BY s.type, s.name", (n["id"], rel)).fetchall()
            out[n["name"]] = {
                "prof": [r["name"] for r in src if r["type"] == "Profession"],
                "creat": [r["name"] for r in src if r["type"] == "Creature"],
            }
        return out

    skills = who("Skill", "HAS_SKILL")
    talents = who("Talent", "HAS_TALENT")

    src = con.execute("SELECT book,edition FROM sources LIMIT 1").fetchone()
    con.close()

    payload = {
        "source": f"{src['book']} (wyd. {src['edition']})" if src else "Księga Zasad 2e",
        "profs": profs, "weapons": weapons, "armour": armour, "items": items,
        "spells": spells, "traditions": traditions, "bestiary": best,
        "skills": skills, "talents": talents, "missing": sorted(missing),
        "counts": {"profesje": len(profs), "broń": len(weapons), "pancerz": len(armour),
                   "czary": len(spells), "ekwipunek": len(items), "potwory": len(best),
                   "umiejętności": len(skills), "zdolności": len(talents)},
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

    print("Eksport KOS ->", payload["counts"])
    print(f"  Artifact  -> {out} ({len(content.encode())/1024:.0f} KB)")
    print(f"  Cloudflare-> {dist} ({len(full.encode())/1024:.0f} KB)")


if __name__ == "__main__":
    main()
