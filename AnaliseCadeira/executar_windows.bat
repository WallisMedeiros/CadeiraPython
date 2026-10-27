@echo off
cd /d "%~dp0"
echo Instalando dependencias...
python -m pip install -r requirements.txt
echo.
echo Abrindo http://localhost:5000 ...
start "" http://localhost:5000
python app.py
pause
