#!/usr/bin/env python3
"""Krok 2: OCR całego PDF -> tekst per strona (wznawialne).

Dla każdej strony: render 300 DPI -> tesseract (pol+eng) -> plik tekstowy.
Wyniki:
  data/text/pages/page_0001.txt ...   (surowy OCR jednej strony)
  data/text/manifest.jsonl            (metadane: strona, znaki, czy pusta)

Wznawianie: strony, które mają już plik .txt, są pomijane. Można bezpiecznie
przerwać (Ctrl-C) i uruchomić ponownie.

    python scripts/02_extract.py data/raw/ksiega_zasad.pdf
    python scripts/02_extract.py data/raw/ksiega_zasad.pdf --dpi 300 --lang pol+eng
"""
import argparse
import io
import json
import os
import sys
import time

import fitz
import pytesseract
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--lang", default="pol+eng")
    ap.add_argument("--out", default="data/text")
    args = ap.parse_args()

    pages_dir = os.path.join(args.out, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    manifest_path = os.path.join(args.out, "manifest.jsonl")

    doc = fitz.open(args.pdf)
    n = doc.page_count
    print(f"PDF: {args.pdf}  stron={n}  dpi={args.dpi}  lang={args.lang}")

    done = 0
    ocr_done = 0
    t0 = time.time()
    manifest = []
    for i in range(n):
        page_no = i + 1
        out_txt = os.path.join(pages_dir, f"page_{page_no:04d}.txt")
        if os.path.exists(out_txt):
            with open(out_txt, encoding="utf-8") as f:
                txt = f.read()
            done += 1
        else:
            pix = doc[i].get_pixmap(dpi=args.dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            txt = pytesseract.image_to_string(img, lang=args.lang).strip()
            with open(out_txt, "w", encoding="utf-8") as f:
                f.write(txt)
            ocr_done += 1
            done += 1
            if ocr_done % 10 == 0:
                el = time.time() - t0
                rate = ocr_done / el
                eta = (n - done) / rate if rate else 0
                print(f"  [{done}/{n}] str.{page_no}  {len(txt)} zn.  "
                      f"~{rate:.2f} str/s  ETA {eta/60:.1f} min", flush=True)
        manifest.append({"page": page_no, "chars": len(txt),
                         "empty": len(txt) < 40})

    with open(manifest_path, "w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    empties = sum(1 for r in manifest if r["empty"])
    total_chars = sum(r["chars"] for r in manifest)
    print(f"\nGOTOWE. Stron: {n}  |  z tekstem: {n - empties}  |  "
          f"pustych/graficznych: {empties}  |  łącznie znaków: {total_chars:,}")
    print(f"OCR wykonany teraz dla {ocr_done} stron, "
          f"czas {(time.time()-t0)/60:.1f} min. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
