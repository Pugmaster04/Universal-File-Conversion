@echo off
setlocal

set ROOT=%~dp0
set ROOT_CLEAN=%ROOT:~0,-1%
cd /d "%ROOT%"
set SNAPSHOT_SCRIPT=%ROOT%tools\create_historical_snapshot.ps1
set STAGE_DIR=%ROOT%release_bins
set PACKAGE_VERSION=
for /f "usebackq delims=" %%i in (`python "%ROOT%tools\extract_app_version.py"`) do set PACKAGE_VERSION=%%i
if "%PACKAGE_VERSION%"=="" (
  echo Unable to determine APP_VERSION from modular_file_utility_suite.py
  exit /b 6
)
set STAGED_APP=FormatFoundry_%PACKAGE_VERSION%.exe
set STAGED_UPDATER=FormatFoundry_Updater_%PACKAGE_VERSION%.exe
set STAGED_SETUP=FormatFoundry_Setup_%PACKAGE_VERSION%.exe

if exist "%SNAPSHOT_SCRIPT%" (
  echo [0/7] Creating pre-build source snapshot...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SNAPSHOT_SCRIPT%" -RepoRoot "%ROOT_CLEAN%" -Reason "pre-build" >nul
)

echo [1/7] Building app one-file executable...
python -m PyInstaller --noconfirm --clean FormatFoundry.spec
if errorlevel 1 (
  echo App build failed.
  exit /b 1
)

echo [2/7] Building updater one-file executable...
python -m PyInstaller --noconfirm --clean FormatFoundry_Updater.spec
if errorlevel 1 (
  echo Updater build failed.
  exit /b 4
)

echo [3/7] Building installer (Inno Setup)...
set ISCC_PATH=
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
if "%ISCC_PATH%"=="" (
  echo Inno Setup compiler not found. Install Inno Setup 6 and run this file again.
  exit /b 2
)
"%ISCC_PATH%" "installer\FormatFoundry.iss"
if errorlevel 1 (
  echo Installer build failed.
  exit /b 3
)

