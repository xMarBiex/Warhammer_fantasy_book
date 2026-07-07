# Warhammer Fantasy — Knowledge Operating System (KOS)

Cyfrowy **ekspert-Mistrz Gry** systemu *Warhammer Fantasy Roleplay 2e*: okno
dialogowe, w którym pytasz o grę, a agent odpowiada **wyłącznie na podstawie
Księgi Zasad** — liczby z tabel, relacje z grafu, zasady i lore z treści księgi,
zawsze ze źródłem i poziomem pewności.

Zasada nadrzędna (spec `docs/KOS_SPEC.md`): **model językowy nie jest bazą
wiedzy** — jest analitykiem, który sięga po wiedzę do warstw danych.

## Architektura — 5 warstw
Pełne mapowanie na technologie: `docs/ARCHITECTURE.md`.

| Warstwa | Rola | Realizacja | Kod |
|---|---|---|---|
| 1. Document Intelligence | PDF → dane | PyMuPDF + Tesseract `pol+eng` | `scripts/01–03` |
| 2. Knowledge Graph | relacje/znaczenie | SQLite `nodes`/`edges` | `kos/` |
| 3. Relational (SQL) | dokładne liczby | SQLite `profession_stats` | `kos/` |
| 4. Semantic Memory | proza / lore | ChromaDB + e5-large | `scripts/embedder.py` |
| 5. Reasoning Engine | plan + odpowiedź | Claude API + narzędzia | `agent/` |
| Metadata / Confidence | źródło, strona, pewność | kolumny na każdym rekordzie | wszędzie |

## Agent w oknie dialogowym (główny produkt)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python kos/build_kos.py                 # zbuduj warstwę Graf+SQL z tabel

export ANTHROPIC_API_KEY=sk-ant-...     # wymagane — klucz do Claude API
python agent/server.py                  # http://127.0.0.1:8000
```

Otwórz `http://127.0.0.1:8000` i pytaj po polsku, np. *„Jakie są cechy akolity
i do czego może awansować?"*, *„Która profesja ma największą WW?"*, *„Jak działają
punkty przeznaczenia?"*. Pytania spoza świata gry agent **grzecznie odrzuca**.

Test z terminala (bez UI):
```bash
python agent/agent.py "statystyki zabójcy demonów"
python kos/query.py  "największa krzepa"      # sama warstwa SQL/Graf, bez API
```

Jak to działa (Warstwa 5): agent klasyfikuje pytanie i wywołuje narzędzia —
`profesja_szczegoly` (SQL+Graf), `porownaj_ceche` (SQL), `szukaj_zasad`
(wektory) — po czym odpowiada z cytowaniem strony i pewności. Model:
`claude-opus-4-8`, myślenie adaptacyjne.

## Warstwa danych (jak zbudowana)

```bash
# Warstwa 1 — OCR całości (skan, 266 stron; wznawialny)
python scripts/02_extract.py data/raw/ksiega_zasad.pdf
python scripts/03_chunk.py

# Warstwa 4 — embeddingi + baza wektorowa (proza)
python scripts/04_build_vectordb.py

# Warstwa 2+3 — graf i tabele z tables/*.json
python kos/build_kos.py

# strona testowa warstwy strukturalnej (offline/Cloudflare)
python kos/export_web.py                # -> web/kos.html + dist/index.html
```

**Źródło prawdy tabel:** `tables/*.json` (w gicie). `data/` jest generowane i poza
gitem. Kontrola spójności grafu przy `build_kos.py` wykrywa braki (np. profesje
wskazane w rozwoju, których jeszcze nie wpisano).

## Ograniczenia środowiska (istotne)
- **HuggingFace zablokowany** → model e5-large z Google Cloud Storage
  (`scripts/embedder.py`), ładowany przez `specific_model_path`.
- **Duże pliki** (PDF 143 MB) → GitHub Release asset (Drive/Dropbox zablokowane).
- **Agent wymaga `ANTHROPIC_API_KEY`** (własny klucz Claude API).
- **venv obowiązkowy** (konflikt z systemowym PyYAML na Debianie).

## Stan i plan
- ✅ OCR całości; baza wektorowa (1561 fragmentów); profesje w SQL/Graf (111 +
  wykryte luki); agent dialogowy z narzędziami i strażnikiem tematu.
- ⬜ Kolejne tabele (broń, pancerz, ekwipunek, czary, trafienia krytyczne,
  bestiariusz) → `weapon_stats`, `spell_stats`… + relacje `CAN_EQUIP`/`CASTS`.
- Szczegóły i przekazanie sesji: `docs/HANDOFF.md`.

## Uwaga o wcześniejszych narzędziach
`scripts/webapp.py` i `scripts/build_mobile.py` (wyszukiwarki prozy) są
**poprzednikami** agenta — nadal działają jako podgląd warstwy wektorowej, ale
docelowym interfejsem jest agent (`agent/`), który łączy wszystkie warstwy.
