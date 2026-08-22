@echo off
REM BDM UYAP GIRIS - hizli baslatici
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Sanal ortam bulunamadi. Once kurulum yapin:
  echo   python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)
.venv\Scripts\python.exe main.py