echo [4/7] Staging executables in release_bins...
if not exist "%STAGE_DIR%" mkdir "%STAGE_DIR%"
if exist "%ROOT%dist\UniversalConversionHub_UCH.exe" del /f /q "%ROOT%dist\UniversalConversionHub_UCH.exe" >nul 2>nul
if exist "%ROOT%dist\UniversalConversionHub_HCB.exe" del /f /q "%ROOT%dist\UniversalConversionHub_HCB.exe" >nul 2>nul
if exist "%ROOT%dist\UniversalFileUtilitySuite.exe" del /f /q "%ROOT%dist\UniversalFileUtilitySuite.exe" >nul 2>nul
if exist "%ROOT%dist\UniversalConversionHub_UCH_Updater.exe" del /f /q "%ROOT%dist\UniversalConversionHub_UCH_Updater.exe" >nul 2>nul
if exist "%ROOT%dist\UniversalConversionHub_HCB_Updater.exe" del /f /q "%ROOT%dist\UniversalConversionHub_HCB_Updater.exe" >nul 2>nul
if exist "%ROOT%dist\UniversalFileUtilitySuite_Updater.exe" del /f /q "%ROOT%dist\UniversalFileUtilitySuite_Updater.exe" >nul 2>nul
if exist "%ROOT%installer_output\UniversalConversionHub_UCH_Setup.exe" del /f /q "%ROOT%installer_output\UniversalConversionHub_UCH_Setup.exe" >nul 2>nul
if exist "%ROOT%installer_output\UniversalConversionHub_HCB_Setup.exe" del /f /q "%ROOT%installer_output\UniversalConversionHub_HCB_Setup.exe" >nul 2>nul
if exist "%ROOT%installer_output\UniversalFileUtilitySuite_Setup.exe" del /f /q "%ROOT%installer_output\UniversalFileUtilitySuite_Setup.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalConversionHub_UCH.exe" del /f /q "%STAGE_DIR%\UniversalConversionHub_UCH.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalConversionHub_HCB.exe" del /f /q "%STAGE_DIR%\UniversalConversionHub_HCB.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalFileUtilitySuite.exe" del /f /q "%STAGE_DIR%\UniversalFileUtilitySuite.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalConversionHub_UCH_Updater.exe" del /f /q "%STAGE_DIR%\UniversalConversionHub_UCH_Updater.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalConversionHub_HCB_Updater.exe" del /f /q "%STAGE_DIR%\UniversalConversionHub_HCB_Updater.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalFileUtilitySuite_Updater.exe" del /f /q "%STAGE_DIR%\UniversalFileUtilitySuite_Updater.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalConversionHub_UCH_Setup.exe" del /f /q "%STAGE_DIR%\UniversalConversionHub_UCH_Setup.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalConversionHub_HCB_Setup.exe" del /f /q "%STAGE_DIR%\UniversalConversionHub_HCB_Setup.exe" >nul 2>nul
if exist "%STAGE_DIR%\UniversalFileUtilitySuite_Setup.exe" del /f /q "%STAGE_DIR%\UniversalFileUtilitySuite_Setup.exe" >nul 2>nul
if exist "%STAGE_DIR%\FormatFoundry.exe" del /f /q "%STAGE_DIR%\FormatFoundry.exe" >nul 2>nul
if exist "%STAGE_DIR%\FormatFoundry_Updater.exe" del /f /q "%STAGE_DIR%\FormatFoundry_Updater.exe" >nul 2>nul
if exist "%STAGE_DIR%\FormatFoundry_Setup.exe" del /f /q "%STAGE_DIR%\FormatFoundry_Setup.exe" >nul 2>nul
if exist "%STAGE_DIR%\FormatFoundry_*.exe" del /f /q "%STAGE_DIR%\FormatFoundry_*.exe" >nul 2>nul
if exist "%STAGE_DIR%\FormatFoundry_Updater_*.exe" del /f /q "%STAGE_DIR%\FormatFoundry_Updater_*.exe" >nul 2>nul
if exist "%STAGE_DIR%\FormatFoundry_Setup_*.exe" del /f /q "%STAGE_DIR%\FormatFoundry_Setup_*.exe" >nul 2>nul
copy /y "%ROOT%dist\FormatFoundry.exe" "%STAGE_DIR%\%STAGED_APP%" >nul
copy /y "%ROOT%dist\FormatFoundry_Updater.exe" "%STAGE_DIR%\%STAGED_UPDATER%" >nul
copy /y "%ROOT%installer_output\FormatFoundry_Setup.exe" "%STAGE_DIR%\%STAGED_SETUP%" >nul

echo [5/7] Validating install surface...
python "%ROOT%tools\validate_install_surface.py" --readme "%ROOT%README.md" --artifacts "%ROOT%release_bins" "%ROOT%installer_output" "%ROOT%dist" --required-asset "%STAGED_SETUP%"
if errorlevel 1 (
  echo Install surface validation failed.
  exit /b 5
)

if exist "%SNAPSHOT_SCRIPT%" (
  echo [6/7] Creating post-build source + artifact snapshot...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SNAPSHOT_SCRIPT%" -RepoRoot "%ROOT_CLEAN%" -Reason "release-build" -IncludeBuildOutputs >nul
)

echo [7/7] Done.
echo App EXE:      "%ROOT%dist\FormatFoundry.exe"
echo Updater EXE:  "%ROOT%dist\FormatFoundry_Updater.exe"
echo Installer:    "%ROOT%installer_output\FormatFoundry_Setup.exe"
echo Versioned public assets: "%STAGE_DIR%\%STAGED_APP%", "%STAGE_DIR%\%STAGED_UPDATER%", "%STAGE_DIR%\%STAGED_SETUP%"
endlocal

