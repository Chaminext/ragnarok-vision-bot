@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PY=python
if exist ".venv311\Scripts\python.exe" set PY=.venv311\Scripts\python.exe

echo ============================================================
echo   Cheffenia Hard -- treino YOLO
echo ============================================================
echo.
echo   Dataset: datasets\cheffenia_hard_synth\dataset.yaml
echo   Modelo : models\cheffenia_hard_yolo.pt
echo.

%PY% ro_yolo_train.py --data datasets\cheffenia_hard_synth\dataset.yaml --output models\cheffenia_hard_yolo.pt --epochs 70 --batch 8 --imgsz 640 --device 0
if errorlevel 1 goto erro

echo.
echo OK. Teste com:
echo   cheffenia_verify.bat
echo.
pause
exit /b 0

:erro
echo.
echo [ERRO] Falha no treino Cheffenia.
pause
exit /b 1
