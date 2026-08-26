@echo off
title Building Raft Launcher Executable...
echo ===================================================
echo   BUILDING RAFT MULTIPLAYER LAUNCHER (.EXE)
echo ===================================================
echo.

REM Run PyInstaller
python -m PyInstaller --noconsole --onefile --name "RaftLauncher" main.py

echo.
if %errorlevel% equ 0 (
    echo ===================================================
    echo   BUILD BERHASIL!
    echo   File executable ada di folder: dist\RaftLauncher.exe
    echo ===================================================
) else (
    echo [ERROR] Terjadi kegagalan saat build.
)

pause
