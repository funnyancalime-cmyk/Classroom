@echo off
setlocal

if not exist "dist\SeatingOrder.exe" (
  echo Chybi dist\SeatingOrder.exe
  echo Nejdriv spust:
  echo   scripts\build_windows.bat
  exit /b 1
)

where iscc >nul 2>nul
if %errorlevel% neq 0 (
  echo Inno Setup Compiler (iscc) neni dostupny v PATH.
  echo Nainstaluj Inno Setup a pridej ISCC.exe do PATH.
  exit /b 1
)

echo Building installer...
iscc installer\windows\SeatingOrder.iss
if %errorlevel% neq 0 (
  echo Build installeru selhal.
  exit /b 1
)

echo Hotovo. Installer je ve slozce dist-installer\
exit /b 0
