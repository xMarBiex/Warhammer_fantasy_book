@echo off
REM Konfiguracja lokalna — Warhammer Fantasy KOS.
REM
REM 1) Skopiuj ten plik jako "config.bat" (bez ".example") w tym samym folderze.
REM 2) Wpisz swoje wartości ponizej.
REM 3) config.bat NIE trafia do gita (jest w .gitignore) — klucz zostaje tylko
REM    na Twoim komputerze. start.bat wczytuje go automatycznie, jesli istnieje.

REM Backend LLM: "ollama" = lokalny Bielik (domyslnie), "claude" = Claude API.
set KOS_BACKEND=ollama

REM --- Backend ollama (lokalny) ---
REM Model musi byc pobrany:
REM   ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
REM 4.5B = wybrany po tescie 20 pytan (16/20 poprawnych vs 9/20 na 1.5B),
REM kosztem ~7x dluzszego czasu odpowiedzi (~1-5 min/pytanie na CPU bez GPU).
REM Wywolywanie narzedzi idzie wlasnym protokolem JSON wymuszonym schematem
REM (JSON Schema z enum na nazwach narzedzi - patrz agent/ollama_agent.py,
REM RESPONSE_SCHEMA), wiec dziala z kazdym modelem.
REM Zalezy Ci na szybkosci kosztem trafnosci?
REM   set KOS_MODEL=hf.co/speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0   (~30-100s/pytanie)
REM Chcesz jeszcze wyzsza jakosc (nieprzetestowana rownie dokladnie)?
REM   set KOS_MODEL=SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M   (32K kontekstu, bardzo wolny na CPU)
set KOS_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
set OLLAMA_URL=http://127.0.0.1:11434

REM --- Backend claude (opcjonalny, KOS_BACKEND=claude) ---
REM Klucz Claude API z console.anthropic.com — wymagany tylko dla tego backendu.
REM set ANTHROPIC_API_KEY=sk-ant-wklej-tutaj-swoj-klucz
REM set KOS_MODEL=claude-sonnet-5

REM Haslo dostepu — WYMAGANE, jesli udostepniasz serwer przez internet (np.
REM tunel Cloudflare). Zostaw puste (usun linie albo wpisz nic po "=") dla
REM pracy tylko na wlasnym komputerze (localhost).
set KOS_PASSWORD=

REM Port serwera (domyslnie 8000) — zwykle nie trzeba zmieniac.
REM set PORT=8000
