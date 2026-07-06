#!/usr/bin/env python3
"""Buduje samodzielną, mobilną stronę wyszukiwarki (do otwarcia w przeglądarce
telefonu, bez serwera).

Wstrzykuje treść fragmentów z data/text/chunks.jsonl w szablon
web/search_mobile.template.html i zapisuje web/search_mobile.html.

Wyszukiwanie działa po stronie przeglądarki (słowno-frazowe, odporne na
literówki OCR). To NIE jest pełne wyszukiwanie semantyczne (model e5 jest za
duży na przeglądarkę) — pełną wersję semantyczną daje scripts/webapp.py.

    python scripts/build_mobile.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    chunks_path = os.path.join(ROOT, "data", "text", "chunks.jsonl")
    tpl_path = os.path.join(ROOT, "web", "search_mobile.template.html")
    out_path = os.path.join(ROOT, "web", "search_mobile.html")

    rows = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rows.append({
                "t": re.sub(r"\s+", " ", r["text"]).strip(),
                "a": r["page_start"],
                "b": r["page_end"],
            })
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    tpl = open(tpl_path, encoding="utf-8").read()
    content = tpl.replace("__DATA__", data)

    # 1) wersja dla Artifacta (bez <head> — Artifact sam dokłada nagłówek)
    open(out_path, "w", encoding="utf-8").write(content)

    # 2) samodzielna wersja dla Cloudflare/telefonu — pełny dokument HTML
    #    z <meta charset="utf-8"> (bez tego polskie znaki się sypią)
    dist_dir = os.path.join(ROOT, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    full = (
        '<!doctype html>\n<html lang="pl">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '</head>\n<body>\n' + content + '\n</body>\n</html>\n'
    )
    dist_path = os.path.join(dist_dir, "index.html")
    open(dist_path, "w", encoding="utf-8").write(full)

    print(f"OK: {len(rows)} fragmentów")
    print(f"  Artifact  -> {out_path} ({len(content.encode('utf-8'))/1e6:.2f} MB)")
    print(f"  Cloudflare-> {dist_path} ({len(full.encode('utf-8'))/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
