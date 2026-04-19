@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title AiStock Launcher
cd /d "%~dp0"

::
:: win.bat - Windows entry point / bootstrapper for AiStock.
::
:: Responsibilities:
::   1. Try to download the latest start.bat from GitHub (30s total timeout).
::   2. If download succeeds and differs from the local copy, atomically
::      replace start.bat. If it fails, times out, or curl is missing,
::      fall back to the existing start.bat without aborting.
::   3. Hand control to start.bat via `call` so it runs in the same cmd
::      process (same window, same pause/exit semantics).
::
:: Why a separate bootstrapper instead of self-update inside start.bat?
::   cmd.exe parses .bat files by seeking back to the current byte offset
::   on every line. Replacing the .bat mid-execution makes cmd jump to
::   garbage offsets -> syntax errors, wrong labels. Updating a DIFFERENT
::   file (start.bat) from this one (win.bat) sidesteps the issue entirely.
::
:: Encoding rules (DO NOT VIOLATE):
::   - This file must be pure ASCII. No Chinese, no em-dash, no smart
::     quotes, no BOM. cmd parses .bat using the system ANSI code page
::     (GBK on Chinese Windows) - any non-ASCII byte corrupts the parser
::     state. See commit a48a8bc for the em-dash incident.
::   - chcp 65001 only changes runtime console output encoding; it does
::     NOT retroactively fix how cmd already parsed this source file.
::
:: Flags:
::   --no-update    Skip the update check (offline / debugging).
::

set "SKIP_UPDATE=0"
if /i "%~1"=="--no-update" set "SKIP_UPDATE=1"

set "RAW_URL=https://raw.githubusercontent.com/callmefisher/aistock/main/start.bat"
set "TMP_NEW=%~dp0start.bat.new"
set "TARGET=%~dp0start.bat"

if "!SKIP_UPDATE!"=="1" (
    echo [*] --no-update given, skipping update check.
    goto :run_start
)

echo [*] Checking for start.bat updates (30s timeout)...

where curl.exe >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARN] curl.exe not found. Skipping update check.
    goto :run_start
)

del /f /q "!TMP_NEW!" >nul 2>&1

:: curl flags:
::   -f  : fail on HTTP >=400 so errorlevel is non-zero
::   -s  : silent (no progress)
::   -S  : show errors even with -s
::   -L  : follow redirects (GitHub raw may 302)
::   --max-time 30 : total wall-clock budget incl. connect + transfer
:: Output is binary-written by curl, so no GBK/UTF-8 transcoding.
curl.exe -fsSL --max-time 30 -o "!TMP_NEW!" "!RAW_URL!"
set "DL_RC=!errorlevel!"

if not "!DL_RC!"=="0" (
    echo [WARN] Download failed or timed out ^(curl rc=!DL_RC!^). Using existing start.bat.
    del /f /q "!TMP_NEW!" >nul 2>&1
    goto :run_start
)

if not exist "!TMP_NEW!" (
    echo [WARN] Download reported success but file is missing. Using existing start.bat.
    goto :run_start
)

:: Sanity check: downloaded file must start with "@echo" to be a plausible
:: start.bat. Guards against an HTML error page sneaking past -f (shouldn't
:: happen with curl -f, but cheap insurance).
set "FIRST_LINE="
for /f "usebackq delims=" %%L in ("!TMP_NEW!") do (
    if not defined FIRST_LINE set "FIRST_LINE=%%L"
)
echo !FIRST_LINE! | findstr /b /i "@echo" >nul
if !errorlevel! neq 0 (
    echo [WARN] Downloaded file does not look like a .bat script. Discarding.
    del /f /q "!TMP_NEW!" >nul 2>&1
    goto :run_start
)

:: If no local start.bat yet, this is a first install: adopt the download.
if not exist "!TARGET!" (
    move /y "!TMP_NEW!" "!TARGET!" >nul
    if !errorlevel! neq 0 (
        echo [ERROR] Could not place start.bat. Check folder write permission.
        pause
        exit /b 1
    )
    echo [OK] Installed start.bat.
    goto :run_start
)

:: Compare byte-for-byte. If identical, no-op.
fc /b "!TARGET!" "!TMP_NEW!" >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] start.bat already up to date.
    del /f /q "!TMP_NEW!" >nul 2>&1
    goto :run_start
)

:: Different - swap it in. move /y is atomic on same volume.
move /y "!TMP_NEW!" "!TARGET!" >nul
if !errorlevel! neq 0 (
    echo [WARN] Could not replace start.bat ^(permission denied?^). Using existing version.
    del /f /q "!TMP_NEW!" >nul 2>&1
    goto :run_start
)
echo [OK] Updated to latest start.bat.

:run_start
if not exist "!TARGET!" (
    echo [ERROR] start.bat not found and could not be downloaded.
    echo         Check your network connection and try again.
    pause
    exit /b 1
)

:: call keeps execution in this same cmd window so start.bat's pause
:: and exit /b behave normally. Forward any remaining args (skip --no-update).
if /i "%~1"=="--no-update" (
    call "!TARGET!" %2 %3 %4 %5 %6 %7 %8 %9
) else (
    call "!TARGET!" %*
)
exit /b !errorlevel!
