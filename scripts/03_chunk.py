#!/usr/bin/env python3
"""Krok 3: czyszczenie tekstu OCR + podział na fragmenty (chunki) z metadanymi.

Wejście : data/text/pages/page_NNNN.txt
Wyjście : data/text/chunks.jsonl  -> {id, text, page_start, page_end, n_chars}

Chunki są pakowane akapitami do docelowego rozmiaru, z zakładką (overlap),
i pamiętają z których stron pochodzą (do cytowania w odpowiedziach RAG).

    python scripts/03_chunk.py
    python scripts/03_chunk.py --target 1100 --overlap 200
"""
import argparse
import glob
import json
import os
import re

# Łączenie wyrazów przeniesionych myślnikiem na końcu wiersza: "sło-\nwo" -> "słowo"
DEHYPHEN = re.compile(r"(\w)-\n(\w)")


def clean_page(txt):
    txt = txt.replace("\r\n", "\n")
    txt = DEHYPHEN.sub(r"\1\2", txt)
    # pojedyncze złamania wiersza -> spacja; podwójne (akapit) zostają
    txt = re.sub(r"[ \t]*\n[ \t]*\n[ \t]*", "\n\n", txt)
    txt = re.sub(r"(?<!\n)\n(?!\n)", " ", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()


def paragraphs(out_dir):
    """Zwraca listę (page, akapit) w kolejności książki."""
    files = sorted(glob.glob(os.path.join(out_dir, "pages", "page_*.txt")))
    paras = []
    for fp in files:
        page = int(re.search(r"page_(\d+)", fp).group(1))
        with open(fp, encoding="utf-8") as f:
            txt = clean_page(f.read())
        if not txt:
            continue
        pending = ""  # krótkie linie (nagłówki np. „Akolita —") doklejamy do następnego akapitu
        for p in txt.split("\n\n"):
            p = p.strip()
            if not p or p.isdigit():        # pomijamy puste i czyste numery stron
                continue
            if len(p) < 15:                 # krótka linia = zwykle nagłówek/etykieta
                pending = (pending + " " + p).strip()
                continue
            if pending:
                p = pending + " " + p       # nagłówek + treść razem (kluczowe dla wyszukiwania)
                pending = ""
            paras.append((page, p))
        if pending:                         # nagłówek na końcu strony bez treści
            paras.append((page, pending))
    return paras


def split_long(text, target):
    """Dzieli zbyt długi akapit na kawałki po zdaniach."""
    if len(text) <= target:
        return [text]
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for s in sents:
        if len(cur) + len(s) + 1 > target and cur:
            out.append(cur.strip())
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur.strip())
    return out


def build_chunks(paras, target, overlap):
    chunks = []
    cur, cur_pages, cid = "", [], 0
    prev_tail = ""

    def flush():
        nonlocal cur, cur_pages, cid, prev_tail
        if not cur.strip():
            return
        chunks.append({
            "id": f"chunk_{cid:05d}",
            "text": cur.strip(),
            "page_start": min(cur_pages),
            "page_end": max(cur_pages),
            "n_chars": len(cur.strip()),
        })
        cid += 1
        prev_tail = cur.strip()[-overlap:] if overlap else ""
        cur, cur_pages = "", []

    for page, para in paras:
        for piece in split_long(para, target):
            if not cur and prev_tail:
                cur = prev_tail + " "  # zakładka z poprzedniego chunku
            if len(cur) + len(piece) + 1 > target and cur.strip():
                flush()
                if prev_tail:
                    cur = prev_tail + " "
            cur += piece + "\n\n"
            cur_pages.append(page)
    flush()
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/text")
    ap.add_argument("--target", type=int, default=1100, help="docelowy rozmiar chunku (znaki)")
    ap.add_argument("--overlap", type=int, default=200, help="zakładka między chunkami (znaki)")
    args = ap.parse_args()

    paras = paragraphs(args.dir)
    chunks = build_chunks(paras, args.target, args.overlap)

    out = os.path.join(args.dir, "chunks.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    avg = sum(c["n_chars"] for c in chunks) / len(chunks) if chunks else 0
    print(f"Akapitów: {len(paras)}  ->  chunków: {len(chunks)}  "
          f"(śr. {avg:.0f} zn.)  ->  {out}")
    if chunks:
        print("\n--- przykładowy chunk ---")
        print(json.dumps(chunks[len(chunks)//2], ensure_ascii=False, indent=2)[:900])


if __name__ == "__main__":
    main()
