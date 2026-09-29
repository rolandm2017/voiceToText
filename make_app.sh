#!/bin/bash
# Builds dist/voiceToText.app — a tiny macOS launcher for this repo's venv, so
# the microphone permission belongs to voiceToText instead of Terminal.
#
# The app runs .venv/bin/python main.py from this folder, so code edits need no
# rebuild. Rebuild only if you move the repo. (Rebuilding may make macOS ask
# for mic permission again.)
set -euo pipefail

NAME="voiceToText"
BUNDLE_ID="local.voicetotext"
REPO="$(cd "$(dirname "$0")" && pwd)"
APP="$REPO/dist/$NAME.app"

[ -x "$REPO/.venv/bin/python" ] || { echo "No .venv found — see README install steps"; exit 1; }

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>$NAME</string>
    <key>CFBundleDisplayName</key><string>$NAME</string>
    <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
    <key>CFBundleExecutable</key><string>$NAME</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleVersion</key><string>1.0</string>
    <key>LSMinimumSystemVersion</key><string>12.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>voiceToText transcribes your speech locally. Audio never leaves this Mac.</string>
</dict>
</plist>
EOF

# A compiled stub (not a shell script) that exec()s Python in place: same
# process, so macOS attributes the mic request to this app, not to Python.
cat > "$REPO/dist/launcher.c" <<'EOF'
#include <stdio.h>
#include <unistd.h>
int main(void) {
    if (chdir(REPO) != 0) { perror("chdir " REPO); return 1; }
    char *argv[] = { REPO "/.venv/bin/python", REPO "/main.py", NULL };
    execv(argv[0], argv);
    perror("execv");
    return 1;
}
EOF
clang -O2 -DREPO="\"$REPO\"" -o "$APP/Contents/MacOS/$NAME" "$REPO/dist/launcher.c"
rm "$REPO/dist/launcher.c"

# Ad-hoc signature: free, local-only; gives macOS a stable identity to attach
# the mic permission to.
codesign --force --sign - "$APP"

echo "Built $APP"
echo "Launch it from Finder (or: open \"$APP\"). Drag it to the Dock to keep it handy."
