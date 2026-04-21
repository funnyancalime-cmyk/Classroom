@echo off
setlocal

where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
  echo PyInstaller neni nainstalovany.
  echo Nainstaluj build zavislosti:
  echo   pip install -r requirements-build.txt
  exit /b 1
)

echo Building Windows executable...
pyinstaller --noconfirm --onefile --windowed --name SeatingOrder app.py
if %errorlevel% neq 0 (
  echo Build selhal.
  exit /b 1
)

echo Hotovo. Vystup najdes ve slozce dist\SeatingOrder.exe
exit /b 0
