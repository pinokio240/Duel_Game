@echo off
chcp 65001 >nul
cls
cd /d "%~dp0"

echo ============================================
echo   Обновление DUEL до последней версии
echo ============================================
echo.

set TMPZIP=%TEMP%\duel_update.zip
set TMPDIR=%TEMP%\duel_update

rem --- 1) качаем свежий ZIP с GitHub ---
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://codeload.github.com/pinokio240/Duel_Game/zip/refs/heads/main' -OutFile '%TMPZIP%' -TimeoutSec 180 -UseBasicParsing } catch { exit 1 }"

if errorlevel 1 (
    echo.
    echo   Не удалось скачать обновление с GitHub.
    echo   Проверьте интернет. Если GitHub не открывается —
    echo   скачайте ZIP вручную: кнопка Code, потом Download ZIP.
    echo.
    pause
    exit /b
)
echo [1/3] Архив скачан.

rem --- 2) распаковываем во временную папку ---
if exist "%TMPDIR%" rmdir /s /q "%TMPDIR%"
powershell -NoProfile -Command "Expand-Archive -Path '%TMPZIP%' -DestinationPath '%TMPDIR%' -Force"
if errorlevel 1 (
    echo   Не удалось распаковать архив.
    pause
    exit /b
)
echo [2/3] Архив распакован.

rem --- 3) копируем новые файлы поверх старых, статистику не трогаем ---
if not exist "%TMPDIR%\Duel_Game-main" (
    echo   В архиве неожиданная структура — обновите вручную с сайта.
    pause
    exit /b
)
xcopy /e /i /y "%TMPDIR%\Duel_Game-main\*" . >nul
echo [3/3] Файлы обновлены. Статистика duel_stats.json сохранена.
echo.
echo   Готово! Запускайте игру через PLAY.bat
echo.
pause
