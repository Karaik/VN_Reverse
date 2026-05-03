---
name: reverse-title-readme
description: Normalize the main README for a reverse title so it becomes the user-facing entry point, with complete executable commands, explicit encoding write-back commands, and validation coverage.
---

# Reverse Title README

Use this skill when the task is to create, rewrite, or validate the main `README.md` of a reverse title.

## Hard rules

- The main README is the human entry point, not an AGENT file.
- Do not write analysis process, exploration process, or temporary process into the main README.
- Keep only the current real workflow that is actually supported by the implementation.
- Every retained command must be complete and executable from the title root.
- Every retained command must be followed by:
  - goal
  - input
  - output
  - why the output matters

## Required structure

The main README should usually follow this order:

1. What this title can do now
2. What the default entry produces
3. Shortest path for text work
4. Default workflow commands
5. Current verified facts
6. Current unconfirmed / unfinished boundaries
7. Docs links

## Encoding rules

For script-oriented reverse titles:

- The README must explicitly state the source text encoding path.
- If the project supports target-encoding write-back, the README must include:
  - source-encoding decompile command
  - source-encoding compile command
  - target-encoding compile command
  - target-encoding re-decompile verification command
- If the implementation does not support target-encoding write-back yet, the README must state that clearly and must not pretend the feature exists.

## Text write-back examples

If the title supports them, keep explicit command chains for:

- patching a specified text entry
- patching a variable-length text entry

Do not write “edit this file manually” without also providing a complete executable command example for that edit step.

## Validation section

The README must only claim what the formal validation actually covers.

If total regression covers:

- unchanged roundtrip
- text write-back
- target-encoding write-back

then the README should say exactly that.

If something is not covered, keep it in the unfinished boundary section.
