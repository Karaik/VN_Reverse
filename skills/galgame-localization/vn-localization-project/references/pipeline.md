# Pipeline

## Scope

Use this workflow for title-specific visual novel localization projects that require reverse engineering, script editing, archive handling, runtime patching, packaging, and long-term maintainability.

## Hard rules

1. Never run delete operations.
2. Never rely on non-project local paths in the final maintained workflow.
3. Keep commands in docs relative to the title root.
4. Do not claim completion without regression results.
5. If text is not editable and compilable, the script stage is not done.

## Title project layout

Use this structure as the target state unless the repo already has a stronger established convention:

```text
title-root/
  README.md
  main_key.py
  main_unpack.py
  main_build.py
  game/
  game_script/
    translated_script/
      scn/
  solution/
    decrypt/
    unpack/
    build/
    patch/
      base/
        chs_patch/
        chs_patch_manifest.txt
    runtime/
```

### Layout rules

- Keep root entry points minimal.
- Put actual implementation under `solution/`.
- Separate `decrypt`, `unpack`, `build`, `patch`, and `runtime`.
- Store per-title keys under the project, not in external shared folders.
- Treat `game/` as local input, not a committed artifact.

## Reverse-engineering order

1. Identify engine.
2. Identify archive/container format.
3. Identify script format.
4. Identify text encoding and control sequences.
5. Identify keys or engine-specific crypto if present.
6. Identify runtime patch strategy only after script and resource loading are understood.

### Priority

- Script structure and editable roundtrip first.
- Archive pack/unpack second.
- Runtime executable or DLL patching third.
- Secondary UI or image resources after the script pipeline is stable.

## Script pipeline requirements

### Required outputs

Produce both of these when the format is instruction-oriented:

1. Editable JSON
2. Readable instruction source

### Required guarantees

- Decompile -> compile must reproduce the source when unchanged.
- Editable text must survive compile without manually patching offsets.
- Recompiler must rebuild sizes, offsets, tables, and related metadata.
- If strings embed control tokens, preserve token handling explicitly.

### Failure conditions

Treat the script pipeline as failed if any of these is true:

- text cannot be extracted in editable form
- edited text cannot compile back
- unchanged source cannot roundtrip byte-identically when that property is expected
- changed text breaks runtime reads due to stale lengths or offsets

## Encoding and filtering

### Encodings

- Detect whether the source is `cp932`, `Shift_JIS`, `win-31j`, UTF-16, or UTF-8.
- If the source is Japanese legacy encoding, provide a documented target-encoding path for `gbk`.
- Do not add `gbk` writeback examples to UTF-16 or UTF-8 pipelines unless specifically needed.

### Filter list

If `filter_text.txt` exists beside the editable inputs:

- treat it as UTF-8
- treat it as line-based exact-match or substring-match logic defined by the title pipeline
- when text matches a filter entry, write it back using source encoding
- when text does not match, use the requested target encoding

Add regression coverage for filtered and unfiltered cases.

## Runtime patch strategy

### Decide the target

Choose one of these based on the title:

1. Resource-only patch
2. New launcher exe plus runtime DLL
3. Proxy DLL only
4. Existing working patch layout migrated into new tooling

### Rules

- If the final deliverable is a playable localized program, build new runtime binaries from source.
- Prefer source-based reproducibility over opaque prebuilt binaries.
- If external binaries remain necessary, document exact upstream origin, version, and permanent links.
- If an existing patch already works, preserve its override scope and structure instead of inventing a new layout.

### KiriKiri-style guidance

- If a known-good patch redirects to a package, keep package redirection unless there is a strong reason to switch.
- Use a manifest to define which files override.
- Do not auto-override every file under a resource tree.

## Documentation rules

### Required docs

For each title, document:

- script or archive structure
- key format if present
- tool roles
- repo structure that is actually committed
- build dependencies
- build order
- incremental update workflow
- final package layout

### Style

- Be direct.
- Remove filler headings and decorative text.
- Replace local source paths in attribution sections with permanent upstream links.
- Use Mermaid only when it adds value and validate syntax.

## Regression checklist

### Minimum required

1. script decompile -> compile
2. archive unpack -> repack
3. runtime package smoke test
4. filtered encoding writeback

### Expected forms

- byte-identical roundtrip when unchanged and the format permits it
- structured equality or runtime readability when exact bytes are not expected
- explicit logs or summary output for failures

### Packaging verification

- unpack rebuilt archive and compare files
- re-decompile rebuilt script outputs
- validate runtime binary exports if using proxy DLLs
- verify save path behavior when custom save redirection is required

## Commit boundaries

Commit:

- source code
- docs
- translation inputs
- raw static patch resources
- manifests
- keys that belong to the title project

Do not commit:

- built packages
- generated `exe`, `dll`, `xp3`, or equivalent release binaries
- local tool caches
- temporary build work directories

## Completion checklist

Before claiming the title pipeline is complete:

- script text is editable
- script text recompiles
- key handling is documented if present
- archive handling is implemented
- runtime packaging is implemented when needed
- README usage is relative
- source attributions are permanent links
- regression results are current
