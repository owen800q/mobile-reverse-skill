# Project instructions

## Trace logging is required

Every function that traces, hooks, captures, records or replays runtime behaviour
must write a log entry for each call. Without these entries the algorithm behind a
result cannot be reconstructed, and a finding that cannot be reconstructed cannot be
checked.

This covers:

- stackplz, ecapture and ios_capture runners and their parsers
- Frida hook scripts in `skills/reverse-skill/assets/frida/` and their host-side handlers
- HAR, pcap and other capture parsers
- any tool that observes a running target: CDP, IPC, module load, file state

Each entry records:

- a UTC timestamp in ISO 8601
- the tool and function name
- input identifiers: session-relative paths, sample or capture IDs, hook targets,
  addresses and offsets
- the parameters that change behaviour: flags, filters, offsets
- the outcome: counts, status and exit code
- the SHA-256 of the upstream artifact, where one exists

Secrets never go into a log. Run the literal redaction pass first, and log only a
length or a digest for a value that must be referenced.

Logs are append-only JSON lines in the session directory, with mode 0600. Writing to
stderr alone does not count as logging.

A trace-related function without a log entry is not finished.
