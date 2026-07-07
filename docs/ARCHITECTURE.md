# KOS — Architektura wdrożenia (Warhammer Fantasy)

Mapowanie specyfikacji `docs/KOS_SPEC.md` na konkretne technologie w TYM
środowisku (kontener efemeryczny, bez serwerów baz danych, bez HuggingFace,
model embeddingów z Google Cloud Storage). Zasada: **model nie jest bazą wiedzy**
— liczby z SQL, relacje z grafu, proza z wektorów, wszystko z prowenancją i
poziomem pewności.

## Warstwy → technologia

| Warstwa (spec) | Rola | Realizacja tutaj | Status |
|---|---|---|---|
| 1. Document Intelligence | PDF → dane | PyMuPDF + tesseract `pol+eng` → `data/text/` | ✅ proza; ⬜ tabele (wzrokowo) |
| 2. Knowledge Graph | znaczenie/relacje | **SQLite** `nodes`+`edges` (`data/kos/kos.db`) | ✅ profesje (siatka rozwoju) |
| 3. Relational (SQL) | dokładne liczby | **SQLite** `profession_stats` (+ przyszłe `*_stats`) | ✅ profesje; ⬜ broń/czary/… |
| 4. Semantic Memory | lore/proza/FAQ | **ChromaDB** + e5-large (fastembed/ONNX) | ✅ 1561 fragmentów |
| 5. Reasoning Engine | plan + pewność | `agent/` (Claude API + narzędzia) i `kos/query.py` (rdzeń SQL/Graf) | ✅ agent dialogowy |
| Metadata Layer | źródło/edycja/pewność | kolumny `source_id, page, confidence` na każdym rekordzie | ✅ |

**Dlaczego SQLite dla Grafu i SQL:** brak serwera (Neo4j/Postgres) w kontenerze,
a graf + relacyjne dane mieszczą się w jednym pliku, wersjonowanym i budowanym w
sekundy. Graf = tabele `nodes`/`edges` z prowenancją. Gdy dane urosną do skali
wielu ksiąg, warstwę 2 można przenieść do Neo4j bez zmiany modelu (te same węzły/
relacje).

## Model grafu (Warstwa 2)
- **Węzeł** (`nodes`): `id` (`prof:akolita`), `type` (Profession/Book/…), `name`,
  `name_fold` (bez pl-znaków, do dopasowań), `data` (JSON pełnego rekordu),
  `source_id`, `page`, `confidence`.
- **Krawędź** (`edges`): `src`, `rel`, `dst`|`dst_name`, `source_id`, `page`,
  `confidence`. **Każda relacja niesie źródło+stronę+edycję+pewność** (wymóg spec).
- Zaimplementowane relacje: `ADVANCES_TO` (siatka rozwoju profesji: wejścia/
  wyjścia z Rozdziału III), `DEFINED_IN` (encja→książka). Słownik docelowy
  (CAN_EQUIP, CASTS, COUNTERS, …) dochodzi wraz z kolejnymi tabelami.

## Reasoning Engine (Warstwa 5) — `kos/query.py`
1. **Klasyfikacja** zapytania: FACT / EXPLANATION / COMPARISON / STRATEGY / RESEARCH.
2. **Routing warstw** wg tabeli ze specyfikacji (FACT→SQL/Graf, COMPARISON→SQL,
   EXPLANATION→Vector+Graf …).
3. **Wykonanie**: liczby i ekstrema przez SQL; sąsiedztwo w karierze przez graf.
4. **Confidence Engine**: 0.95 tabela/reguła, 0.9 relacja, prozę deleguje do
   Warstwy 4. Odpowiedź zawsze ze źródłem i pewnością.

## Agent rozwoju wiedzy / Validation (spec) — działa
`kos/build_kos.py` przy budowie wykrywa **encje wskazywane w relacjach, których
brak w tabelach**. Dzięki temu wykryto pominiętą stronę 69 — profesje `Kapłan`
i `Karczmarz` — które **uzupełniono** (graf domknięty, 0 luk). Nie-encję
`chwalebna śmierć!` (klimatyczne wyjście kariery) dodano do whitelisty
(`NON_ENTITIES`). To dokładnie „wykrywanie niepełnych danych i błędów OCR" ze
specyfikacji — i realnie poprawiło kompletność (111 → 113).

## Przepływ pracy
```bash
. .venv/bin/activate
python kos/build_kos.py                 # tables/*.json -> data/kos/kos.db (Graf+SQL+Meta)
python kos/query.py "statystyki akolita"        # FACT (SQL+Graf)
python kos/query.py "największa modyfikacja WW"  # COMPARISON (SQL)
# Warstwa 4 (proza) osobno: scripts/embedder.py + ChromaDB (data/chroma)
```

## Standardy wg specyfikacji — jak spełnione
- **„Nigdy nie pytaj modelu o liczby"** → `profession_stats` (SQL), `stat_extreme()`.
- **„Każda relacja: źródło, strona, książka, edycja, pewność"** → kolumny na `edges`.
- **„Confidence Engine"** → progi 0.95/0.9 + delegacja <do wektorów> dla prozy.
- **„Agent przed odpowiedzią tworzy plan"** → `classify()` + routing warstw.
- **„Po dodaniu książki system mądrzejszy, nie większy"** → nowe źródło = nowy
  `sources` + węzły/krawędzie z własnym `source_id`; `edition` rozróżnia wydania,
  `confidence` i przyszłe `UPDATED_BY`/errata rozstrzygają sprzeczności.

## Do zrobienia (kolejność wartości)
1. ✅ Uzupełniono `Kapłan`, `Karczmarz` (str. 69) — graf profesji domknięty (0 luk).
2. ✅ **Broń** — `weapon_stats` (47, str. 110) + `bron_szczegoly`.
   ✅ **Pancerz** — `armour_stats` (17, str. 114) + `pancerz_szczegoly`.
   ⬜ Ekwipunek/usługi (`item_costs`) + relacje `CAN_EQUIP`/`CAN_USE`.
3. **Czary** per tradycja → `spell_stats` + `Spell`/`CASTS`/`KNOWS`.
4. Podpiąć Warstwę 4 do `kos/query.py` (EXPLANATION/RESEARCH pobiera prozę z
   ChromaDB i łączy z faktami — pełny hybrydowy plan).
5. ✅ **Agent (Claude API) — zrobiony**: `agent/agent.py` (pętla tool-use,
   `claude-opus-4-8`, myślenie adaptacyjne, strażnik tematu), `agent/tools.py`
   (narzędzia `profesja_szczegoly`/`porownaj_ceche`/`szukaj_zasad`),
   `agent/server.py` + `agent/chat.html` (okno dialogowe). Wymaga
   `ANTHROPIC_API_KEY`. Kolejne tabele automatycznie wzbogacą narzędzia.
```
