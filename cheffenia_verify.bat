@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PY=python
if exist ".venv311\Scripts\python.exe" set PY=.venv311\Scripts\python.exe

set RO_YOLO_MODEL=models\cheffenia_hard_yolo.pt
set RO_VISUAL_LOG=0

echo ============================================================
echo   Cheffenia Hard -- verificar overlay
echo ============================================================
echo.
echo   Modelo: %RO_YOLO_MODEL%
echo   Q ou ESC fecha o verificador.
echo.

%PY% ro_bot.py --verificar
pause
