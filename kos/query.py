#!/usr/bin/env python3
"""KOS — Reasoning Engine (Warstwa 5) + dostęp do warstw SQL/Graf.

Rdzeń „cyfrowego eksperta": klasyfikuje zapytanie, wybiera warstwy, zwraca
odpowiedź WRAZ ZE ŹRÓDŁEM i POZIOMEM PEWNOŚCI (Confidence Engine). Liczby zawsze
z SQL, relacje z grafu — nigdy z modelu.

Użycie z CLI:
    python kos/query.py "statystyki akolita"
    python kos/query.py "z kogo można awansować na kapłana"
    python kos/query.py "która profesja ma największą modyfikację WW"

Import w agencie:
    from kos.query import KOS
    kos = KOS(); kos.answer("statystyki akolita")
"""
import json
import os
import re
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "data", "kos", "kos.db")

MAIN = ["WW", "US", "K", "Odp", "Zr", "Int", "SW", "Ogd"]
SEC = ["A", "Zyw", "S", "Wt", "Sz", "Mag", "PO", "PP"]
STAT_ALIASES = {  # nazwa cechy w pytaniu -> kolumna SQL
    "ww": "WW", "walka wrecz": "WW", "us": "US", "umiejetnosci strzeleckie": "US",
    "k": "K", "krzepa": "K", "odp": "Odp", "odpornosc": "Odp", "zr": "Zr",
    "zrecznosc": "Zr", "int": "Int", "inteligencja": "Int", "sw": "SW",
    "sila woli": "SW", "ogd": "Ogd", "oglada": "Ogd", "a": "A", "ataki": "A",
    "zyw": "Zyw", "zywotnosc": "Zyw", "s": "S", "sila": "S", "wt": "Wt",
    "wytrzymalosc": "Wt", "sz": "Sz", "szybkosc": "Sz", "mag": "Mag",
    "magia": "Mag", "po": "PO", "pp": "PP",
}

# słowa-klucze do klasyfikacji zapytań (Warstwa 5 — system planowania)
KIND_PATTERNS = [
    ("COMPARISON", r"najwi[ęe]ksz|najmniejsz|najlepsz|najwy[żz]sz|wi[ęe]cej|"
                   r"por[óo]wnaj|kt[óo]ra .* ma"),
    ("STRATEGY", r"strategi|taktyk|kontruj|najlepiej radzi|synergi|przeciwko"),
    ("EXPLANATION", r"wyja[śs]nij|jak dzia[łl]a|dlaczego|co to|zasad[ay]"),
    ("FACT", r"statystyk|cechy|ile|cena|obra[żz]enia|str\.|strona|awans|"
             r"wej[śs]ci|wyj[śs]ci|z kogo|do kogo"),
]


def fold(s):
    s = (s or "").strip().lower().replace("ł", "l")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def stat_key(v):
    """'+10'->10, '+5'->5, '—'/''->None. Do porównań liczbowych."""
    if not v or v == "—":
        return None
    m = re.search(r"[-+]?\d+", v)
    return int(m.group()) if m else None


