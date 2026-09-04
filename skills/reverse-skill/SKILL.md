---
name: reverse-skill
description: >-
  Collect a mobile app target and documentation goal, then route to the detailed
  workflow when the required context is present.
argument-hint: "<app target> <documentation goal>"
disable-model-invocation: true
---

# Mobile app workflow

Request:

```text
$ARGUMENTS
```

If the request is empty, respond only with:

> Please provide the app file or package identifier and describe what you want
> documented. Also confirm that you have permission to inspect it.

Then stop. Do not read other files, create files, or use tools.

If the request is present but the app target, documentation goal, or permission
confirmation is missing, ask only for the missing information and stop.

When all three items are present, read `references/workflow.md` completely and
follow it. Treat paths beginning with `references/`, `scripts/`, or `assets/`
as relative to this skill directory.
