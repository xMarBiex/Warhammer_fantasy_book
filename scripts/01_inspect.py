#!/usr/bin/env python3
"""Krok 1: inspekcja PDF + test jakości OCR.

Cel: zanim zbudujemy pipeline, sprawdzić:
  1. Ile stron, jak duży plik, jakie metadane.
  2. Czy PDF ma wbudowaną warstwę tekstową (wtedy OCR często zbędny),
     czy to skan/grafika (wtedy trzeba OCR-ować).
  3. Jak dobrze OCR (tesseract pol+eng) radzi sobie na kilku próbkach.

Uruchomienie:
    python scripts/01_inspect.py data/raw/ksiazka.pdf
    python scripts/01_inspect.py data/raw/ksiazka.pdf --ocr 1,50,120 --dpi 300
"""
import argparse
import io
import os
import sys

import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image
    HAVE_OCR = True
except ImportError:
    HAVE_OCR = False

# Poniżej tylu znaków "prawdziwego" tekstu na stronie uznajemy stronę
# za bez warstwy tekstowej (sam obraz / ozdobniki).
TEXT_LAYER_THRESHOLD = 40


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def analyze_text_layer(doc):
    """Ile stron ma sensowną warstwę tekstową."""
    per_page = []
    for i, page in enumerate(doc):
        txt = page.get_text("text").strip()
        per_page.append(len(txt))
    with_text = sum(1 for n in per_page if n >= TEXT_LAYER_THRESHOLD)
    return per_page, with_text


def ocr_page(doc, page_index, dpi, lang):
    """Renderuje stronę do obrazu i przepuszcza przez tesseract."""
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang=lang)


def main():
    ap = argparse.ArgumentParser(description="Inspekcja PDF + test OCR")
    ap.add_argument("pdf", help="ścieżka do pliku PDF")
    ap.add_argument("--ocr", default="",
                    help="strony do OCR (1-indeks, po przecinku), np. 1,50,120. "
                         "Domyślnie auto-wybór kilku stron.")
    ap.add_argument("--dpi", type=int, default=300, help="DPI renderu do OCR")
    ap.add_argument("--lang", default="pol+eng", help="języki tesseract")
    ap.add_argument("--chars", type=int, default=800,
                    help="ile znaków próbki tekstu wypisać")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        sys.exit(f"BŁĄD: nie ma pliku {args.pdf}")

    size = os.path.getsize(args.pdf)
    doc = fitz.open(args.pdf)
    n = doc.page_count

    print("=" * 70)
    print(f"PLIK      : {args.pdf}")
    print(f"ROZMIAR   : {human(size)}")
    print(f"STRON     : {n}")
    md = doc.metadata or {}
    for k in ("title", "author", "producer", "creator"):
        if md.get(k):
            print(f"{k.upper():10}: {md[k]}")
    print("=" * 70)

    per_page, with_text = analyze_text_layer(doc)
    pct = 100 * with_text / n if n else 0
    print(f"\nWARSTWA TEKSTOWA: {with_text}/{n} stron ma tekst "
          f"(>= {TEXT_LAYER_THRESHOLD} znaków) = {pct:.0f}%")
    if pct >= 90:
        print("  -> PDF ma dobrą warstwę tekstową. OCR raczej NIEpotrzebny "
              "(albo tylko dla nielicznych stron-obrazów).")
    elif pct <= 10:
        print("  -> PDF to praktycznie skan/grafika. OCR KONIECZNY dla całości.")
    else:
        print("  -> Mieszany. Część stron z tekstem, część do OCR.")

    # Rozkład: pokaż kilka stron bez tekstu (kandydaci do OCR)
    no_text = [i + 1 for i, c in enumerate(per_page) if c < TEXT_LAYER_THRESHOLD]
    if no_text:
        preview = no_text[:15]
        more = "" if len(no_text) <= 15 else f" ... (+{len(no_text)-15})"
        print(f"  Strony bez warstwy tekstowej: {preview}{more}")

    # --- Próbka warstwy tekstowej (pierwsza strona z tekstem) ---
    first_txt = next((i for i, c in enumerate(per_page) if c >= TEXT_LAYER_THRESHOLD), None)
    if first_txt is not None:
        print(f"\n--- PRÓBKA WARSTWY TEKSTOWEJ (strona {first_txt + 1}) ---")
        print(doc[first_txt].get_text("text").strip()[:args.chars])

    # --- Test OCR ---
    if not HAVE_OCR:
        print("\n[OCR pominięty: brak pytesseract/PIL]")
        doc.close()
        return

    if args.ocr:
        pages = [int(x) - 1 for x in args.ocr.split(",") if x.strip()]
    else:
        # auto: pierwsza strona, środek, i pierwsza strona bez warstwy tekstowej
        cand = {0, n // 2}
        if no_text:
            cand.add(no_text[0] - 1)
        pages = sorted(p for p in cand if 0 <= p < n)

    print(f"\n{'='*70}\nTEST OCR (dpi={args.dpi}, lang={args.lang})\n{'='*70}")
    for p in pages:
        print(f"\n--- OCR strona {p + 1} ---")
        try:
            out = ocr_page(doc, p, args.dpi, args.lang).strip()
        except Exception as e:  # np. brak języka w tesseract
            print(f"  BŁĄD OCR: {e}")
            continue
        print(f"  [znaków OCR: {len(out)} | warstwa tekstowa: {per_page[p]}]")
        print("  " + "\n  ".join(out[:args.chars].splitlines()))

    doc.close()
    print(f"\n{'='*70}\nGotowe. Oceń powyższe próbki: czy tekst jest czytelny, "
          "czy polskie znaki (ą ę  ł ż ź ć ń ó) są poprawne.")


if __name__ == "__main__":
    main()
