# Warhammer Fantasy — książka (PDF) → baza wektorowa

Pipeline zamieniający książkę w PDF (z grafikami i ozdobnikami, ~150 MB)
na przeszukiwalną **bazę wektorową** (RAG). Budujemy **małymi krokami** i
po każdym sprawdzamy jakość — szczególnie OCR.

## Plan (krok po kroku)

| Krok | Co robimy | Status |
|------|-----------|--------|
| 0 | Wgranie PDF (Google Drive → `data/raw/`) | ⏳ czeka na plik |
| 1 | **Inspekcja PDF + test OCR** — ile stron, czy jest warstwa tekstowa, jakość OCR na próbkach (`scripts/01_inspect.py`) | ✅ narzędzie gotowe |
| 2 | Ekstrakcja tekstu z całości (warstwa tekstowa lub OCR pol+eng) → `data/text/` | ⬜ |
| 3 | Czyszczenie + podział na fragmenty (chunking) z metadanymi (strona, rozdział) | ⬜ |
| 4 | Embeddingi + zapis do bazy wektorowej (ChromaDB, standard, lokalnie) | ⬜ |
| 5 | Zapytania testowe (retrieval) + ocena trafności | ⬜ |

Rozbudowujemy pipeline dopiero po zatwierdzeniu poprzedniego kroku —
nie chcemy OCR-ować 150 MB na złych ustawieniach.

## Jak wgrać PDF, żebym go widział

Plik ma 150 MB — **za duży dla gita** (GitHub odrzuca >100 MB i nie należy
trzymać binariów w repo). Najprościej przez **Google Drive** (podłączony):

1. Wrzuć PDF na swój Dysk Google (gdziekolwiek).
2. Napisz mi nazwę pliku **albo** wklej link `drive.google.com/file/d/.../view`.
3. Pobiorę go do `data/raw/` i odpalę krok 1 (inspekcja + próbki OCR).

Alternatywy, jeśli wolisz: publiczny link (Dropbox / WeTransfer / S3) —
wtedy ściągnę przez `curl`.

## Stack (proponowany, „zgodnie ze standardami")

- **Ekstrakcja / render:** PyMuPDF (fitz)
- **OCR:** Tesseract 5 (`pol+eng`) — tylko dla stron bez warstwy tekstowej
- **Baza wektorowa:** ChromaDB (lokalna, trwała, standard dla RAG)
- **Embeddingi:** model wielojęzyczny (np. `intfloat/multilingual-e5`)
  lokalnie przez `sentence-transformers` — bez kluczy API i offline.
  Do ustalenia w kroku 4 (lokalnie vs API).

## Instalacja

```bash
pip install -r requirements.txt
# OCR systemowy:
sudo apt-get install -y tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng
```

## Użycie (krok 1)

```bash
python scripts/01_inspect.py data/raw/ksiazka.pdf
# konkretne strony do OCR + wyższe DPI:
python scripts/01_inspect.py data/raw/ksiazka.pdf --ocr 1,50,120 --dpi 400
```
