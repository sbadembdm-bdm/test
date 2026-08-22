@echo off
setlocal EnableDelayedExpansion
title BDM UYAP GIRIS - Tek Tik EXE Olusturucu
cd /d "%~dp0"

echo ==================================================
echo   BDM UYAP GIRIS - TEK TIK EXE OLUSTURUCU
echo ==================================================
echo   Bu script her seyi otomatik yapar:
echo   1. Python yoksa indirip kurar (sessiz)
echo   2. Gerekli paketleri yukler
echo   3. Tek dosya EXE olusturur
echo ==================================================
echo.

REM --- Adim 1: Python bul veya kur ---
set "PYEXE="
for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
if not defined PYEXE (
    for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
)
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)

if defined PYEXE (
    echo [1/4] Python bulundu: !PYEXE!
) else (
    echo [1/4] Python bulunamadi. Otomatik indiriliyor... ^(~25 MB^)
    curl -L -o "%TEMP%\python-setup.exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    if errorlevel 1 (
        echo.
        echo HATA: Python indirilemedi. Internet baglantinizi kontrol edin.
        pause
        exit /b 1
    )
    echo       Python kuruluyor, lutfen bekleyin ^(1-2 dakika^)...
    "%TEMP%\python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    if not exist "!PYEXE!" (
        echo.
        echo HATA: Python kurulumu basarisiz oldu.
        echo Cozum: https://www.python.org/downloads/ adresinden manuel kurun,
        echo "Add python.exe to PATH" kutusunu isaretleyin, sonra bu scripti tekrar calistirin.
        pause
        exit /b 1
    )
    echo       Python kuruldu: !PYEXE!
)
echo.

REM --- Adim 2: Paketleri kur ---
echo [2/4] Gerekli paketler yukleniyor ^(1-3 dakika^)...
"!PYEXE!" -m pip install --upgrade pip --quiet
"!PYEXE!" -m pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo.
    echo HATA: Paket kurulumu basarisiz. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)
echo       Paketler hazir.
echo       Opsiyonel kart algilama paketi deneniyor...
"!PYEXE!" -m pip install PyKCS11 --quiet >nul 2>&1
if errorlevel 1 echo       PyKCS11 kurulamadi - onemli degil, kart on-kontrolu atlanir, giris etkilenmez.
echo.

REM --- Adim 3: EXE olustur ---
echo [3/4] EXE olusturuluyor ^(3-5 dakika surebilir, pencereyi kapatmayin^)...
"!PYEXE!" -m PyInstaller --noconfirm --clean ^
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
if not exist "dist\BDM-UYAP-GIRIS.exe" (
    echo.
    echo HATA: EXE olusturulamadi. Yukaridaki hata mesajlarini kontrol edin.
    pause
    exit /b 1
)
echo.

REM --- Adim 4: Config'i yanina kopyala ---
echo [4/4] Son dokunuslar...
if not exist "dist\config.json" copy /y config.example.json "dist\config.json" >nul
if exist task_examples.json copy /y task_examples.json "dist\task_examples.json" >nul

echo.
echo ==================================================
echo   TAMAMLANDI!
echo   EXE dosyaniz: dist\BDM-UYAP-GIRIS.exe
echo.
echo   1. dist klasorundeki config.json dosyasini
echo      duzenleyip PIN kodunuzu girin.
echo   2. BDM-UYAP-GIRIS.exe cift tiklayarak calistirin.
echo   3. Bu exe'yi config.json ile birlikte istediginiz
echo      bilgisayara kopyalayabilirsiniz - Python gerekmez.
echo ==================================================
echo.
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\BDM UYAP GIRIS.lnk'); $lnk.TargetPath = (Resolve-Path 'dist\BDM-UYAP-GIRIS.exe').Path; $lnk.WorkingDirectory = (Resolve-Path 'dist').Path; $lnk.IconLocation = (Resolve-Path 'dist\BDM-UYAP-GIRIS.exe').Path + ',0'; $lnk.Save()" >nul 2>&1
echo       Masaustune "BDM UYAP GIRIS" kisayolu eklendi.
start "" explorer "dist"
pause
