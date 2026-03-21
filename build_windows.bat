@echo off
setlocal
cd /d "%~dp0"

echo Installing requirements...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

echo Building Windows EXE...
py -m PyInstaller ^
  --noconsole ^
  --onefile ^
  --name UniversalFileConverterHub ^
  --collect-all imageio_ffmpeg ^
  universal_converter_hub.py

echo.
echo Build complete.
echo EXE path: dist\UniversalFileConverterHub.exe
pause
