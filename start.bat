@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title AiStock - Deploying...
cd /d "%~dp0"

echo.
echo ==========================================
echo   AiStock One-Click Deploy
echo ==========================================
echo.

:: =============================================
:: [0] Locate Git Bash
:: =============================================
echo [0/6] Locating Git Bash...
set "BASH="
for %%P in (
    "C:\Program Files\Git\bin\bash.exe"
    "C:\Program Files (x86)\Git\bin\bash.exe"
) do (
    if exist "%%~P" if not defined BASH set "BASH=%%~P"
)
if not defined BASH (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\GitForWindows" /v "InstallPath" 2^>nul') do (
        if exist "%%B\bin\bash.exe" set "BASH=%%B\bin\bash.exe"
    )
)
if not defined BASH (
    echo [ERROR] Git for Windows not found. Please install from:
    echo         https://git-scm.com/download/win
    pause
    exit /b 1
)
echo [OK] Git Bash: !BASH!

:: =============================================
:: [1] Clone or update code
::     Three cases handled explicitly to avoid the "aistock subfolder"
::     collision bug: if the bat lives in a folder already named "aistock",
::     git clone creates aistock\aistock\ on first run. On re-runs .git
::     still won't exist in the bat's directory but aistock\.git will,
::     so we cd in and pull instead of trying to clone again.
:: =============================================
echo.
echo [1/6] Getting latest code...
set "GOT_CODE=0"

:: Case A: bat is inside the repo itself
if exist ".git" (
    echo Pulling latest from GitHub...
    git pull
    if !errorlevel! neq 0 (
        echo [WARN] git pull failed, continuing with existing code.
    )
    set "GOT_CODE=1"
)

:: Case B: already cloned to aistock\ subdirectory on a previous run
if !GOT_CODE! equ 0 (
    if exist "aistock\.git" (
        cd /d aistock
        echo Pulling latest from GitHub...
        git pull
        if !errorlevel! neq 0 (
            echo [WARN] git pull failed, continuing with existing code.
        )
        set "GOT_CODE=1"
    )
)

:: Case C: fresh install - clone for the first time
if !GOT_CODE! equ 0 (
    echo Cloning from GitHub...
    git clone https://github.com/callmefisher/aistock.git aistock
    if !errorlevel! neq 0 (
        echo [ERROR] git clone failed. Check your network connection.
        pause
        exit /b 1
    )
    cd /d aistock
    set "GOT_CODE=1"
)

echo [OK] Code ready.

:: =============================================
:: [2] Fix CRLF (Windows git may convert LF->CRLF)
::     - .sh files: bash execute fails with \r in shebang
::     - .env file: trailing \r in env vars breaks MySQL auth, JWT, URLs
::     Use "bash ./script.sh" everywhere to bypass execute-bit issue
::     (Windows git does not preserve +x permission bits)
:: =============================================
echo.
echo [2/6] Fixing line endings on shell scripts and .env...
"!BASH!" -c "find . -maxdepth 3 -name '*.sh' -exec sed -i 's/\r$//' {} \; 2>/dev/null; true"
"!BASH!" -c "[ -f .env ] && sed -i 's/\r$//' .env; [ -f .env.example ] && sed -i 's/\r$//' .env.example; true"
echo [OK] Line endings fixed.

:: =============================================
:: [3] Check .env
:: =============================================
echo.
echo [3/6] Checking .env config...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] .env created from .env.example with default values.
    ) else (
        echo [ERROR] No .env or .env.example found. Cannot continue.
        pause
        exit /b 1
    )
) else (
    echo [OK] .env found.
)

:: =============================================
:: [4] Check / start Docker
::     Label :wait_docker must NOT be inside an if(...) block -
::     Windows batch parser terminates the block at the label line.
::     Use call :start_docker subroutine instead.
:: =============================================
echo.
echo [4/6] Checking Docker...
docker info >nul 2>&1
if !errorlevel! neq 0 (
    call :start_docker
    if !errorlevel! neq 0 (
        pause
        exit /b 1
    )
)
echo [OK] Docker is running.

:: =============================================
:: [5] Build images
:: =============================================
echo.
echo [5/6] Building images (first run: 5-10 min, later runs use cache)...
"!BASH!" -c "bash ./deploy.sh build"
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Build failed. See output above for details.
    pause
    exit /b 1
)
echo [OK] Build complete.

:: =============================================
:: [6] Start services
:: =============================================
echo.
echo [6/6] Starting services...
"!BASH!" -c "bash ./deploy.sh restart"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to start services.
    pause
    exit /b 1
)
echo [OK] Services started.

:: =============================================
:: Wait for frontend
:: =============================================
echo.
echo Waiting for frontend at http://localhost:7654 ...
set RETRY=0
:wait_web
timeout /t 3 /nobreak >nul
set /a RETRY+=1
"!BASH!" -c "curl -sf http://localhost:7654 -o /dev/null"
if !errorlevel! neq 0 (
    if !RETRY! lss 20 goto :wait_web
    echo [WARN] Frontend slow to start, opening anyway...
)

:: =============================================
:: Done
:: =============================================
echo.
echo ==========================================
echo   SUCCESS - AiStock is running
echo   Frontend : http://localhost:7654
echo   API Docs : http://localhost:8000/docs
echo ==========================================
echo.
start http://localhost:7654
title AiStock - Running
pause
exit /b 0

:: =============================================
:: Subroutine: find and start Docker Desktop,
:: then wait until "docker info" succeeds.
:: Avoids putting a label inside an if block.
:: =============================================
:start_docker
echo Docker not running. Starting Docker Desktop...

:: Check hardcoded paths first (avoids %PROGRAMFILES% space-tokenization
:: bug in for-loop lists). Then fall back to %LOCALAPPDATA% via if exist.
set "DOCKER_EXE="
for %%P in (
    "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"
) do (
    if exist "%%~P" if not defined DOCKER_EXE set "DOCKER_EXE=%%~P"
)
if not defined DOCKER_EXE (
    if exist "%LOCALAPPDATA%\Programs\Docker\Docker\Docker Desktop.exe" (
        set "DOCKER_EXE=%LOCALAPPDATA%\Programs\Docker\Docker\Docker Desktop.exe"
    )
)
if not defined DOCKER_EXE (
    echo [ERROR] Docker Desktop not found. Please install from:
    echo         https://www.docker.com/products/docker-desktop
    exit /b 1
)

start "" "!DOCKER_EXE!"
echo Waiting for Docker to be ready (max 120s)...
set RETRY=0
:wait_docker
timeout /t 5 /nobreak >nul
set /a RETRY+=1
docker info >nul 2>&1
if !errorlevel! equ 0 exit /b 0
if !RETRY! lss 24 goto :wait_docker
echo [ERROR] Docker did not start within 120 seconds. Please start it manually.
exit /b 1
