#!/bin/bash
#
# start.command - macOS one-click deploy for AiStock.
# Equivalent of start.bat on Windows.
#
# Assumes docker (Docker Desktop) and git are already installed.
# No other prerequisites required: bash, curl, lsof, sed, find are all
# shipped with macOS by default. Python is not needed on the host
# (backend runs inside Docker).

set -u

# UTF-8 locale guard. macOS launchd often hands down an empty locale to
# double-clicked .command files; git, sed, docker-compose all misbehave
# when LC_ALL is unset ("Could not set locale"). en_US.UTF-8 is always
# present on macOS.
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=========================================="
echo "   AiStock One-Click Deploy (macOS)"
echo "=========================================="
echo ""

pause_exit() {
    local code="${1:-1}"
    echo ""
    read -r -p "Press Enter to exit..." _
    exit "$code"
}

# =============================================
# [1/6] Clone or update code
#     Three cases to handle, mirroring start.bat:
#       A. script lives inside the repo itself (.git present)
#       B. previous run left an aistock/ subfolder (aistock/.git)
#       C. fresh install -> clone
# =============================================
echo "[1/6] Getting latest code..."
GOT_CODE=0

if [ -d ".git" ]; then
    echo "Pulling latest from GitHub..."
    if ! git pull; then
        echo "[WARN] git pull failed, continuing with existing code."
    fi
    GOT_CODE=1
fi

if [ "$GOT_CODE" -eq 0 ] && [ -d "aistock/.git" ]; then
    cd aistock
    SCRIPT_DIR="$(pwd)"
    echo "Pulling latest from GitHub..."
    if ! git pull; then
        echo "[WARN] git pull failed, continuing with existing code."
    fi
    GOT_CODE=1
fi

if [ "$GOT_CODE" -eq 0 ]; then
    echo "Cloning from GitHub..."
    if ! git clone https://github.com/callmefisher/aistock.git aistock; then
        echo "[ERROR] git clone failed. Check your network connection."
        pause_exit 1
    fi
    cd aistock
    SCRIPT_DIR="$(pwd)"
fi

echo "[OK] Code ready at: $SCRIPT_DIR"

# =============================================
# [2/6] Normalize line endings (only relevant if repo was
#      touched on Windows with autocrlf=true, but cheap insurance).
#      Uses `tr -d '\r'` instead of sed -i to sidestep BSD-vs-GNU
#      sed incompatibility (a Homebrew GNU sed in PATH breaks `sed -i ''`).
# =============================================
echo ""
echo "[2/6] Normalizing line endings..."
strip_cr() {
    local f="$1"
    [ -f "$f" ] || return 0
    # Skip files with no CR to avoid unnecessary writes / mtime churn.
    if LC_ALL=C grep -q $'\r' "$f" 2>/dev/null; then
        local tmp
        tmp="$(mktemp "${f}.XXXXXX")" || return 0
        tr -d '\r' < "$f" > "$tmp" && mv -f "$tmp" "$f"
    fi
}
while IFS= read -r -d '' f; do
    strip_cr "$f"
done < <(find . -maxdepth 3 -type f \( -name '*.sh' -o -name '*.command' \) -print0 2>/dev/null)
for f in .env .env.example; do
    strip_cr "$f"
done
echo "[OK] Line endings normalized."

# =============================================
# [3/6] Check .env
# =============================================
echo ""
echo "[3/6] Checking .env config..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[OK] .env created from .env.example with default values."
    else
        echo "[ERROR] No .env or .env.example found. Cannot continue."
        pause_exit 1
    fi
else
    echo "[OK] .env found."
fi

# =============================================
# [4/6] Ensure Docker is running
#     On macOS, Docker Desktop installs /Applications/Docker.app
#     and provides the `docker` CLI in PATH. Start it via `open -a`
#     and poll `docker info` until ready.
# =============================================
echo ""
echo "[4/6] Checking Docker..."

if ! command -v docker >/dev/null 2>&1; then
    echo "[ERROR] 'docker' command not found. Please install Docker Desktop:"
    echo "        https://www.docker.com/products/docker-desktop"
    pause_exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker not running. Starting Docker Desktop..."
    if [ -d "/Applications/Docker.app" ]; then
        open -a Docker
    elif [ -d "$HOME/Applications/Docker.app" ]; then
        open -a "$HOME/Applications/Docker.app"
    else
        echo "[ERROR] Docker Desktop not found. Please install from:"
        echo "        https://www.docker.com/products/docker-desktop"
        pause_exit 1
    fi

    echo "Waiting for Docker to be ready (max 120s)..."
    RETRY=0
    while [ "$RETRY" -lt 24 ]; do
        sleep 5
        RETRY=$((RETRY + 1))
        if docker info >/dev/null 2>&1; then
            break
        fi
    done

    if ! docker info >/dev/null 2>&1; then
        echo "[ERROR] Docker did not start within 120 seconds. Please start it manually."
        pause_exit 1
    fi
fi
echo "[OK] Docker is running."

# =============================================
# [5/6] Smart build (skips if git fingerprint unchanged)
# =============================================
echo ""
echo "[5/6] Smart build (skips if no changes)..."
chmod +x ./deploy.sh 2>/dev/null || true
if ! bash ./deploy.sh smart-build; then
    echo ""
    echo "[ERROR] Build failed. If 'cannot allocate memory':"
    echo "        Open Docker Desktop > Settings > Resources, set Memory to 4GB+."
    pause_exit 1
fi
echo "[OK] Build step done."

# =============================================
# [6/6] Start services
# =============================================
echo ""
echo "[6/6] Starting services..."
if ! bash ./deploy.sh restart; then
    echo "[ERROR] Failed to start services."
    pause_exit 1
fi
echo "[OK] Services started."

# =============================================
# Wait for frontend
# =============================================
echo ""
echo "Waiting for frontend at http://localhost:7654 ..."
RETRY=0
while [ "$RETRY" -lt 20 ]; do
    sleep 3
    RETRY=$((RETRY + 1))
    if curl -sf http://localhost:7654 -o /dev/null; then
        break
    fi
done

if ! curl -sf http://localhost:7654 -o /dev/null; then
    echo "[WARN] Frontend slow to start, opening anyway..."
fi

# =============================================
# Done
# =============================================
echo ""
echo "=========================================="
echo "   SUCCESS - AiStock is running"
echo "   Frontend : http://localhost:7654"
echo "   API Docs : http://localhost:8000/docs"
echo "=========================================="
echo ""
open "http://localhost:7654" >/dev/null 2>&1 || true

read -r -p "Press Enter to close this window..." _
exit 0
