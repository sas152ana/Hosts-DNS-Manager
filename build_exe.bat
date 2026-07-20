@echo off
REM ============================================================
REM  Сборка HostsDnsManager.exe (запускать на Windows)
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/3] Установка зависимостей...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo [2/3] Сборка exe...
python -m PyInstaller --noconfirm --clean --windowed --onefile --uac-admin ^
  --name HostsDnsManager ^
  --icon "data\icon.ico" ^
  --add-data "data;data" ^
  main.py
if errorlevel 1 goto :error

echo [3/3] Готово! Файл: dist\HostsDnsManager.exe
explorer dist
goto :eof

:error
echo.
echo ОШИБКА сборки. Убедитесь, что установлен Python 3.9+ и есть интернет.
pause
