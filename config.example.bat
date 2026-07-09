@echo off
REM Konfiguracja lokalna — Warhammer Fantasy KOS.
REM
REM 1) Skopiuj ten plik jako "config.bat" (bez ".example") w tym samym folderze.
REM 2) Wpisz swoje wartości ponizej.
REM 3) config.bat NIE trafia do gita (jest w .gitignore) — klucz zostaje tylko
REM    na Twoim komputerze. start.bat wczytuje go automatycznie, jesli istnieje.

REM Klucz Claude API z console.anthropic.com — wymagany do czatu.
set ANTHROPIC_API_KEY=sk-ant-wklej-tutaj-swoj-klucz

REM Model agenta: claude-haiku-4-5 (najtaniej) / claude-sonnet-5 (tanio, dobra
REM jakosc) / claude-opus-4-8 (max jakosc, drozej).
set KOS_MODEL=claude-sonnet-5

REM Haslo dostepu — WYMAGANE, jesli udostepniasz serwer przez internet (np.
REM tunel Cloudflare). Zostaw puste (usun linie albo wpisz nic po "=") dla
REM pracy tylko na wlasnym komputerze (localhost).
set KOS_PASSWORD=

REM Port serwera (domyslnie 8000) — zwykle nie trzeba zmieniac.
REM set PORT=8000
