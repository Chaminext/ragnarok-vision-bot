@echo off
cd /d "%~dp0..\.."
python tools\memory_probe\ro_memory_probe.py --pretty --include mobs
pause
