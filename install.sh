#!/usr/bin/env bash
# Default remains a Claude Code copy install; see --help for Codex/shared mode.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/tools/install_skill.py" "$@"
