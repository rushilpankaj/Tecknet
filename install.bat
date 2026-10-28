@echo off
rem Installs the Python packages needed to run from source. Run once.
cd /d "%~dp0"
py -m pip install -r requirements.txt
echo.
echo Done. Start the app with run.bat.
pause
