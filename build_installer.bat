@echo off
title Building Raft Launcher Setup Installer
echo ========================================================
echo   BUILDING RAFT LAUNCHER STANDALONE + SETUP INSTALLER
echo ========================================================
echo.

taskkill /F /IM RaftLauncher.exe > nul 2>&1

echo [1/3] Building Executable with PyInstaller...
python -m PyInstaller --clean --noconsole --onefile --icon="app_icon.ico" --add-data="app_icon.ico;." --name "RaftLauncher" main.py

if %errorlevel% neq 0 (
    echo [ERROR] Gagal mem-build RaftLauncher.exe!
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] Locating Inno Setup Compiler (ISCC)...
set "ISCC_PATH="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC_PATH%"=="" (
    echo [WARNING] Inno Setup Compiler tidak ditemukan.
    echo Hanya RaftLauncher.exe yang selesai dibuild di dist\RaftLauncher.exe
    pause
    exit /b 0
)

echo [3/3] Compiling Setup Installer with Inno Setup...
"%ISCC_PATH%" installer.iss

echo.
if %errorlevel% equ 0 (
    echo ========================================================
    echo   [SUCCESS] BUILD INSTALLER BERHASIL!
    echo   File Installer: dist\RaftLauncher_Setup_v0.3.9.exe
    echo   File Executable: dist\RaftLauncher.exe
    echo ========================================================
) else (
    echo [ERROR] Gagal meng-compile Installer!
)

pause
