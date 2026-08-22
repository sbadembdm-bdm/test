' BDM UYAP GIRIS - izleme modunu pencere gostermeden (gizli) baslatir
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Run "run_watch.bat", 0, False
