@echo off
title Rebuilding Raft Launcher
echo ========================================================
echo   REBUILDING RAFT LAUNCHER EXECUTABLE
echo ========================================================
taskkill /F /IM RaftLauncher.exe > nul 2>&1

set ICON_FLAG=
set DATA_FLAG=
if exist "app_icon.ico" (
    set "ICON_FLAG=--icon=app_icon.ico"
    set "DATA_FLAG=--add-data=app_icon.ico;."
) else if exist "icon.ico" (
    set "ICON_FLAG=--icon=icon.ico"
    set "DATA_FLAG=--add-data=icon.ico;."
) else if exist "raft.ico" (
    set "ICON_FLAG=--icon=raft.ico"
    set "DATA_FLAG=--add-data=raft.ico;."
)

python -m PyInstaller --noconsole --onefile %ICON_FLAG% %DATA_FLAG% --name "RaftLauncher" main.py
echo.
if %errorlevel% equ 0 (
    echo [SUCCESS] RaftLauncher.exe berhasil dibuat di folder dist\
) else (
    echo [ERROR] Gagal membuat executable.
)
pause
