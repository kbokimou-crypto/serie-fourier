@echo off
REM ==========================================================
REM  Fabrication de SerieFourier.exe sous Windows
REM  Prerequis : Python 3.10+ installe (https://www.python.org)
REM             avec la case "Add python.exe to PATH" cochee.
REM  Facultatif : Inno Setup 6 (https://jrsoftware.org/isdl.php)
REM             pour fabriquer aussi l'installateur.
REM  Double-cliquez sur ce fichier : l'exe sera dans dist\
REM ==========================================================
cd /d "%~dp0"
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || goto :err
pyinstaller --noconfirm --onefile --windowed --name SerieFourier --hidden-import PIL._tkinter_finder --add-data "exemple_suite.csv;." fourier_app.py || goto :err
echo.
echo  [1/2] Programme termine : dist\SerieFourier.exe
echo.

REM ---- Installateur (Inno Setup) ----
set "ISCC="
where iscc >nul 2>nul && set "ISCC=iscc"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if defined ISCC goto :installer

echo  [2/2] Installateur NON fabrique : Inno Setup n'est pas installe sur ce PC.
echo        - dist\SerieFourier.exe fonctionne deja seul, sans installation.
echo        - Pour obtenir aussi SerieFourier_Setup.exe, installez Inno Setup 6
echo          depuis https://jrsoftware.org/isdl.php puis relancez ce script.
goto :fin

:installer
"%ISCC%" installer.iss || goto :err
echo.
echo  [2/2] Installateur FABRIQUE (pas encore installe) : Output\SerieFourier_Setup.exe
echo.
echo  ==^> Pour INSTALLER l'application, double-cliquez sur SerieFourier_Setup.exe
echo      dans le dossier Output qui va s'ouvrir.
start "" explorer "%~dp0Output"

:fin
echo.
pause
exit /b 0
:err
echo.
echo  ERREUR pendant la fabrication.
pause
exit /b 1
