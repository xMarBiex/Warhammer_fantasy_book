# Warhammer Fantasy — Księga Zasad (PDF) → baza wektorowa

Pipeline zamieniający zeskanowaną książkę w PDF (266 stron, ~143 MB, pełną
grafik i ozdobników) na przeszukiwalną **bazę wektorową** (RAG). Budowany
**małymi krokami**, z weryfikacją jakości po każdym — szczególnie OCR.

## Status

| Krok | Co robimy | Status |
|------|-----------|--------|
| 0 | Wgranie PDF → `data/raw/` (przez GitHub Release, patrz niżej) | ✅ pobrany, checksum OK |
| 1 | Inspekcja PDF + test OCR (`scripts/01_inspect.py`) | ✅ 0% warstwy tekstowej → skan; OCR pol+eng czytelny |
| 2 | OCR całości → `data/text/pages/` (`scripts/02_extract.py`) | ⏳ w toku |
| 3 | Czyszczenie + chunking z metadanymi stron (`scripts/03_chunk.py`) | ✅ |
| 4 | Embeddingi + baza wektorowa ChromaDB (`scripts/04_build_vectordb.py`) | ✅ (przetestowane na 10 stronach) |
| 5 | Zapytania testowe / retrieval (`scripts/05_query.py`) | ✅ (przetestowane) |

**Test na 10 stronach** przeszedł: retrieval trafnie odpowiada na pytania po
polsku z cytowaniem stron. Pełną bazę budujemy po zakończeniu OCR całości.

## Stack (finalny, dobrany pod ograniczenia środowiska)

- **Ekstrakcja / render:** PyMuPDF (fitz)
- **OCR:** Tesseract 5 (`pol+eng`), render 300 DPI (eksperyment: 300 DPI surowe
  = optimum; binaryzacja pogarsza polskie znaki diakrytyczne)
- **Embeddingi:** `intfloat/multilingual-e5-large` (dim 1024) przez **fastembed**
  (ONNX, bez torcha). Model pobierany z **Google Cloud Storage**, bo HuggingFace
  jest w tym środowisku zablokowany — szczegóły w `scripts/embedder.py`.
- **Baza wektorowa:** **ChromaDB** (lokalna, trwała, metryka cosine)

Uwaga o jakości: skan generuje literówki OCR (gubione ż/ć/ń, ligatura „fi"→h),
ale e5-large jest na taki szum odporny — retrieval działa poprawnie mimo błędów.

## Jak dostarczono PDF (150 MB)

Plik jest za duży dla gita (>100 MB) i dla pobrania przez MCP (base64 do
kontekstu). Google Drive i Dropbox są zablokowane przez egress proxy. Zadziałał
**GitHub Release**: PDF wgrany jako *release asset* (host `objects.githubusercontent.com`
jest dostępny), a skrypt pobiera go z `browser_download_url`.

## Instalacja

```bash
# OCR systemowy
sudo apt-get install -y tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng
# Python w venv (unika konfliktu z systemowym PyYAML)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## Użycie (cały pipeline)

```bash
. .venv/bin/activate

# 1. Inspekcja + próbki OCR
python scripts/01_inspect.py data/raw/ksiega_zasad.pdf

# 2. OCR całości (wznawialny — można przerwać i wznowić)
python scripts/02_extract.py data/raw/ksiega_zasad.pdf

# 3. Chunking z metadanymi stron
python scripts/03_chunk.py

# 4. Embeddingi + baza wektorowa
python scripts/04_build_vectordb.py

# 5. Zapytanie z terminala (retrieval z cytowaniem stron)
python scripts/05_query.py "jak działa parowanie ciosu?" -k 5
```

## Wyszukiwarka w przeglądarce (okno HTML)

Graficzne okno zapytań do bazy — serwer ładuje model i bazę raz, strona
odpytuje go przez `fetch`:

```bash
. .venv/bin/activate
python scripts/webapp.py            # domyślnie port 8000, baza data/chroma
# potem otwórz w przeglądarce:  http://localhost:8000
```

Pliki: `scripts/webapp.py` (serwer, tylko stdlib + chromadb + fastembed) oraz
`web/index.html` (interfejs). Wpisujesz pytanie po polsku, dostajesz fragmenty
z numerami stron i podobieństwem.

Dane (PDF, tekst OCR, baza wektorowa) są poza gitem — patrz `.gitignore`.
