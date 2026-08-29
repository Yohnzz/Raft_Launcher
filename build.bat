@echo off
title Raft Launcher - TEST BUILD

echo ========================================
echo       RAFT LAUNCHER TEST BUILD
echo ========================================

taskkill /F /IM RaftLauncher.exe >nul 2>&1

echo.
echo [1/4] Cleaning old build...
rmdir /S /Q build >nul 2>&1
rmdir /S /Q dist >nul 2>&1
del /Q RaftLauncher.spec >nul 2>&1

echo.
echo [2/4] Checking Python...
python --version
python -c "import sys; print(sys.executable)"
echo.

echo [3/4] Checking PyInstaller...
python -m PyInstaller --version
echo.

echo [4/4] Building ONEFILE executable...
set ICON_FLAG=
set DATA_FLAG=
if exist "app_icon.ico" (
    set "ICON_FLAG=--icon=app_icon.ico"
    set "DATA_FLAG=--add-data=app_icon.ico;."
)

python -m PyInstaller ^
    --clean ^
    --noconsole ^
    --onefile ^
    %ICON_FLAG% ^
    %DATA_FLAG% ^
    --name "RaftLauncher" ^
    main.py

echo.

if %errorlevel% equ 0 (
    echo ========================================
    echo [SUCCESS] Build Berhasil!
    echo File: dist\RaftLauncher.exe
    echo ========================================
) else (
    echo ========================================
    echo [ERROR] Build Gagal!
    echo ========================================
)

pause