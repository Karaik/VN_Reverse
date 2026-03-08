---
name: vn-localization-project
description: Build or reorganize a reproducible visual novel or galgame localization project with reverse engineering, editable script roundtrip, runtime patch packaging, source attribution, and regression validation. Use when starting a new title, migrating a legacy patch chain, defining project structure, documenting formats, or preparing tools and tests for script, archive, and runtime localization.
---

# VN Localization Project

Use this skill when the task is to establish, normalize, or extend a title-specific galgame localization pipeline.

## Start

- Enforce the strongest rule first: never run delete operations or commands that can remove user data.
- Read `references/pipeline.md` before making structural decisions, writing tools, changing packaging behavior, or preparing commits.
- Treat an existing working patch as the behavioral baseline. Migrate the execution chain around it instead of guessing override scope from scratch.

## Required workflow

1. Identify the engine, archive format, script format, text encoding, key requirements, and runtime patch model.
2. Normalize the title project so the final maintained workflow depends only on project-local relative paths.
3. Prioritize script format reversal before secondary resources.
4. Require editable script roundtrip before calling the script pipeline complete.
5. Add runtime packaging when the final deliverable is a playable localization program instead of raw resources only.
6. Write format and usage documentation while implementing, not after.
7. Run regression validation on every critical pipeline stage before claiming completion.
8. Commit only source, docs, translation inputs, and static patch resources. Do not commit built package binaries.

## Non-negotiable rules

- Do not use delete operations.
- Do not hardcode external absolute project paths in the final maintained pipeline.
- Keep final usage commands relative.
- Keep file names short and clear.
- Keep code comments sparse and functional; remove explanatory filler.
- Keep code log and prompt strings in English unless a file is explicitly documentation.
- Keep documentation direct; avoid decorative filler text.

## Script requirements

- Decompile and compile must actually process script text. If the text cannot be edited and compiled back, treat the script pipeline as failed.
- If the script format is instruction-based, provide both:
  - JSON form for structured editing
  - Readable instruction-source form for low-level inspection
- Recompilation must recalculate lengths, offsets, and tables so text length changes do not break runtime reads.

## Encoding requirements

- When the source script text uses Japanese legacy encodings such as `cp932`, `Shift_JIS`, or `win-31j`, provide a documented target-encoding writeback path for `gbk`.
- If `filter_text.txt` exists beside the editable input, treat it as a UTF-8 line-based filter list. Matched text must be written back with source encoding, not target encoding.
- Include regression coverage for filtered writeback behavior.

## Runtime requirements

- If the final playable patch requires runtime binaries, compile new runtime binaries from source.
- If old binaries are reused for compatibility, document exact origin, version, and permanent source links.
- If a title already has a known-good patch layout, use that layout and drive new tooling around it.

## Documentation requirements

- Document binary structures clearly.
- If Mermaid is used, keep it syntactically valid and minimal.
- Replace local-source references in docs with permanent upstream links.
- In the title README, document:
  - committed repo structure
  - build dependencies
  - build order
  - patch inputs
  - incremental update workflow for text and static resources

## Read next

- Read `references/pipeline.md` for the full checklist, structure template, testing rules, packaging rules, and commit boundaries.

## Scaffold helper

Use `scripts/generate_title_layout.py` to create the standard directory layout from `references/pipeline.md`.

```powershell
python .\skills\galgame-localization\vn-localization-project\scripts\generate_title_layout.py ".\titles\<游戏名>"
```
