@echo off
setlocal

set ROOT=%~dp0
set ROOT_CLEAN=%ROOT:~0,-1%
cd /d "%ROOT%"
set SNAPSHOT_SCRIPT=%ROOT%tools\create_historical_snapshot.ps1
set STAGE_DIR=%ROOT%release_bins

if exist "%SNAPSHOT_SCRIPT%" (
  echo [0/6] Creating pre-build source snapshot...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SNAPSHOT_SCRIPT%" -RepoRoot "%ROOT_CLEAN%" -Reason "pre-build" >nul
)

echo [1/6] Building app one-file executable...
python -m PyInstaller --noconfirm --clean UniversalFileUtilitySuite.spec
if errorlevel 1 (
  echo App build failed.
  exit /b 1
)

echo [2/6] Building updater one-file executable...
python -m PyInstaller --noconfirm --clean UniversalFileUtilitySuite_Updater.spec
if errorlevel 1 (
  echo Updater build failed.
  exit /b 4
)

echo [3/6] Building installer (Inno Setup)...
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

echo [4/6] Staging executables in release_bins...
if not exist "%STAGE_DIR%" mkdir "%STAGE_DIR%"
copy /y "%ROOT%dist\UniversalFileUtilitySuite.exe" "%STAGE_DIR%\UniversalFileUtilitySuite.exe" >nul
copy /y "%ROOT%dist\UniversalFileUtilitySuite_Updater.exe" "%STAGE_DIR%\UniversalFileUtilitySuite_Updater.exe" >nul
copy /y "%ROOT%installer_output\UniversalFileUtilitySuite_Setup.exe" "%STAGE_DIR%\UniversalFileUtilitySuite_Setup.exe" >nul

if exist "%SNAPSHOT_SCRIPT%" (
  echo [5/6] Creating post-build source + artifact snapshot...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SNAPSHOT_SCRIPT%" -RepoRoot "%ROOT_CLEAN%" -Reason "release-build" -IncludeBuildOutputs >nul
)

echo [6/6] Done.
echo App EXE:      "%ROOT%dist\UniversalFileUtilitySuite.exe"
echo Updater EXE:  "%ROOT%dist\UniversalFileUtilitySuite_Updater.exe"
echo Installer:    "%ROOT%installer_output\UniversalFileUtilitySuite_Setup.exe"
echo Staged all in "%STAGE_DIR%"
endlocal
