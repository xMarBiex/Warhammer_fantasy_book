@echo off
REM Uruchomienie lokalne (Windows) - Warhammer Fantasy KOS.
REM Uzycie:  set ANTHROPIC_API_KEY=sk-ant-...   potem dwuklik na start.bat
setlocal
cd /d "%~dp0"

REM 1) srodowisko Pythona
if not exist ".venv\Scripts\python.exe" (
  echo Tworze srodowisko .venv i instaluje zaleznosci...
  python -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt
)
set PY=.venv\Scripts\python

REM 2) baza KOS (SQL+Graf) z tables\*.json
if not exist "data\kos\kos.db" (
  echo Buduje baze KOS...
  %PY% kos\build_kos.py
)

REM 3) przegladarka strukturalna (statyczna, bez API)
if not exist "web\kos.html" (
  echo Generuje przegladarke strukturalna...
  %PY% kos\export_web.py
)

REM 4) baza wektorowa
if not exist "data\chroma\chroma.sqlite3" (
  echo [!] Brak bazy wektorowej data\chroma. Rozpakuj kos-dane.tar.gz
  echo     albo zbuduj raz:  %PY% scripts\04_build_vectordb.py
)

REM 5) klucz API - tylko do czatu; przegladarka dziala bez niego
if "%ANTHROPIC_API_KEY%"=="" (
  echo [i] Brak ANTHROPIC_API_KEY - przegladarka zadziala, czat zwroci blad.
  echo     Ustaw:  set ANTHROPIC_API_KEY=sk-ant-...
)

if "%PORT%"=="" set PORT=8000
echo.
echo ============================================================
echo   Otworz w przegladarce:
echo     Czat z Mistrzem Gry:     http://127.0.0.1:%PORT%/
echo     Przegladarka (bez API):  http://127.0.0.1:%PORT%/przegladarka
echo ============================================================
echo.
%PY% agent\server.py --port %PORT%
endlocal
