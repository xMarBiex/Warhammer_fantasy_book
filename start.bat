@echo off
REM Uruchomienie lokalne (Windows) - Warhammer Fantasy KOS.
REM Konfiguracja (backend LLM, haslo, model) wczytywana z config.bat - patrz
REM config.example.bat. Domyslny backend to lokalny Bielik przez Ollame.
setlocal
cd /d "%~dp0"

REM 0) lokalna konfiguracja (nie jest w gicie - patrz .gitignore)
if not exist "config.bat" (
  copy /y "config.example.bat" "config.bat" >nul
  echo.
  echo [i] Utworzylem plik config.bat z szablonu.
  echo     Otworz go w Notatniku, wpisz swoj ANTHROPIC_API_KEY ^(i opcjonalnie
  echo     KOS_PASSWORD / KOS_MODEL^), zapisz i uruchom start.bat ponownie.
  echo.
  notepad config.bat
  endlocal
  exit /b
)
call config.bat

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

REM 5) backend LLM - ollama (domyslnie) albo claude, patrz config.bat
if "%KOS_BACKEND%"=="" set KOS_BACKEND=ollama
if "%KOS_BACKEND%"=="claude" (
  if "%ANTHROPIC_API_KEY%"=="" (
    echo [i] Brak ANTHROPIC_API_KEY - przegladarka zadziala, czat zwroci blad.
    echo     Uzupelnij go w config.bat.
  )
) else (
  where ollama >nul 2>nul
  if errorlevel 1 (
    echo [!] Nie znaleziono komendy "ollama" w PATH - zainstaluj z ollama.com,
    echo     albo przelacz KOS_BACKEND=claude w config.bat.
  ) else (
    ollama list | findstr /i "bielik" >nul 2>nul
    if errorlevel 1 (
      echo [!] Model %KOS_MODEL% nie jest jeszcze pobrany. Uruchom:
      echo       ollama pull %KOS_MODEL%
    )
  )
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
