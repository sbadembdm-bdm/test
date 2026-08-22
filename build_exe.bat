@echo off
REM BDM-UYAP-GIRIS.exe olusturur (tek dosya)
pyinstaller --noconfirm --clean ^
  --name "BDM-UYAP-GIRIS" ^
  --onefile ^
  --icon "assets\icon.ico" ^
  --add-data "assets;assets" ^
  --add-data "config.example.json;." ^
  --windowed ^
  --collect-all selenium ^
  --collect-all pywinauto ^
  --collect-all keyring ^
  --collect-all winotify ^
  --collect-all pystray ^
  --collect-all PIL ^
  main.py
echo.
echo dist\BDM-UYAP-GIRIS.exe olusturuldu. config.json'i exe ile ayni klasore koyun.
pause
