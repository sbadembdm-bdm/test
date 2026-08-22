@echo off
REM Otomatik baslatmayi kaldirir
schtasks /Delete /TN "BDM UYAP GIRIS" /F
echo Otomatik baslatma kaldirildi.
pause
