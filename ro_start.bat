@echo off
chcp 65001 > nul
color 0A
cls

echo ============================================================
echo   RO BOT -- Launcher
echo ============================================================
echo.
echo   Janela alvo  : 4th ^| Gepard Shield 3.0
echo   Parar o bot  : F12  ^|  ou mouse no canto sup-esq
echo.
echo   Iniciando...
echo ============================================================
echo.

python ro_bot.py %*

echo.
echo ============================================================
echo   Sessao encerrada.
echo ============================================================
echo.
pause
