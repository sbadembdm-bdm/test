@echo off
title Masaustu Kisayolu Olustur
cd /d "%~dp0"

set "EXE=%~dp0dist\BDM-UYAP-GIRIS.exe"
if not exist "%EXE%" set "EXE=%~dp0BDM-UYAP-GIRIS.exe"
if not exist "%EXE%" (
    echo HATA: BDM-UYAP-GIRIS.exe bulunamadi.
    echo Once make_exe_oneclick.bat ile exe olusturun.
    pause
    exit /b 1
)

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\BDM UYAP GIRIS.lnk'); $lnk.TargetPath = '%EXE%'; $lnk.WorkingDirectory = '%~dp0dist'; $lnk.IconLocation = '%EXE%,0'; $lnk.Description = 'UYAP otomatik giris'; $lnk.Save()"

if errorlevel 1 (
    echo HATA: Kisayol olusturulamadi.
) else (
    echo Masaustune "BDM UYAP GIRIS" kisayolu olusturuldu.
)
pause
