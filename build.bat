@echo off
rem Builds dist\TecknetControl\ (the app) and, if Inno Setup 6 is installed,
rem dist\TecknetControl-Setup-<version>.exe (the installer).
setlocal
cd /d "%~dp0"

py -m pip install -r requirements.txt pyinstaller || goto :error
py -m unittest discover -s tests -t . || goto :error
py tools\make_icon.py || goto :error
py -m PyInstaller --noconfirm --clean TecknetControl.spec || goto :error

set "ISCC="
for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do (
  if exist %%P set "ISCC=%%~P"
)
if defined ISCC (
  "%ISCC%" /Q installer\TecknetControl.iss || goto :error
  echo.
  echo Installer created in dist\
) else (
  echo.
  echo Inno Setup 6 not found: only dist\TecknetControl\ was built.
)
echo App folder: dist\TecknetControl\TecknetControl.exe
goto :end

:error
echo.
echo Build failed.
exit /b 1

:end
endlocal
