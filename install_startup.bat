@echo off
REM Windows oturum acilisinda BDM UYAP GIRIS'i (gizli izleme modu) otomatik baslatir
setlocal
schtasks /Create /SC ONLOGON /TN "BDM UYAP GIRIS" /TR "wscript.exe \"%~dp0start_watch_silent.vbs\"" /F
if %errorlevel%==0 (
  echo Otomatik baslatma eklendi. Bilgisayari her actiginizda izleme modu calisacak.
) else (
  echo Gorev olusturulamadi. Bu dosyayi Yonetici olarak calistirmayi deneyin.
)
pause
