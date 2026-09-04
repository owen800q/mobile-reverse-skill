---
name: reverse-skill
description: >-
  Manually run an evidence-based mobile application analysis workflow for an
  explicitly authorized APK, IPA, package, bundle, or test environment. Requires
  a concrete target and objective before loading detailed procedures.
argument-hint: "<owned APK/IPA/package> <specific analysis objective>"
disable-model-invocation: true
---

# reverse-skill — authorized mobile analysis preflight

Invocation request:

```text
$ARGUMENTS
```

Treat this entrypoint as a preflight dispatcher. Do not begin analysis, read the
detailed workflow, create files, or run tools until the request is sufficiently
scoped.

1. Trim the invocation request. If it is empty, ask the user for all three items
   below, then stop:
   - the APK/IPA path, package name, bundle ID, or other concrete app target;
   - the specific feature or behavior they want documented;
   - confirmation that the target is their own app, a CTF, or part of an
     explicitly authorized assessment.
2. If only some of those items are present, ask only for what is missing, then
   stop. Statements such as "my app", "our staging app", "CTF", or "authorized
   pentest" are sufficient authorization context.
3. Do not infer a default target or silently default the objective to login,
   authentication, signing, or any other feature.
4. Once the target, objective, and authorization context are clear, read
   `references/workflow.md` completely and follow it. Treat paths beginning with
   `references/`, `scripts/`, or `assets/` as relative to this skill directory.

For an empty invocation, the response should be only a short request for the
missing preflight information. Do not summarize the detailed workflow.
