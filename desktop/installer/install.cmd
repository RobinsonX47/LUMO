@echo off
setlocal

set "APPDIR=%LocalAppData%\Programs\LUMO"

if exist "%APPDIR%" rmdir /s /q "%APPDIR%"
mkdir "%APPDIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%~dp0app.zip' -DestinationPath '%APPDIR%' -Force"
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $shell=New-Object -ComObject WScript.Shell; $shortcut=$shell.CreateShortcut($desktop + '\\LUMO.lnk'); $shortcut.TargetPath='%APPDIR%\\LUMO-Desktop.exe'; $shortcut.WorkingDirectory='%APPDIR%'; $shortcut.IconLocation='%APPDIR%\\LUMO-Desktop.exe,0'; $shortcut.Save()"

start "" "%APPDIR%\LUMO-Desktop.exe"
exit /b 0
