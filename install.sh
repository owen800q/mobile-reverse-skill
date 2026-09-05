#!/usr/bin/env bash
# Install the reverse-skill into your Claude Code skills directory.
# Usage: ./install.sh [--link]   (--link symlinks instead of copying)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/skills/reverse-skill"
DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$DEST_DIR/reverse-skill"
MODE="copy"
[ "${1:-}" = "--link" ] && MODE="link"

if [ ! -f "$SRC/SKILL.md" ]; then
  echo "error: $SRC/SKILL.md not found" >&2; exit 1
fi

mkdir -p "$DEST_DIR"
rm -rf "$DEST"
if [ "$MODE" = "link" ]; then
  ln -s "$SRC" "$DEST"
  echo "linked  $DEST -> $SRC"
else
  cp -R "$SRC" "$DEST"
  echo "copied  $SRC -> $DEST"
fi

# Make helper scripts executable.
find "$DEST" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} + 2>/dev/null || true

echo "done. In Claude Code, invoke with:  /reverse-skill ./app.apk <feature or question>"
