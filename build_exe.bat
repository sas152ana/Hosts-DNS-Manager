@echo off
REM ============================================================
REM  Сборка HostsDnsManager.exe (запускать на Windows)
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo [1/3] Проверка и установка зависимостей...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo [2/3] Подготовка параметров сборщика...
set "ICON_PARAM="
if exist "data\icon.ico" (
    set "ICON_PARAM=--icon data\icon.ico"
    echo   - Найдена иконка: data\icon.ico
) else (
    echo   - Внимание: data\icon.ico не найдена, сборка со стандартной иконкой.
)

echo [3/3] Сборка единого EXE...
python -m PyInstaller --noconfirm --clean --windowed --onefile --uac-admin ^
  --name HostsDnsManager ^
  !ICON_PARAM! ^
  --add-data "data;data" ^
  main.py
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  СБОРКА УСПЕШНО ЗАВЕРШЕНА!
echo  Готовый файл: dist\HostsDnsManager.exe
echo ============================================================
explorer dist
goto :eof

:error
echo.
echo [!] ОШИБКА сборки. Убедитесь, что установлен Python 3.9+ и есть интернет.
pause