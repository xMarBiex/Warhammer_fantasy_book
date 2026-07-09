# Uruchomienie lokalne (tylko dla Ciebie, na własnym laptopie)

Cały system działa na `localhost` — nic nie jest wystawiane do internetu, nikt
inny nie ma dostępu. Dwa narzędzia w jednym oknie przeglądarki:

- **Czat z Mistrzem Gry** (`http://127.0.0.1:8000/`) — pytania naturalne, wymaga
  klucza Claude API.
- **Przeglądarka strukturalna** (`http://127.0.0.1:8000/przegladarka`) — lookupy
  cech, czarów, cen, potworów, zależności i zasad. **Bez API, za darmo.**

## Co jest potrzebne
- **Python 3.10+**
- **~2 GB wolnej pamięci RAM** (model wyszukiwania semantycznego)
- **Klucz Claude API** z `console.anthropic.com` — tylko do czatu (przeglądarka
  działa bez niego). To osobny produkt od subskrypcji Claude Pro.

## Krok po kroku (macOS / Linux)
```bash
# 1. Sklonuj repo i wejdź do katalogu
git clone <adres-repo> && cd Warhammer_fantasy_book

# 2. Rozpakuj dołączoną paczkę danych (baza wektorowa + KOS) do katalogu projektu
tar -xzf kos-dane.tar.gz          # tworzy data/chroma, data/kos, data/text, data/tables

# 3. Ustaw klucz API (do czatu) i uruchom
export ANTHROPIC_API_KEY=sk-ant-...
./start.sh
```
Skrypt sam utworzy środowisko Pythona, doinstaluje zależności i wystartuje serwer.
Potem otwórz `http://127.0.0.1:8000/`.

## Windows (PowerShell)
```powershell
git clone <adres-repo>; cd Warhammer_fantasy_book
tar -xzf kos-dane.tar.gz                     # Windows 10/11 ma wbudowany tar
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.\.venv\Scripts\python kos\build_kos.py       # baza SQL/Graf
.\.venv\Scripts\python kos\export_web.py       # przeglądarka
.\.venv\Scripts\python agent\server.py         # serwer -> http://127.0.0.1:8000
```

## Bez paczki danych (budowa bazy wektorowej od zera)
Jeśli nie masz `kos-dane.tar.gz`, ale masz `data/text/chunks.jsonl` (proza z OCR):
```bash
./.venv/bin/python scripts/build_facts.py         # fakt-karty z tabel
./.venv/bin/python scripts/04_build_vectordb.py    # embeddingi -> data/chroma (~15 min, raz)
```
Model embeddingów pobiera się automatycznie z Google Cloud Storage przy
pierwszym uruchomieniu (HuggingFace bywa zablokowany — patrz `scripts/embedder.py`).

## Sprawdzenie, że działa
```bash
./.venv/bin/python scripts/selftest.py            # SQL/Graf + spójność (bez klucza)
./.venv/bin/python scripts/selftest.py --vectors  # + wyszukiwanie semantyczne
ANTHROPIC_API_KEY=sk-... ./.venv/bin/python scripts/selftest.py --all   # + czat
```

## Koszty
- Przeglądarka strukturalna: **0 zł** (żadnego API).
- Czat: płatny wg zużycia Claude API (Sonnet ~0,15–0,30 zł/pytanie). Model
  ustawisz w `agent/agent.py` (`MODEL = "claude-sonnet-5"` dla taniej,
  `"claude-opus-4-8"` dla max jakości).

## Zatrzymanie
Ctrl+C w terminalu. Nic nie zostaje uruchomione w tle.
