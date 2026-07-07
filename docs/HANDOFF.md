# HANDOFF — Warhammer Fantasy: PDF → baza wiedzy dla agenta

> **ARCHITEKTURA (2026-07): przejście na Knowledge Operating System (KOS).**
> Kanon wymagań: `docs/KOS_SPEC.md`. Mapowanie na technologie: `docs/ARCHITECTURE.md`.
> 5 warstw: Graf+SQL+Metadane = SQLite `data/kos/kos.db` (`kos/build_kos.py`,
> `kos/query.py`), Wektory = ChromaDB, Document Store = `data/text/`.
> Zasada: **model nie jest bazą wiedzy** — liczby z SQL, relacje z grafu, proza z
> wektorów, wszystko ze źródłem i poziomem pewności.

Dokument dla nowej sesji. Cel: agent „nakarmiony" Księgą Zasad = **baza wektorowa
(proza)** + **tabele w warstwie SQL/Graf (dane strukturalne z prowenancją)**.

Repo: `xMarBiex/Warhammer_fantasy_book` · gałąź `claude/pdf-vector-database-rj4qzp`
Katalog roboczy: `/home/user/Warhammer_fantasy_book` · Python: `./.venv/bin/python`

## 1. Co jest zrobione ✅
- **PDF → OCR całości**: 266 stron, tesseract `pol+eng` 300 DPI → `data/text/pages/`.
  Diagnoza: PDF to czysty skan (0% warstwy tekstowej).
- **Baza wektorowa (proza)**: ChromaDB, model `intfloat/multilingual-e5-large` (fastembed/ONNX),
  **1537 wektorów**. Ranking: **spis treści > nagłówki > treść (IDF)**.
- **Tabele: PROFESJE — 113 (KOMPLET, graf domknięty)** (Rozdział III, str. 32–88).
  Źródło prawdy: `tables/professions.json`. Kontrola spójności KOS wykryła i
  **uzupełniono** brakującą stronę 69 (`Kapłan`, `Karczmarz` — zaawansowane).
  Nie-encja `chwalebna śmierć!` (klimatyczne wyjście) na whiteliście w `build_kos.py`.
- **Oręż — KOMPLET (Tabela 5-4/5-5 + amunicja, str. 110)**: `tables/weapons.json`,
  **47 rekordów** (19 biała, 24 strzelecka, 4 amunicja) — obrażenia (Siła broni),
  cena, obciążenie, kategoria, zasięg/przeładowanie, cechy oręża, dostępność.
- **Pancerz — KOMPLET (Tabela 5-6, str. 114)**: `tables/armour.json`, **17 rekordów**
  (skórzana/kolcza/płytowa) — PZ, cena, obciążenie, chronione lokacje, dostępność.
- **Czary — W TOKU (`tables/spells.json`)**: **Magia powszechna KOMPLET (8 czarów,
  str. 155–156)** — poziom mocy, czas rzucania, składnik, czas trwania, opis.
  Węzły `Spell` + `MagicLore` z relacją `BELONGS_TO`. Kolejne tradycje: Magia
  tajemna (8 Tradycji, str. 156–167), czarnoksięska (168+), kapłańska.
- **KOS Graf+SQL**: `data/kos/kos.db` — 186 węzłów, 760 krawędzi (`ADVANCES_TO`,
  `DEFINED_IN`, `BELONGS_TO`), tabele SQL: 113 profesji + 47 oręża + 17 pancerzy
  + 8 czarów. **0 luk.**
- **Agent dialogowy (Warstwa 5)**: `agent/` — okno czatu na Claude API
  (`claude-opus-4-8`), 7 narzędzi: `profesja_szczegoly`, `porownaj_ceche`,
  `bron_szczegoly`, `pancerz_szczegoly`, `czar_szczegoly`, `czary_tradycji`
  (wszystkie SQL/Graf) + `szukaj_zasad` (wektory); strażnik tematu (tylko WFRP).
  Uruchomienie: `ANTHROPIC_API_KEY=... python agent/server.py`.
