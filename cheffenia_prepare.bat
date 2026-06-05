@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PY=python
if exist ".venv311\Scripts\python.exe" set PY=.venv311\Scripts\python.exe

echo ============================================================
echo   Cheffenia Hard -- preparar dataset sintetico
echo ============================================================
echo.
echo   Saida: datasets\cheffenia_hard_synth
echo.

%PY% ro_cheffenia_assist.py --write-yaml --status
if errorlevel 1 goto erro

%PY% ro_synthetic_dataset.py --profile data\cheffenia_hard_mobs.json --out datasets\cheffenia_hard_synth --per-class 90 --negatives 120 --max-distractors 2
if errorlevel 1 goto erro

echo.
echo OK. Agora treine com:
echo   cheffenia_train.bat
echo.
pause
exit /b 0

:erro
echo.
echo [ERRO] Falha preparando Cheffenia.
pause
exit /b 1
