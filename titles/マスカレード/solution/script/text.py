from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from solution.script.disasm import DEFAULT_SWITCH_CHECK_DEPTH, _parse_seed_var16, disasm_file

INT_LITERAL_RE = re.compile(r"^-?\d+$")


def iter_literals(value: Any, path: str = ""):
    if isinstance(value, dict):
        if value.get("type") == "literal":
            yield path, value["text"]
            return
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            yield from iter_literals(item, next_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            next_path = f"{path}[{index}]"
            yield from iter_literals(item, next_path)


def iter_string_refs(value: Any, path: str = ""):
    if isinstance(value, dict):
        if value.get("type") == "string_table_ref":
            yield path, value
            return
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            yield from iter_string_refs(item, next_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            next_path = f"{path}[{index}]"
            yield from iter_string_refs(item, next_path)


def _parse_int_literal(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not INT_LITERAL_RE.fullmatch(text):
        return None
    return int(text, 10)


def _find_meta_int(args: list[Any], key: str) -> int | None:
    for value in reversed(args):
        if not isinstance(value, dict):
            continue
        meta = value.get(key)
        if isinstance(meta, int):
            return meta
    return None


def _is_cp932_lead_byte(value: int) -> bool:
    return (0x81 <= value <= 0x9F) or (0xE0 <= value <= 0xFC)


def _split_cp932_by_delim(source_text: str, delim: int) -> list[str]:
    data = source_text.encode("cp932", errors="replace")
    chunks: list[bytes] = []
    start = 0
    pos = 0
    if 0 <= delim <= 0xFF:
        needle = delim & 0xFF
        while pos < len(data):
            current = data[pos]
            if _is_cp932_lead_byte(current) and pos + 1 < len(data):
                pos += 2
                continue
            if current == needle:
                chunks.append(data[start:pos])
                start = pos + 1
            pos += 1
    else:
        hi = (delim >> 8) & 0xFF
        lo = delim & 0xFF
        while pos < len(data):
            current = data[pos]
            if pos + 1 < len(data) and current == hi and data[pos + 1] == lo:
                chunks.append(data[start:pos])
                start = pos + 2
                pos += 2
                continue
            if _is_cp932_lead_byte(current) and pos + 1 < len(data):
                pos += 2
            else:
                pos += 1
    chunks.append(data[start:])
    return [chunk.decode("cp932", errors="replace") for chunk in chunks]


def _hex_nibble(byte: int) -> int | None:
    if 0x30 <= byte <= 0x39:
        return byte - 0x30
    if 0x41 <= byte <= 0x46:
        return byte - 0x41 + 10
    if 0x61 <= byte <= 0x66:
        return byte - 0x61 + 10
    return None


def _parse_decimal_ascii(data: bytes, start: int) -> tuple[int, int]:
    value = 0
    pos = start
    while pos < len(data):
        current = data[pos]
        if current < 0x30 or current > 0x39:
            break
        value = value * 10 + (current - 0x30)
        pos += 1
    return value, pos


def _resolve_sub4019f0_table_value(
    kind_byte: int,
    index: int,
    *,
    str18_state: dict[int, str],
    str19_state: dict[int, str],
) -> str | None:
    kind = kind_byte | 0x20
    if kind == ord("g"):
        return str18_state.get(index)
    if kind == ord("s"):
        return str19_state.get(index)
    return None


def _resolve_sub401840_table_value(
    kind_byte: int,
    index: int,
    *,
    num16_state: dict[int, int],
    num32_state: dict[int, int],
    num48_state: dict[int, int],
) -> int | None:
    kind = kind_byte | 0x20
    if kind == ord("s"):
        return num16_state.get(index)
    if kind == ord("w"):
        return num32_state.get(index)
    if kind == ord("g"):
        return num48_state.get(index)
    return None


def _parse_escape_table_ref(data: bytes, pos: int, prefix: int) -> tuple[int, int, int] | None:
    if pos + 4 >= len(data):
        return None
    if not (
        data[pos] == 0x5B
        and data[pos + 1] == 0x5F
        and (data[pos + 2] | 0x20) == (prefix | 0x20)
    ):
        return None
    table_kind = data[pos + 3]
    pos += 4
    index, pos = _parse_decimal_ascii(data, pos)
    if pos >= len(data) or data[pos] != 0x5D:
        return None
    return table_kind, index, pos + 1


def _transform_string_sub402280(
    source_text: str,
    *,
    str18_state: dict[int, str],
    str19_state: dict[int, str],
    num16_state: dict[int, int],
    num32_state: dict[int, int],
    num48_state: dict[int, int],
) -> str | None:
    data = source_text.encode("cp932", errors="replace")
    out = bytearray()
    pos = 0
    while pos < len(data):
        current = data[pos]
        if _is_cp932_lead_byte(current):
            if pos + 1 >= len(data):
                return None
            out.append(current)
            out.append(data[pos + 1])
            pos += 2
            continue
        pos += 1
        if current != 0x5C:
            out.append(current)
            continue
        if pos >= len(data):
            break
        escape = data[pos]
        pos += 1
        if escape == 0:
            break
        if escape == 0x5C:
            out.append(0x5C)
            continue
        if escape == 0x27:
            if pos + 1 >= len(data):
                return None
            hi = _hex_nibble(data[pos])
            lo = _hex_nibble(data[pos + 1])
            if hi is None or lo is None:
                return None
            out.append((hi << 4) | lo)
            pos += 2
            continue
        lowered = escape | 0x20
        if lowered == ord("n"):
            out.append(0x0D)
            continue
        if lowered == ord("c"):
            parsed_ref = _parse_escape_table_ref(data, pos, ord("i"))
            if parsed_ref is None:
                return None
            table_kind, index, pos = parsed_ref
            resolved = _resolve_sub401840_table_value(
                table_kind,
                index,
                num16_state=num16_state,
                num32_state=num32_state,
                num48_state=num48_state,
            )
            if resolved is None or resolved < 0:
                return None
            if resolved >= 0x100:
                out.append((resolved >> 8) & 0xFF)
            out.append(resolved & 0xFF)
            continue
        if lowered in {ord("i"), ord("z")}:
            full_width = lowered == ord("z")
            zero_pad = False
            width = 0
            if pos < len(data) and data[pos] == 0x30:
                zero_pad = True
                pos += 1
            if pos < len(data) and 0x31 <= data[pos] <= 0x39:
                width, pos = _parse_decimal_ascii(data, pos)
            parsed_ref = _parse_escape_table_ref(data, pos, ord("i"))
            if parsed_ref is None:
                return None
            table_kind, index, pos = parsed_ref
            resolved = _resolve_sub401840_table_value(
                table_kind,
                index,
                num16_state=num16_state,
                num32_state=num32_state,
                num48_state=num48_state,
            )
            if resolved is None:
                return None
            negative = resolved < 0
            abs_value = -resolved if negative else resolved
            if negative and width > 0:
                width -= 1
            digits = str(abs_value).encode("ascii")
            rendered = bytearray()
            pad_count = max(width - len(digits), 0)
            if pad_count > 0:
                rendered.extend((b"0" if zero_pad else b" ") * pad_count)
            if negative:
                rendered.append(0x2D)
            rendered.extend(digits)
            if full_width:
                for ch in rendered:
                    if ch == 0x20:
                        out.extend(b"\x81\x40")
                    elif ch == 0x2D:
                        out.extend(b"\x81\x7C")
                    elif 0x30 <= ch <= 0x39:
                        out.extend(bytes((0x82, ch + 0x1F)))
                    else:
                        return None
            else:
                out.extend(rendered)
            continue
        if lowered == ord("s"):
            width = 0
            if pos < len(data) and 0x31 <= data[pos] <= 0x39:
                width, pos = _parse_decimal_ascii(data, pos)
            parsed_ref = _parse_escape_table_ref(data, pos, ord("s"))
            if parsed_ref is None:
                return None
            table_kind, index, pos = parsed_ref
            resolved = _resolve_sub4019f0_table_value(
                table_kind,
                index,
                str18_state=str18_state,
                str19_state=str19_state,
            )
            if resolved is None:
                return None
            resolved_bytes = resolved.encode("cp932", errors="replace")
            if width > len(resolved_bytes):
                out.extend(b" " * (width - len(resolved_bytes)))
            out.extend(resolved_bytes)
            continue
        return None
    return out.decode("cp932", errors="replace")


def _resolve_table_name(ref: dict[str, Any]) -> str | None:
    table = ref.get("table")
    if isinstance(table, str):
        return table
    kind = ref.get("kind")
    if kind == 1:
        return "str19"
    if kind == 3:
        return "str18"
    return None


def _resolve_string_ref(
    ref: dict[str, Any],
    *,
    str18_state: dict[int, str],
    str19_state: dict[int, str],
) -> tuple[str | None, str | None, int | None]:
    table = _resolve_table_name(ref)
    index = ref.get("index")
    if not isinstance(index, int):
        index = ref.get("index_const")
    if not isinstance(index, int):
        return None, table, None
    if table == "str18":
        return str18_state.get(index), table, index
    if table == "str19":
        return str19_state.get(index), table, index
    return None, table, index


def _resolve_string_value(
    value: Any,
    *,
    str18_state: dict[int, str],
    str19_state: dict[int, str],
) -> str | None:
    if isinstance(value, dict):
        if value.get("type") == "literal":
            text = value.get("text")
            return text if isinstance(text, str) else None
        if value.get("type") == "string_table_ref":
            text, _table, _index = _resolve_string_ref(
                value,
                str18_state=str18_state,
                str19_state=str19_state,
            )
            if text is not None:
                return text
            if value.get("runtime_fallback") == "empty_literal":
                return ""
    return None


def _apply_arg_bundle_named_state(
    bundle: dict[str, Any],
    *,
    str18_state: dict[int, str],
    str19_state: dict[int, str],
) -> None:
    named = bundle.get("named")
    if not isinstance(named, list):
        return
    for index, value in enumerate(named):
        resolved = _resolve_string_value(
            value,
            str18_state=str18_state,
            str19_state=str19_state,
        )
        if resolved is None:
            str19_state.pop(index, None)
        else:
            str19_state[index] = resolved


def _extract_expr_writes_meta(args: list[Any]) -> list[dict[str, Any]]:
    for value in reversed(args):
        if not isinstance(value, dict):
            continue
        writes = value.get("expr_writes")
        if isinstance(writes, list):
            return [row for row in writes if isinstance(row, dict)]
    return []


def _apply_numeric_expression_writes(
    writes: list[dict[str, Any]],
    *,
    num16_state: dict[int, int],
    num32_state: dict[int, int],
    num48_state: dict[int, int],
) -> None:
    buckets = {
        16: num16_state,
        32: num32_state,
        48: num48_state,
    }
    for row in writes:
        var_type = row.get("var_type")
        if not isinstance(var_type, int):
            continue
        bucket = buckets.get(var_type)
        if bucket is None:
            continue
        index = row.get("index_const")
        if not isinstance(index, int) or index < 0:
            continue
        value = row.get("value_const")
        if isinstance(value, int):
            bucket[index] = value
        elif index in bucket:
            bucket.pop(index)


def dump_text_items(
    input_path: Path,
    limit: int = 512,
    entry: int | None = None,
    strict_expr: bool = False,
    conservative_cfg: bool = False,
    filter_switch_targets: bool = False,
    filter_branch_targets: bool = False,
    filter_call_targets: bool = False,
    sanitize_branch_targets: bool = True,
    no_call_fallthrough: bool = False,
    switch_check_depth: int = DEFAULT_SWITCH_CHECK_DEPTH,
    switch_plus2_fallback: bool = False,
    auto_filter_sparse_switch: bool = False,
    propagate_var16_const: bool = False,
    seed_var16: dict[int, int] | None = None,
    infer_entry_var16_seed: bool = False,
) -> dict[str, Any]:
    use_filter_switch_targets = conservative_cfg or filter_switch_targets
    use_follow_call_fallthrough = not (conservative_cfg or no_call_fallthrough)
    use_switch_plus2_fallback = switch_plus2_fallback and (use_filter_switch_targets or auto_filter_sparse_switch)
    disasm = disasm_file(
        input_path,
        limit=limit,
        entry=entry,
        strict_expr=strict_expr,
        follow_call_fallthrough=use_follow_call_fallthrough,
        filter_switch_targets=use_filter_switch_targets,
        filter_branch_targets=filter_branch_targets,
        filter_call_targets=filter_call_targets,
        sanitize_branch_targets=sanitize_branch_targets,
        switch_check_depth=switch_check_depth,
        switch_plus2_fallback=use_switch_plus2_fallback,
        auto_filter_sparse_switch=auto_filter_sparse_switch,
        propagate_var16_const=propagate_var16_const,
        seed_var16=seed_var16,
        infer_entry_var16_seed=infer_entry_var16_seed,
    )
    items: list[dict[str, Any]] = []
    resolved_items: list[dict[str, Any]] = []
    str18_state: dict[int, str] = {}
    str19_state: dict[int, str] = {}
    num16_state: dict[int, int] = {}
    num32_state: dict[int, int] = {}
    num48_state: dict[int, int] = {}
    for instruction in disasm.decoded:
        for arg_path, text in iter_literals(instruction.args, "args"):
            items.append(
                {
                    "offset": instruction.offset,
                    "line": instruction.line,
                    "opcode": instruction.opcode,
                    "name": instruction.name,
                    "arg_path": arg_path,
                    "text": text,
                }
            )
        for arg_path, ref in iter_string_refs(instruction.args, "args"):
            resolved_text, resolved_table, resolved_index = _resolve_string_ref(
                ref,
                str18_state=str18_state,
                str19_state=str19_state,
            )
            if resolved_text is None:
                continue
            resolved_items.append(
                {
                    "offset": instruction.offset,
                    "line": instruction.line,
                    "opcode": instruction.opcode,
                    "name": instruction.name,
                    "arg_path": arg_path,
                    "text": resolved_text,
                    "resolved_from_table": resolved_table,
                    "resolved_from_index": resolved_index,
                }
            )

        for arg in instruction.args:
            if isinstance(arg, dict) and "named" in arg and "numeric" in arg:
                _apply_arg_bundle_named_state(
                    arg,
                    str18_state=str18_state,
                    str19_state=str19_state,
                )
        _apply_numeric_expression_writes(
            _extract_expr_writes_meta(instruction.args),
            num16_state=num16_state,
            num32_state=num32_state,
            num48_state=num48_state,
        )

        if instruction.name == "set_str18" and len(instruction.args) >= 2:
            index = _parse_int_literal(instruction.args[0])
            if index is None:
                index = _find_meta_int(instruction.args, "str18_index_const")
            if index is not None:
                value = _resolve_string_value(
                    instruction.args[1],
                    str18_state=str18_state,
                    str19_state=str19_state,
                )
                if value is None:
                    str18_state.pop(index, None)
                else:
                    str18_state[index] = value
        elif instruction.name == "append_str18" and len(instruction.args) >= 2:
            index = _parse_int_literal(instruction.args[0])
            if index is None:
                index = _find_meta_int(instruction.args, "str18_index_const")
            if index is not None:
                suffix = _resolve_string_value(
                    instruction.args[1],
                    str18_state=str18_state,
                    str19_state=str19_state,
                )
                prefix = str18_state.get(index)
                if suffix is None or prefix is None:
                    str18_state.pop(index, None)
                else:
                    str18_state[index] = prefix + suffix
        elif instruction.name == "transform_set_str18":
            index = _parse_int_literal(instruction.args[0]) if instruction.args else None
            if index is None:
                index = _find_meta_int(instruction.args, "str18_index_const")
            if index is not None:
                source_value = None
                if len(instruction.args) >= 2:
                    source_value = _resolve_string_value(
                        instruction.args[1],
                        str18_state=str18_state,
                        str19_state=str19_state,
                    )
                if source_value is None:
                    str18_state.pop(index, None)
                else:
                    transformed = _transform_string_sub402280(
                        source_value,
                        str18_state=str18_state,
                        str19_state=str19_state,
                        num16_state=num16_state,
                        num32_state=num32_state,
                        num48_state=num48_state,
                    )
                    if transformed is None:
                        str18_state.pop(index, None)
                    else:
                        str18_state[index] = transformed
        elif instruction.name == "store_filtered_string_to_str19_0":
            value: str | None = None
            if len(instruction.args) >= 2:
                value = _resolve_string_value(
                    instruction.args[1],
                    str18_state=str18_state,
                    str19_state=str19_state,
                )
            if value is None:
                str19_state.pop(0, None)
            else:
                str19_state[0] = value
        elif instruction.name == "split_string_to_str19" and len(instruction.args) >= 2:
            source = _resolve_string_value(
                instruction.args[0],
                str18_state=str18_state,
                str19_state=str19_state,
            )
            delim = _parse_int_literal(instruction.args[1])
            if delim is None:
                delim = _find_meta_int(instruction.args, "split_delim_const")
            if source is None or delim is None:
                str19_state.clear()
            else:
                parts = _split_cp932_by_delim(source, delim)
                str19_state.clear()
                for index, part in enumerate(parts):
                    str19_state[index] = part
        elif instruction.name == "obj4_read_scalar_or_cstr_to_str19_0":
            read_mode = None
            if len(instruction.args) >= 3:
                read_mode = _parse_int_literal(instruction.args[2])
            if read_mode is None:
                read_mode = _find_meta_int(instruction.args, "read_mode_const")
            if read_mode is None or read_mode == 0:
                str19_state.pop(0, None)
        elif instruction.name in {
            "collect_system_info_to_str19_var16",
            "system_command_to_var16_0",
            "profile_get_to_str19_0",
            "drive_probe_to_var16_0",
            "snapshot_current_message_to_str19_0",
        }:
            str19_state.pop(0, None)
        elif instruction.name in {
            "lookup_table_row_to_str19",
            "clipboard_snapshot_to_str19",
        }:
            str19_state.clear()
    return {
        "input": str(input_path),
        "entry": disasm.entry,
        "with_line": disasm.with_line,
        "strict_expr": strict_expr,
        "conservative_cfg": conservative_cfg,
        "filter_switch_targets": use_filter_switch_targets,
        "auto_filter_sparse_switch": auto_filter_sparse_switch,
        "filter_branch_targets": filter_branch_targets,
        "filter_call_targets": filter_call_targets,
        "sanitize_branch_targets": sanitize_branch_targets,
        "no_call_fallthrough": not use_follow_call_fallthrough,
        "switch_check_depth": switch_check_depth,
        "switch_plus2_fallback": use_switch_plus2_fallback,
        "propagate_var16_const": propagate_var16_const,
        "seed_var16": {str(key): value for key, value in sorted((seed_var16 or {}).items())},
        "infer_entry_var16_seed": infer_entry_var16_seed,
        "decoded_count": len(disasm.decoded),
        "error_count": len(disasm.errors),
        "text_count": len(items),
        "resolved_ref_count": len(resolved_items),
        "total_text_count": len(items) + len(resolved_items),
        "items": items,
        "resolved_items": resolved_items,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Masquerade Himauri text dumper")
    parser.add_argument("input", type=Path)
    parser.add_argument("out_file", type=Path)
    parser.add_argument("--entry", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--limit", type=int, default=512)
    parser.add_argument("--strict-expr", action="store_true", help="Enable expression stack underflow checks during decode")
    parser.add_argument(
        "--conservative-cfg",
        action="store_true",
        help="Shortcut for --no-call-fallthrough + --filter-switch-targets",
    )
    parser.add_argument(
        "--filter-switch-targets",
        action="store_true",
        help="Filter switch targets by plausibility checks",
    )
    parser.add_argument(
        "--auto-filter-sparse-switch",
        action="store_true",
        help="Automatically prune very sparse switch tables in default CFG (experimental)",
    )
    parser.add_argument(
        "--filter-branch-targets",
        action="store_true",
        help="Filter if/ifelse/ifnot/goto targets by plausibility checks",
    )
    parser.add_argument(
        "--filter-call-targets",
        action="store_true",
        help="Filter opcode 0x06 call targets by plausibility checks",
    )
    parser.add_argument(
        "--no-branch-target-sanitize",
        action="store_true",
        help="Disable default branch target normalization (decodeability + target+2 fallback)",
    )
    parser.add_argument(
        "--no-call-fallthrough",
        action="store_true",
        help="Do not add fallthrough edges for call-like opcodes (0x06/0x09/0x0A)",
    )
    parser.add_argument(
        "--switch-check-depth",
        type=int,
        default=DEFAULT_SWITCH_CHECK_DEPTH,
        help="Instruction depth used for conservative switch target plausibility checks",
    )
    parser.add_argument(
        "--switch-plus2-fallback",
        action="store_true",
        help="Try target+2 for suspicious switch entries (experimental, conservative mode only)",
    )
    parser.add_argument(
        "--propagate-var16-const",
        action="store_true",
        help="Propagate var16 constants through opcode 0x06 call arg-bundles to narrow switch(var16[x]) targets",
    )
    parser.add_argument(
        "--seed-var16",
        action="append",
        default=[],
        metavar="INDEX=VALUE",
        help="Seed var16 constants before entry decode (can be repeated)",
    )
    parser.add_argument(
        "--infer-entry-var16-seed",
        action="store_true",
        help="Infer entry seed var16[255]=1 for arg-dispatch prologues (experimental)",
    )
    return parser


def build_mainline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Masquerade Himauri text dumper")
    parser.add_argument("input", type=Path)
    parser.add_argument("out_file", type=Path)
    parser.add_argument("--entry", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--limit", type=int, default=512)
    parser.add_argument("--strict-expr", action="store_true", help="Enable expression stack underflow checks during decode")
    parser.add_argument(
        "--conservative-cfg",
        action="store_true",
        help="Shortcut for --no-call-fallthrough + --filter-switch-targets",
    )
    return parser


def mainline_main(argv: list[str] | None = None) -> int:
    parser = build_mainline_parser()
    args = parser.parse_args(argv)
    payload = dump_text_items(
        args.input,
        limit=args.limit,
        entry=args.entry,
        strict_expr=args.strict_expr,
        conservative_cfg=args.conservative_cfg,
        filter_switch_targets=False,
        filter_branch_targets=False,
        filter_call_targets=False,
        sanitize_branch_targets=True,
        no_call_fallthrough=False,
        switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        switch_plus2_fallback=False,
        auto_filter_sparse_switch=False,
        propagate_var16_const=False,
        seed_var16=None,
        infer_entry_var16_seed=False,
    )
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] texts: {payload['text_count']}")
    print(f"[ok] output: {args.out_file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    seed_var16 = _parse_seed_var16(args.seed_var16)
    payload = dump_text_items(
        args.input,
        limit=args.limit,
        entry=args.entry,
        strict_expr=args.strict_expr,
        conservative_cfg=args.conservative_cfg,
        filter_switch_targets=args.filter_switch_targets,
        filter_branch_targets=args.filter_branch_targets,
        filter_call_targets=args.filter_call_targets,
        sanitize_branch_targets=not args.no_branch_target_sanitize,
        no_call_fallthrough=args.no_call_fallthrough,
        switch_check_depth=args.switch_check_depth,
        switch_plus2_fallback=args.switch_plus2_fallback,
        auto_filter_sparse_switch=args.auto_filter_sparse_switch,
        propagate_var16_const=args.propagate_var16_const,
        seed_var16=seed_var16,
        infer_entry_var16_seed=args.infer_entry_var16_seed,
    )
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] texts: {payload['text_count']}")
    print(f"[ok] output: {args.out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