class KOS:
    def __init__(self, db_path=DB_PATH):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Brak bazy KOS: {db_path} — uruchom kos/build_kos.py")
        self.con = sqlite3.connect(db_path)
        self.con.row_factory = sqlite3.Row

    # ── klasyfikacja (Warstwa 5) ──────────────────────────────────────────
    def classify(self, q):
        f = fold(q)
        for kind, pat in KIND_PATTERNS:
            if re.search(pat, f):
                return kind
        return "RESEARCH"

    # ── rozwiązywanie encji ───────────────────────────────────────────────
    def resolve_profession(self, q):
        """Znajdź profesję wspomnianą w zapytaniu (najdłuższe dopasowanie nazwy)."""
        f = fold(q)
        rows = self.con.execute(
            "SELECT node_id,name FROM profession_stats").fetchall()
        hits = [r for r in rows if fold(r["name"]) in f]
        if not hits:
            return None
        return max(hits, key=lambda r: len(r["name"]))["node_id"]

    # ── Warstwa 3 (SQL): dokładne cechy ───────────────────────────────────
    def profession_stats(self, node_id):
        r = self.con.execute(
            "SELECT * FROM profession_stats WHERE node_id=?", (node_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        return {
            "name": d["name"], "kind": d["kind"], "page": d["page"],
            "main": {k: d[k] for k in MAIN},
            "secondary": {k: d[k] for k in SEC},
            "skills": d["skills"], "talents": d["talents"], "trappings": d["trappings"],
            "source": "Księga Zasad 2e", "confidence": d["confidence"],
        }

    # ── Warstwa 2 (Graf): siatka rozwoju ──────────────────────────────────
    def career_neighbors(self, node_id):
        exits = self.con.execute(
            "SELECT COALESCE(n.name, e.dst_name) AS name, e.confidence "
            "FROM edges e LEFT JOIN nodes n ON n.id=e.dst "
            "WHERE e.src=? AND e.rel='ADVANCES_TO' ORDER BY name", (node_id,)).fetchall()
        entries = self.con.execute(
            "SELECT n.name AS name, e.confidence FROM edges e JOIN nodes n ON n.id=e.src "
            "WHERE e.dst=? AND e.rel='ADVANCES_TO' ORDER BY name", (node_id,)).fetchall()
        return ([dict(r) for r in entries], [dict(r) for r in exits])

    # ── Warstwa 3 (SQL): oręż ─────────────────────────────────────────────
    def resolve_weapon(self, q):
        f = fold(q)
        rows = self.con.execute("SELECT node_id,name FROM weapon_stats").fetchall()
        hits = [r for r in rows if fold(r["name"]) in f]
        if not hits:
            return None
        return max(hits, key=lambda r: len(r["name"]))["node_id"]

    def weapon_details(self, node_id):
        r = self.con.execute(
            "SELECT * FROM weapon_stats WHERE node_id=?", (node_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["dwureczna"] = bool(d["dwureczna"])
        d["source"] = "Księga Zasad 2e (Tabela 5-4/5-5, str. 110)"
        return d

    # ── COMPARISON: ekstremum cechy przez SQL ─────────────────────────────
    def stat_extreme(self, stat_col, biggest=True):
        rows = self.con.execute(
            f"SELECT name, {stat_col} AS v, page FROM profession_stats").fetchall()
        scored = [(r["name"], r["v"], r["page"], stat_key(r["v"]))
                  for r in rows]
        scored = [s for s in scored if s[3] is not None]
        if not scored:
            return []
        best = max(s[3] for s in scored) if biggest else min(s[3] for s in scored)
        return [{"name": n, "value": v, "page": p}
                for (n, v, p, k) in sorted(scored) if k == best]

    def find_stat_col(self, q):
        f = fold(q)
        best = None
        for alias, col in STAT_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", f) and (best is None or len(alias) > best[0]):
                best = (len(alias), col)
        return best[1] if best else None

    # ── fasada: klasyfikuj -> wykonaj -> odpowiedź z pewnością ─────────────
    def answer(self, q):
        kind = self.classify(q)
        out = {"query": q, "type": kind, "layers": [], "confidence": None,
               "source": None, "result": None, "note": None}

        if kind == "COMPARISON":
            col = self.find_stat_col(q) or "WW"
            biggest = not re.search(r"najmniejsz|najni[żz]sz", fold(q))
            res = self.stat_extreme(col, biggest)
            out.update(layers=["SQL"], result={"stat": col, "extreme": res},
                       confidence=0.95, source="Księga Zasad 2e (tabele cech)")
            return out

        nid = self.resolve_profession(q)
        if nid:
            stats = self.profession_stats(nid)
            entries, exits = self.career_neighbors(nid)
            out.update(layers=["SQL", "Graf"],
                       result={"stats": stats, "entries": entries, "exits": exits},
                       confidence=stats["confidence"] if stats else 0.9,
                       source="Księga Zasad 2e")
            if kind in ("EXPLANATION", "RESEARCH"):
                out["note"] = ("Prozę/interpretację dobierz z bazy wektorowej "
                               "(Warstwa 4) — tu tylko dane strukturalne.")
            return out

        out.update(note="Encji nie ma w warstwie strukturalnej — użyj bazy "
                        "wektorowej (Warstwa 4) do prozy/lore.", confidence=None)
        return out


def _fmt(a):
    lines = [f"[{a['type']}]  warstwy: {', '.join(a['layers']) or '—'}"]
    r = a.get("result")
    if r and "stats" in r and r["stats"]:
        s = r["stats"]
        lines.append(f"\n{s['name']} — profesja {s['kind']} (str. {s['page']})")
        lines.append("  Główne:  " + ", ".join(
            f"{k} {v}" for k, v in s["main"].items() if v != "—"))
        lines.append("  Drugorz.:" + ", ".join(
            f" {k} {v}" for k, v in s["secondary"].items() if v != "—"))
        if s["skills"]:
            lines.append(f"  Umiejętności: {s['skills']}")
        ent = ", ".join(e["name"] for e in r["entries"]) or "brak"
        ex = ", ".join(e["name"] for e in r["exits"]) or "brak"
        lines.append(f"  ← wejście z: {ent}")
        lines.append(f"  → wyjście do: {ex}")
    if r and "extreme" in r:
        lines.append(f"\nEkstremum cechy {r['stat']}:")
        for x in r["extreme"]:
            lines.append(f"  {x['name']}: {x['value']}  (str. {x['page']})")
    if a.get("note"):
        lines.append(f"\nℹ {a['note']}")
    if a.get("confidence") is not None:
        lines.append(f"\nŹródło: {a['source']}  ·  pewność: {a['confidence']:.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "statystyki akolita"
    print(_fmt(KOS().answer(q)))
