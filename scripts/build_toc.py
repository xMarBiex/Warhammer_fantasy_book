#!/usr/bin/env python3
"""Parsuje spis treści z OCR i zapisuje mapę „temat -> strona" do data/text/toc.json.

Spis treści to gotowa, kuratorowana mapa sekcja->strona — używamy jej jako
najwyższej wagi w wyszukiwarce (nad nagłówkami i treścią).

Numery w spisie są DRUKOWANE; strony w bazie to arkusze PDF. Zweryfikowany
offset: druk N = arkusz PDF N+1 (np. „Trafienia krytyczne 138" -> PDF 139).

    python scripts/build_toc.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# strony PDF, na których jest spis treści (u nas: 3; w razie potrzeby dołóż 4)
TOC_PAGES = [3]
PRINT_TO_PDF = 1          # offset: PDF = druk + 1
MAX_PAGE = 266

LINE = re.compile(r"^(.*?[A-Za-zżźąćęłńóśŻŹĄĆĘŁŃÓŚ].*?)[\s.·•_—-]*?(\d{1,3})\s*$")


def clean_title(t):
    t = re.sub(r"[.·•_]{2,}", " ", t)           # ciągi kropek/wypełniaczy
    t = re.sub(r"\s+", " ", t).strip(" .-—_·•")
    return t


def main():
    entries = []
    seen = set()
    for pg in TOC_PAGES:
        fp = os.path.join(ROOT, "data", "text", "pages", f"page_{pg:04d}.txt")
        if not os.path.exists(fp):
            continue
        for line in open(fp, encoding="utf-8"):
            m = LINE.match(line.rstrip("\n"))
            if not m:
                continue
            printed = int(m.group(2))
            if not (1 <= printed <= MAX_PAGE):
                continue
            title = clean_title(m.group(1))
            # tytuł musi mieć sensowne słowo (>=4 litery)
            words = re.findall(r"[A-Za-zżźąćęłńóśŻŹĄĆĘŁŃÓŚ]{4,}", title)
            if not words:
                continue
            pdf = min(MAX_PAGE, printed + PRINT_TO_PDF)
            key = (title.lower(), pdf)
            if key in seen:
                continue
            seen.add(key)
            entries.append({"t": title, "p": pdf})

    # Spis treści jest rosnący po stronach. OCR czasem psuje numer (np. 128->179).
    # Zostawiamy najdłuższy niemalejący podciąg (po stronie) — spójny szkielet,
    # bez odstających numerów.
    n = len(entries)
    if n:
        dp = [1] * n
        prev = [-1] * n
        for i in range(n):
            for j in range(i):
                if entries[j]["p"] <= entries[i]["p"] and dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    prev[i] = j
        end = max(range(n), key=lambda i: dp[i])
        keep = []
        while end != -1:
            keep.append(end)
            end = prev[end]
        keep = set(keep)
        dropped = n - len(keep)
        entries = [e for i, e in enumerate(entries) if i in keep]
        print(f"(odfiltrowano {dropped} wpisów z odstającym numerem strony)")

    out = os.path.join(ROOT, "data", "text", "toc.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
    print(f"Wpisów spisu treści: {len(entries)} -> {out}")
    for e in entries[:25]:
        print(f"  str.{e['p']:>3}  {e['t']}")


if __name__ == "__main__":
    main()
