English | [中文](README.md)

# reverse-engineering

## Purpose

This category contains capability-oriented reverse-engineering skills.

These skills are meant for focused analysis tasks. They do not define the full layout of a title project, and they do not replace a localization pipeline.

## Source

- Upstream repository: [`P4nda0s/reverse-skills`](https://github.com/P4nda0s/reverse-skills)
- Why it is kept here: it serves as the local `reverse-engineering` skill category for this repository
- Current doc state: this README has been rewritten to match `VN_Reverse` repository usage instead of the upstream plugin-marketplace presentation

## Current skills

- `rev-symbol`
  - Recover likely function names from code patterns, strings, imports, exports, and call context.
- `rev-struct`
  - Reconstruct data structures from memory access patterns across functions and call chains.

## When to use

- You already have decompiled output and need to analyze a specific function or call chain.
- You want to recover better symbol names from constants, strings, and usage context.
- You want to infer structure layouts from offset-based reads and writes.

## Expected input

These skills currently assume an IDA-NO-MCP style export directory, usually including:

- `decompile/`
- `strings.txt`
- `imports.txt`
- `exports.txt`
- `memory/`

## Out of scope

This category does not define:

- title-level project scaffolding
- localization packaging pipelines
- runtime patch layout
- long-term project state tracking

For title-level localization workflow, see:

- `../galgame-localization/README.md`
