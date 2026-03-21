@echo off
setlocal

set ROOT=%~dp0
cd /d "%ROOT%"
set SNAPSHOT_SCRIPT=%ROOT%tools\create_historical_snapshot.ps1

if exist "%SNAPSHOT_SCRIPT%" (
  echo [0/5] Creating pre-build source snapshot...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SNAPSHOT_SCRIPT%" -RepoRoot "%ROOT%" -Reason "pre-build" >nul
)

echo [1/5] Building one-file executable...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name UniversalFileUtilitySuite --icon "assets\universal_file_utility_suite.ico" --add-data "assets\universal_file_utility_suite.ico;assets" modular_file_utility_suite.py
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo [2/5] Building installer (Inno Setup)...
set ISCC_PATH=
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
if "%ISCC_PATH%"=="" (
  echo Inno Setup compiler not found. Install Inno Setup 6 and run this file again.
  exit /b 2
)
"%ISCC_PATH%" "installer\UniversalFileUtilitySuite.iss"
if errorlevel 1 (
  echo Installer build failed.
  exit /b 3
)

if exist "%SNAPSHOT_SCRIPT%" (
  echo [3/5] Creating post-build source + artifact snapshot...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SNAPSHOT_SCRIPT%" -RepoRoot "%ROOT%" -Reason "release-build" -IncludeBuildOutputs >nul
)

echo [4/5] Done.
echo EXE:      "%ROOT%dist\UniversalFileUtilitySuite.exe"
echo Installer "%ROOT%installer_output\UniversalFileUtilitySuite_Setup.exe"
endlocal
