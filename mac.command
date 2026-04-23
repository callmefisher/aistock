#!/bin/bash
#
# mac.command - macOS entry point / bootstrapper for AiStock.
# Double-clickable equivalent of win.bat.
#
# Responsibilities:
#   1. Try to download the latest start.command from GitHub (30s total timeout).
#   2. If download succeeds and differs from the local copy, atomically
#      replace start.command. If it fails, times out, or curl is missing,
#      fall back to the existing start.command without aborting.
#   3. Hand control to start.command in the same terminal window.
#
# Flags:
#   --no-update    Skip the update check (offline / debugging).
#
# Notes:
#   - UTF-8 safe: macOS bash handles UTF-8 source natively (unlike cmd.exe).
#   - Executable bit must be preserved: chmod +x mac.command start.command.
#     The repo tracks +x via git's index mode. If you clone via https and
#     still lose it, run: chmod +x mac.command start.command.

set -u

# Force a stable, UTF-8-safe locale. Some shells inherit LANG=zh_CN.GBK or
# an empty POSIX locale from launchd; both can break `cmp`, `grep`, and any
# downstream tool that reads UTF-8 paths. C.UTF-8 isn't on macOS, but
# en_US.UTF-8 is always present.
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Clear the Gatekeeper quarantine attribute on ourselves and siblings so
# subsequent double-clicks don't hit the "unidentified developer" dialog.
# Silent-fail: xattr always exists on macOS, but the attribute may not.
xattr -d com.apple.quarantine "$SCRIPT_DIR/mac.command" 2>/dev/null || true
[ -f "$SCRIPT_DIR/start.command" ] && \
    xattr -d com.apple.quarantine "$SCRIPT_DIR/start.command" 2>/dev/null || true

SKIP_UPDATE=0
if [ "${1:-}" = "--no-update" ]; then
    SKIP_UPDATE=1
    shift
fi

RAW_URL="https://raw.githubusercontent.com/callmefisher/aistock/main/start.command"
TARGET="$SCRIPT_DIR/start.command"
TMP_NEW="$SCRIPT_DIR/start.command.new"

run_start() {
    if [ ! -f "$TARGET" ]; then
        echo "[ERROR] start.command not found and could not be downloaded."
        echo "        Check your network connection and try again."
        read -r -p "Press Enter to exit..." _
        exit 1
    fi
    chmod +x "$TARGET" 2>/dev/null || true
    exec "$TARGET" "$@"
}

if [ "$SKIP_UPDATE" = "1" ]; then
    echo "[*] --no-update given, skipping update check."
    run_start "$@"
fi

echo "[*] Checking for start.command updates (30s timeout)..."

if ! command -v curl >/dev/null 2>&1; then
    echo "[WARN] curl not found. Skipping update check."
    run_start "$@"
fi

rm -f "$TMP_NEW" 2>/dev/null || true

# curl flags:
#   -f  : fail on HTTP >=400
#   -s  : silent
#   -S  : show errors even with -s
#   -L  : follow redirects
#   --max-time 30 : total wall-clock budget
if curl -fsSL --max-time 30 -o "$TMP_NEW" "$RAW_URL"; then
    DL_RC=0
else
    DL_RC=$?
fi

if [ "$DL_RC" -ne 0 ] || [ ! -s "$TMP_NEW" ]; then
    echo "[WARN] Download failed or empty (rc=$DL_RC). Using existing start.command."
    rm -f "$TMP_NEW" 2>/dev/null || true
    run_start "$@"
fi

# Sanity check: downloaded file must start with a shebang.
FIRST_LINE="$(head -n 1 "$TMP_NEW" 2>/dev/null || true)"
case "$FIRST_LINE" in
    \#!/*) ;;
    *)
        echo "[WARN] Downloaded file does not look like a shell script. Discarding."
        rm -f "$TMP_NEW" 2>/dev/null || true
        run_start "$@"
        ;;
esac

# First install: no local start.command -> adopt the download.
if [ ! -f "$TARGET" ]; then
    mv -f "$TMP_NEW" "$TARGET"
    chmod +x "$TARGET"
    xattr -d com.apple.quarantine "$TARGET" 2>/dev/null || true
    echo "[OK] Installed start.command."
    run_start "$@"
fi

# Compare byte-for-byte.
if cmp -s "$TARGET" "$TMP_NEW"; then
    echo "[OK] start.command already up to date."
    rm -f "$TMP_NEW" 2>/dev/null || true
    run_start "$@"
fi

# Different -> swap it in. mv is atomic on the same volume.
if mv -f "$TMP_NEW" "$TARGET"; then
    chmod +x "$TARGET"
    xattr -d com.apple.quarantine "$TARGET" 2>/dev/null || true
    echo "[OK] Updated to latest start.command."
else
    echo "[WARN] Could not replace start.command (permission denied?). Using existing version."
    rm -f "$TMP_NEW" 2>/dev/null || true
fi

run_start "$@"
