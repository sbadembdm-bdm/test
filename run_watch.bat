@echo off
REM BDM UYAP GIRIS - arayuzsuz izleme modu (Windows baslangici icin)
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  ".venv\Scripts\pythonw.exe" main.py --watch
) else (
  pythonw main.py --watch
)
