@echo off
chcp 65001 >nul
cls
cd /d "%~dp0"

set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python

if not defined PY (
    echo.
    echo   ============================================
    echo   Python не найден!
    echo   1. Скачайте Python: https://www.python.org/downloads/
    echo   2. При установке поставьте галочку "Add Python to PATH"
    echo   3. Запустите PLAY.bat ещё раз
    echo   ============================================
    echo.
    pause
    exit /b
)

%PY% -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Первый запуск: устанавливаю pygame и numpy, подождите минуту...
    %PY% -m pip install -r requirements.txt
)

echo Запускаю DUEL...
%PY% main.py

if errorlevel 1 (
    echo.
    echo Игра завершилась с ошибкой. Сделайте скриншот этого окна
    echo и пришлите его в чат.
    pause
)
