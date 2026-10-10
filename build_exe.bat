@echo off
REM ==========================================================
REM  Fabrication de SerieFourier.exe sous Windows
REM  Prérequis : Python 3.10+ installé (https://www.python.org)
REM             avec la case "Add python.exe to PATH" cochée.
REM  Double-cliquez sur ce fichier : l'exe sera dans dist\
REM ==========================================================
cd /d "%~dp0"
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || goto :err
pyinstaller --noconfirm --onefile --windowed --name SerieFourier --hidden-import PIL._tkinter_finder fourier_app.py || goto :err
echo.
echo  Termine : dist\SerieFourier.exe
REM Installateur optionnel si Inno Setup est installe
where iscc >nul 2>nul && iscc installer.iss && echo  Installateur : Output\SerieFourier_Setup.exe
pause
exit /b 0
:err
echo  ERREUR pendant la fabrication.
pause
exit /b 1
