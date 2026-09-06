# Agent runtime and shared sessions

Claude Code and Codex load the same `SKILL.md`; there is no generated fork or
provider-specific knowledge copy. The installer preserves `/reverse-skill` for
Claude Code and exposes `$reverse-skill` for Codex.

| Need | Runtime rule |
|---|---|
| Skill path | Use the directory of the skill file supplied by the host; resolve symlinks. Do not hardcode a Claude install path. |
| Shell and files | Use the current host's shell/read/write/search capabilities. Tool names in examples describe intent, not a required host API. |
| IDA MCP | Discover callable tools and map by capability; otherwise use the existing headless export path. |
| Device access | Check the actual host and device connection. A cloud session does not imply USB access to the user's phone or access to their Mac. Continue static analysis when unavailable. |
| Second analysis | Use available, permitted delegation with the selected/default model. Otherwise continue locally. |
| Permissions | Honor the current host's sandbox and approvals. Never change models or hosts to get around a rejection. |

## Paths and continuation

Use an absolute `SKILL_ROOT` and an absolute project-local `SESSION_DIR`, such as
`/path/to/project/re_out/app-debug`. These names are command placeholders set by
the agent for the current shell, not automatic host environment variables. Resolve
input artifact paths before any directory change. Prefer calling scripts from
the project, e.g. `python3 "$SKILL_ROOT/scripts/findings.py" --out "$SESSION_DIR" show`.
Pass explicit output paths to every helper that writes files. Do not write target
captures, keys, APKs, or findings into the shared installation or KB.

On a handoff, use that same session directory, read its ledger, verify the target
and goal, and inspect the relevant artifacts. Continue from the recorded phase;
`init` is only for a new ledger and rejects an existing file. A new objective for
the same app may need a separate session. Preserve the existing JSON schema and
rung names for compatibility. Use a single ledger writer at a time; sub-agents
return findings to that writer instead of concurrently editing the JSON file.

The core skill is self-contained. Optional repository tools such as `tools/slider-cv`
are separate from the installed skill folder: locate the original checkout when
needed, and report them unavailable if only a skill snapshot is present. Do not
assume `../../tools` exists relative to a user-level installation.
