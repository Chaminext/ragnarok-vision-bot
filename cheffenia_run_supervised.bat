@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PY=python
if exist ".venv311\Scripts\python.exe" set PY=.venv311\Scripts\python.exe

set RO_YOLO_MODEL=models\cheffenia_hard_yolo.pt
set RO_VISUAL_LOG=1
set RO_VISUAL_LOG_VIDEO=1

echo ============================================================
echo   Cheffenia Hard -- run supervisionada
echo ============================================================
echo.
echo   Modelo     : %RO_YOLO_MODEL%
echo   Visual log : ON
echo   Parar      : F12 ou mouse no canto sup-esq
echo.
echo   ATENCAO: teste curto, supervisionado.
echo ============================================================
echo.

%PY% ro_bot.py
pause
