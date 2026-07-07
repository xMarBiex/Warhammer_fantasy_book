#!/usr/bin/env python3
"""Buduje zwarty DIGEST tabel do KONTEKSTU agenta (system prompt).

Agent dostaje ten tekst na wejściu = dane strukturalne (dokładne wartości) zawsze
pod ręką, deterministycznie. Prozę/zasady agent dobiera osobno z bazy wektorowej.

Wynik:
  data/tables/context_digest.md   — pełny digest (wszystkie pola)
  data/tables/context_index.md    — skrót (nazwa + cechy główne), do szybkiej referencji

    python scripts/build_digest.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TABLES = os.path.join(ROOT, "tables")
OUT_DIR = os.path.join(ROOT, "data", "tables")

MAIN = ["WW", "US", "K", "Odp", "Zr", "Int", "SW", "Ogd"]
SEC = ["A", "Żyw", "S", "Wt", "Sz", "Mag", "PO", "PP"]


def stat_inline(d, order):
    return ", ".join(f"{k} {d[k]}" for k in order if d.get(k, "—") != "—") or "—"


def professions_full():
    path = os.path.join(TABLES, "professions.json")
    if not os.path.exists(path):
        return "", ""
    profs = sorted(json.load(open(path, encoding="utf-8")),
                   key=lambda p: (p["type"] != "podstawowa", p["name"]))
    full, index = [], []
    for p in profs:
        head = f"### {p['name']} — profesja {p['type']} (str. {p['page']})"
        lines = [head,
                 f"Cechy główne: {stat_inline(p['main'], MAIN)}. "
                 f"Drugorzędne: {stat_inline(p['secondary'], SEC)}."]
        if p.get("skills"):    lines.append(f"Umiejętności: {p['skills']}.")
        if p.get("talents"):   lines.append(f"Zdolności: {p['talents']}.")
        if p.get("trappings"): lines.append(f"Wyposażenie: {p['trappings']}.")
        if p.get("entries"):   lines.append(f"Wejście: {p['entries']}.")
        if p.get("exits"):     lines.append(f"Wyjście: {p['exits']}.")
        if p.get("note"):      lines.append(f"Uwaga: {p['note']}.")
        full.append("\n".join(lines))
        index.append(f"- **{p['name']}** ({p['type']}, str. {p['page']}): "
                     f"{stat_inline(p['main'], MAIN)}")
    return "\n\n".join(full), "\n".join(index)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    prof_full, prof_index = professions_full()
    n = prof_full.count("### ")

    header = (
        "# Warhammer Fantasy Roleplay 2e — DIGEST TABEL (kontekst agenta)\n\n"
        "Dane strukturalne z Księgi Zasad — dokładne wartości do bezpośrednich odpowiedzi.\n"
        "Zasady/prozę dobieraj osobno z bazy wektorowej (narzędzie wyszukiwania).\n"
        "Modyfikatory cech (np. WW +5) to bonusy profesji do cech Bohatera. Numer strony = strona drukowana.\n\n"
        f"## Profesje ({n})\n\n"
    )
    full_md = header + prof_full + "\n"
    open(os.path.join(OUT_DIR, "context_digest.md"), "w", encoding="utf-8").write(full_md)

    index_md = (f"# Indeks profesji ({n}) — cechy główne\n\n" + prof_index + "\n")
    open(os.path.join(OUT_DIR, "context_index.md"), "w", encoding="utf-8").write(index_md)

    def toks(s):
        return round(len(s) / 4 / 1000, 1)
    print(f"Profesje: {n}")
    print(f"  context_digest.md : {len(full_md)/1024:.0f} KB  (~{toks(full_md)} K tokenów)")
    print(f"  context_index.md  : {len(index_md)/1024:.0f} KB  (~{toks(index_md)} K tokenów)")


if __name__ == "__main__":
    main()
