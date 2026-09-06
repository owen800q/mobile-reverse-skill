#!/usr/bin/env python3
"""Install one skill for Claude Code, Codex, or both (Python standard library)."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import uuid


def location(variable, default):
    value = os.environ.get(variable)
    if value == "":
        raise ValueError(f"{variable} must not be empty")
    path = Path(value if value is not None else default).expanduser().absolute()
    # Resolve the parent, never the final destination symlink being replaced.
    return path.parent.resolve() / path.name


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def install(source, agent, link):
    source = source.resolve(strict=True)
    if not (source / "SKILL.md").is_file():
        raise ValueError(f"{source}/SKILL.md not found")
    home = Path.home()
    destinations = []
    if agent in ("claude", "both"):
        destinations.append(location("CLAUDE_SKILLS_DIR", home / ".claude/skills") / "reverse-skill")
    if agent in ("codex", "both"):
        destinations.append(location("CODEX_SKILLS_DIR", home / ".agents/skills") / "reverse-skill")
    shared = None
    if agent == "both" and not link:
        shared = location("REVERSE_SKILL_SHARED_DIR", home / ".local/share/mobile-reverse-skill/reverse-skill")
    plans = ([(shared, None)] if shared else [])
    plans += [(d, source if link else shared) for d in destinations]
    normalized = []
    for dest, target in plans:
        dest = dest.parent.resolve() / dest.name
        if overlaps(dest, source):
            raise ValueError(f"destination overlaps source: {dest}")
        if any(overlaps(dest, prior) for prior, _ in normalized):
            raise ValueError(f"installation destinations overlap: {dest}")
        normalized.append((dest, target))

    staged, committed, backups = [], [], []
    try:
        # Stage all payloads before replacing any existing installation.
        for dest, target in normalized:
            dest.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=".reverse-skill-stage-", dir=dest.parent))
            staged.append(stage)
            payload = stage / "reverse-skill"
            if target is None:
                shutil.copytree(source, payload, symlinks=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "re_out"))
                for script in (payload / "scripts").glob("*"):
                    if script.is_file() and not script.is_symlink() and script.suffix in (".sh", ".py"):
                        script.chmod(script.stat().st_mode | 0o111)
            else:
                payload.symlink_to(target, target_is_directory=True)
        for (dest, _), stage in zip(normalized, staged):
            if os.path.lexists(dest):
                # Backups live outside the skill scan root to avoid duplicate discovery.
                backup_dir = dest.parent.parent / "reverse-skill-install-backups"
                backup_dir.mkdir(exist_ok=True)
                backup = backup_dir / uuid.uuid4().hex
                dest.rename(backup)
                backups.append((dest, backup))
            (stage / "reverse-skill").rename(dest)
            committed.append(dest)
    except Exception:
        for dest in reversed(committed):
            if dest.is_symlink():
                dest.unlink()
            else:
                shutil.rmtree(dest)
        for dest, backup in reversed(backups):
            backup.rename(dest)
        raise
    finally:
        for stage in staged:
            shutil.rmtree(stage, ignore_errors=True)
    for dest, target in normalized:
        print(f"{'linked' if target else 'copied'}  {dest}" + (f" -> {target}" if target else ""))
    for _, backup in backups:
        print(f"previous installation saved at {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("claude", "codex", "both"), default="claude")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--link", action="store_true", help="link directly to this checkout")
    modes.add_argument("--copy", action="store_true", help="copy a snapshot (default)")
    args = parser.parse_args()
    try:
        install(Path(__file__).resolve().parents[1] / "skills/reverse-skill", args.agent, args.link)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")
    if args.agent in ("claude", "both"):
        print("Claude Code: /reverse-skill <target and objective>")
    if args.agent in ("codex", "both"):
        print("Codex: $reverse-skill <target and objective> (restart if discovery has not refreshed)")


if __name__ == "__main__":
    main()
