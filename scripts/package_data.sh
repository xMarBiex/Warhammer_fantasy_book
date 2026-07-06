#!/usr/bin/env bash
# Pakuje kompletne dane pipeline'u do jednego archiwum do pobrania.
# Zawiera: bazę wektorową (ChromaDB), tekst OCR per strona, chunki, manifest.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="warhammer_vectordb.tar.gz"
STAMP="$(date +%Y%m%d)"

# krótki README do archiwum
cat > data/ARCHIVE_README.md <<EOF
# Warhammer Fantasy — baza wektorowa (paczka danych, $STAMP)

Zawartość:
- chroma/              trwała baza wektorowa ChromaDB (kolekcja 'warhammer')
- text/pages/          tekst OCR per strona (page_NNNN.txt)
- text/chunks.jsonl    fragmenty z metadanymi stron (page_start/page_end)
- text/manifest.jsonl  statystyki OCR per strona

Model embeddingów: intfloat/multilingual-e5-large (dim 1024, cosine).

## Jak użyć bazy
    python3 -m venv .venv && . .venv/bin/activate
    pip install chromadb fastembed
    # zapytanie (skrypty z repo Warhammer_fantasy_book):
    python scripts/05_query.py "jak działa parowanie ciosu?" -k 5

Baza jest przenośna: wystarczy ten katalog chroma/ + ten sam model embeddingów.
EOF

tar -czf "$OUT" \
    -C data ARCHIVE_README.md chroma text
echo "Spakowano -> $OUT"
ls -lh "$OUT"