- **Fakt-karty**: 111 (zdania z dokładnymi liczbami) → `data/tables/facts.json`.
- **Wyszukiwarka mobilna** (samodzielny HTML, offline w przeglądarce):
  artefakt `https://claude.ai/code/artifact/f7157f9c-3bbd-4e9c-9fdf-127e4633ba3c`
  oraz paczka Cloudflare Pages (`dist/`). Renderuje karty cech profesji + wyszukiwanie prozy.

## 2. Co pozostało ⬜ (kolejność wg wartości)
Wszystko to TABELE (wymagają odczytu WZROKOWEGO — tesseract ich nie czyta):
1. ✅ **Broń** — zrobione (`tables/weapons.json`, str. 110).
2. ✅ **Pancerz** — zrobione (`tables/armour.json`, Tabela 5-6, str. 114).
3. **Ekwipunek / usługi** (ceny) — Rozdział V, str. ~116–127 (Tabele 5-8…5-19)
4. **Czary** — ⏳ W TOKU. Zrobiona Magia powszechna (8, str. 155–156). Pozostałe:
   Magia tajemna (8 Tradycji: Cienia, Ognia, Metalu, Śmierci, Życia, Niebios,
   Bestii, Światła — str. 157–167), Magia czarnoksięska (168+), Magia kapłańska.
   Format czaru: nazwa / Wymagany poziom mocy / Czas rzucania / [Zasięg] /
   Składnik / Czas trwania / Opis. **PM czytaj WZROKOWO** (OCR myli cyfry, np. „Ś").
5. **Trafienia krytyczne** (tabele efektów wg lokacji) — ~str. 138–141
6. **Bestiariusz** (profile potworów) — Rozdział XI, ~str. 238–247

Wzorzec dodania tabeli (jak przy broni): `tables/<x>.json` → tabela SQL w
`kos/schema.sql` → materializacja w `kos/build_kos.py` → metody w `kos/query.py`
→ narzędzie w `agent/tools.py` (+ wpis w SYSTEM `agent/agent.py`).
Numery stron sprawdź w spisie treści: `data/text/toc.json` (offset druk→PDF: `doc[P]` = strona drukowana P).

Po tabelach: **przebudować bazę wektorową** na aktualne chunki (`chunks.jsonl` ma 1561, baza ma 1537)
i **wstrzyknąć fakt-karty**, żeby proza i tabele były spójne.

## 3. Struktura danych
```
tables/                    ← ŹRÓDŁO PRAWDY (w gicie)
  professions.json         111 rekordów. Schemat:
      {name, type:"podstawowa|zaawansowana", page:int(drukowana),
       main{WW,US,K,Odp,Zr,Int,SW,Ogd}, secondary{A,Żyw,S,Wt,Sz,Mag,PO,PP},
       skills, talents, trappings, entries, exits, note?}
      Wartości cech to stringi: "+10" / "+5" / "—" (puste pole = "—").
  (do zrobienia) weapons.json, armour.json, items.json, spells.json, criticals.json, bestiary.json
data/                      ← generowane (poza gitem, .gitignore)
  raw/ksiega_zasad.pdf     143 MB (pobrany z GitHub Release, sha256 526c211c…beb1)
  text/pages/*.txt         OCR per strona
  text/chunks.jsonl        1561 chunków prozy (metadane page_start/page_end)
  text/toc.json            spis treści (temat→strona) do rankingu
  tables/facts.json        111 fakt-kart
  chroma/                  baza wektorowa
scripts/                   01_inspect 02_extract 03_chunk 04_build_vectordb 05_query
                           embedder build_toc build_facts build_mobile webapp run_all package_data
web/                       search_mobile.template.html (źródło), index.html (serwerowa wersja)
docs/                      TABLES_DESIGN.md (architektura), HANDOFF.md (ten plik)
```

## 4. Docelowa architektura agenta (standard: hybrid RAG)
- **Proza → baza wektorowa** (narzędzie `szukaj_zasad(pytanie)` → fragmenty + strony).
- **Tabele → strukturalny JSON w kontekście** (digest) **+ narzędzie `lookup(typ,nazwa)`**.
  Embeddingi są słabe w „podaj dokładną wartość" — tabele obsługujemy deterministycznie.
- Profesje kompaktowo ≈ **21 K tokenów** (mieści się w kontekście). Całość tabel szacunkowo
  ~40–50 K tokenów — OK dla dedykowanego agenta; gdyby rosło, przełączyć tabele na tryb narzędzia.

## 5. ⚠️ Ograniczenia środowiska (KRYTYCZNE — czytaj przed pracą)
- **HuggingFace ZABLOKOWANY.** Model embeddingów pobierany z **Google Cloud Storage**
  (`storage.googleapis.com/qdrant-fastembed/…`), ładowany lokalnie przez `specific_model_path`.
  Patrz `scripts/embedder.py`. Nie próbuj `sentence-transformers` z HF.
- **Google Drive / Dropbox ZABLOKOWANE** dla pobierania. Duże pliki → **GitHub Release asset**.
- **Limit obrazów: ~32 MB / zapytanie (ŁĄCZNIE).** Każdy odczytany obraz zostaje w kontekście.
  Po ~40 stronach limit się zapełnia i kolejne obrazy są odrzucane („Request too large (max 32MB)").
  ROZWIĄZANIE: renderuj tylko PRAWĄ POŁOWĘ strony jako MAŁY JPEG (dpi≈115, quality 70, ~0,07 MB)
  i/lub użyj **podagenta** (ma własny budżet obrazów).
- **Tabele ≠ tesseract.** Siatka cech OCR-uje się na śmieci. Jedyna metoda: odczyt WZROKOWY z renderu.
- **Limit sesji konta** bywa osiągany (reset ~4:00 UTC) — może ubić długie zadania.
- **Git:** committer email = `noreply@anthropic.com`, name = `Claude` (inaczej hook zgłasza „Unverified").
- **venv:** `chromadb`, `fastembed`, `pymupdf`, `pytesseract` są w `./.venv`. NIE instaluj globalnie
  (konflikt z systemowym PyYAML — dlatego venv).

## 6. Jak ekstrahować tabele (sprawdzony przepis)
Render prawej połowy strony (górna/dolna profesja) jako mały JPEG:
```python
import fitz
doc=fitz.open("data/raw/ksiega_zasad.pdf"); p=doc[IDX]; r=p.rect   # IDX = strona drukowana (0-idx)
p.get_pixmap(dpi=115, clip=fitz.Rect(r.width*0.46, r.height*0.06, r.width*0.99, r.height*0.52)).save("/tmp/t.jpg", jpg_quality=70)  # góra
p.get_pixmap(dpi=115, clip=fitz.Rect(r.width*0.46, r.height*0.55, r.width*0.99, r.height*0.99)).save("/tmp/b.jpg", jpg_quality=70)  # dół
```
Czytaj JPEG narzędziem Read, przepisz DOKŁADNIE wartości. **Podagent: zapisuj przyrostowo**
(dopisuj do pliku po każdej stronie), bo crash/limit sesji kasuje niezapisany kontekst
(tak omal nie stracono 26 profesji — uratowane ze skryptu roboczego podagenta).

## 7. Budowa artefaktów po zmianie danych
```bash
. .venv/bin/activate
python scripts/build_facts.py       # tables/*.json -> data/tables/facts.json
python scripts/build_mobile.py      # -> web/search_mobile.html (artefakt) + dist/index.html (Cloudflare)
# baza wektorowa (proza) — do przebudowy na 1561 chunków + fakt-karty:
python scripts/03_chunk.py && python scripts/04_build_vectordb.py
```
Publikacja artefaktu: narzędzie Artifact na `web/search_mobile.html` (ten sam URL co wyżej).

## 8. Następny krok
Po resecie limitu: **podagent** na broń (str. ~105–125), z zapisem przyrostowym do
`tables/weapons.json` (+ `armour.json`, `items.json`). Potem czary, trafienia krytyczne, bestiariusz.
Na końcu: przebudowa bazy wektorowej + złożenie pakietu agenta (digest + narzędzia).
