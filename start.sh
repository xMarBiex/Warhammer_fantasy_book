#!/usr/bin/env bash
# Uruchomienie lokalne (tylko dla Ciebie, na localhost) — Warhammer Fantasy KOS.
# Użycie:  ./start.sh                          (backend domyślny: Ollama/Bielik)
#          KOS_BACKEND=claude ANTHROPIC_API_KEY=sk-ant-... ./start.sh
set -e
cd "$(dirname "$0")"

# 1) środowisko Pythona
if [ ! -x .venv/bin/python ]; then
  echo "→ Tworzę środowisko .venv i instaluję zależności…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
PY=./.venv/bin/python

# 2) warstwa SQL/Graf (buduje się z tables/*.json w sekundy)
if [ ! -f data/kos/kos.db ]; then
  echo "→ Buduję bazę KOS (SQL+Graf)…"
  $PY kos/build_kos.py
fi

# 3) przeglądarka strukturalna (statyczna, bez API)
if [ ! -f web/kos.html ]; then
  echo "→ Generuję przeglądarkę strukturalną…"
  $PY kos/export_web.py >/dev/null
fi

# 4) baza wektorowa (proza + fakty). Jeśli brak — trzeba zbudować raz (embeddingi).
if [ ! -f data/chroma/chroma.sqlite3 ]; then
  echo "⚠ Brak bazy wektorowej (data/chroma). Rozpakuj dołączoną paczkę danych"
  echo "  albo zbuduj raz:  $PY scripts/04_build_vectordb.py   (potrzebny data/text/chunks.jsonl)"
fi

# 5) backend LLM — ollama (domyślny) albo claude, patrz config.bat/README
KOS_BACKEND="${KOS_BACKEND:-ollama}"
if [ "$KOS_BACKEND" = "claude" ]; then
  if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ℹ Brak ANTHROPIC_API_KEY — przeglądarka zadziała, czat zwróci błąd."
    echo "  Ustaw klucz:  export ANTHROPIC_API_KEY=sk-ant-…   (z console.anthropic.com)"
  fi
elif ! command -v ollama >/dev/null 2>&1; then
  echo "⚠ Nie znaleziono komendy 'ollama' — zainstaluj z ollama.com albo"
  echo "  przełącz KOS_BACKEND=claude."
fi

PORT="${PORT:-8000}"
echo ""
echo "════════════════════════════════════════════════════════"
echo "  Otwórz w przeglądarce:"
echo "    Czat z Mistrzem Gry:      http://127.0.0.1:$PORT/"
echo "    Przeglądarka (bez API):   http://127.0.0.1:$PORT/przegladarka"
echo "════════════════════════════════════════════════════════"
echo ""
exec $PY agent/server.py --port "$PORT"
