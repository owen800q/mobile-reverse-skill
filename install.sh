#!/usr/bin/env bash
# Install the reverse-skill into your Claude Code skills directory, along with
# its companion subagent (reverse-skill-worker) that pins the skill to the Fable
# model. The skill runs in a forked subagent by default (context: fork), so the
# agent must be installed too — the skill's `agent: reverse-skill-worker` points
# at it.
# Usage: ./install.sh [--link]   (--link symlinks instead of copying)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/skills/reverse-skill"
SRC_AGENT="$HERE/agents/reverse-skill-worker.md"
DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$DEST_DIR/reverse-skill"
DEST_AGENT_DIR="${CLAUDE_AGENTS_DIR:-$HOME/.claude/agents}"
DEST_AGENT="$DEST_AGENT_DIR/reverse-skill-worker.md"
MODE="copy"
[ "${1:-}" = "--link" ] && MODE="link"

if [ ! -f "$SRC/SKILL.md" ]; then
  echo "error: $SRC/SKILL.md not found" >&2; exit 1
fi
if [ ! -f "$SRC_AGENT" ]; then
  echo "error: $SRC_AGENT not found" >&2; exit 1
fi

mkdir -p "$DEST_DIR" "$DEST_AGENT_DIR"
rm -rf "$DEST"
rm -f "$DEST_AGENT"
if [ "$MODE" = "link" ]; then
  ln -s "$SRC" "$DEST"
  ln -s "$SRC_AGENT" "$DEST_AGENT"
  echo "linked  $DEST -> $SRC"
  echo "linked  $DEST_AGENT -> $SRC_AGENT"
else
  cp -R "$SRC" "$DEST"
  cp "$SRC_AGENT" "$DEST_AGENT"
  echo "copied  $SRC -> $DEST"
  echo "copied  $SRC_AGENT -> $DEST_AGENT"
fi

# Make helper scripts executable.
find "$DEST" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} + 2>/dev/null || true

echo "done. The skill runs as a forked Fable subagent by default."
echo "In Claude Code, invoke with:  /reverse-skill reverse the login API from com.example.aa"
