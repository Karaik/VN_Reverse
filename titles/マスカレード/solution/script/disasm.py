from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path
from typing import Any, Callable

from solution.script.argpack import parse_arg_bundle
from solution.script.expression import decode_expression, decode_expression_with_const, decode_expression_with_const_and_writes
from solution.script.himauri import parse_stream_entry
from solution.script.model import DisasmResult, Instruction
from solution.script.opcodes import OpcodeSpec, load_opcode_specs
from solution.script.reader import Reader
from solution.script.strings import decode_string_expr


# These opcodes transfer control to another script/context but can later
# resume at the current stream position, so the fallthrough address is a
# valid CFG successor.
CALL_LIKE_OPCODES = {0x06, 0x09, 0x0A}
DEFAULT_SWITCH_CHECK_DEPTH = 4
SPARSE_SWITCH_MIN_CASE_COUNT = 24
SPARSE_SWITCH_MAX_PLAUSIBLE_CASES = 8
VAR16_DIRECT_RE = re.compile(r"^var16\[(\d+)\]$")
INT_LITERAL_RE = re.compile(r"^-?\d+$")
_VAR16_WRITER_META_CACHE: dict[int, dict[str, Any]] | None = None
RESOURCE_SLOT_WRITER_OPCODES = {
    0x25,
    0x29,
    0x31,
    0x32,
    0x36,
    0x41,
    0x4B,
    0x4F,
    0x53,
    0x58,
    0x5E,
    0x60,
    0x70,
}
RESOURCE_SLOT_TYPE1_WRITER_OPCODE = 0x5E
RESOURCE_SLOT_TYPE_BY_OPCODE = {
    0x29: 7,
    0x31: 5,
    0x32: 6,
    0x36: 8,
    0x4B: 9,
    0x4F: 4,
    0x58: 3,
    0x60: 10,
    0x70: 2,
}
GENERIC_HANDLER_NAME_OPCODES = {
    0x22,
    0x23,
    0x24,
    0x25,
    0x26,
    0x29,
    0x2B,
    0x2C,
    0x2D,
    0x2F,
    0x3A,
    0x3B,
    0x3C,
    0x3D,
    0x3E,
    0x3F,
    0x44,
    0x45,
    0x4D,
    0x4E,
    0x52,
    0x53,
    0x55,
    0x56,
    0x57,
    0x58,
    0x59,
    0x5A,
    0x70,
}


def _get_var16_writer_meta() -> dict[int, dict[str, Any]]:
    global _VAR16_WRITER_META_CACHE
    if _VAR16_WRITER_META_CACHE is None:
        from solution.script.var16_writers import audit_var16_writers

        cache: dict[int, dict[str, Any]] = {}
        for item in audit_var16_writers()["writers"]:
            opcode = int(item["opcode"])
            const_indices = {
                int(value)
                for value in item.get("write_var16_const_indices", [])
                if isinstance(value, int) and value >= 0
            }
            dynamic_indices = [
                str(value) for value in item.get("write_var16_dynamic_indices", []) if isinstance(value, str)
            ]
            cache[opcode] = {
                "const_indices": const_indices,
                "has_dynamic": bool(dynamic_indices),
            }
        _VAR16_WRITER_META_CACHE = cache
    return _VAR16_WRITER_META_CACHE


def _extract_direct_var16_index(expr: str) -> int | None:
    match = VAR16_DIRECT_RE.fullmatch(expr.strip())
    if not match:
        return None
    return int(match.group(1))


def _derive_call_target_var16_state(item: Instruction, state: dict[int, int]) -> dict[int, int]:
    if item.opcode != 0x06 or not item.args:
        return dict(state)
    payload = item.args[0]
    if not isinstance(payload, dict):
        return dict(state)
    consts = payload.get("numeric_consts")
    if not isinstance(consts, list):
        return dict(state)
    next_state = dict(state)
    for index, value in enumerate(consts):
        if isinstance(value, int):
            next_state[index] = value
        elif index in next_state:
            next_state.pop(index)
    next_state[255] = len(consts)
    named = payload.get("named")
    if isinstance(named, list):
        next_state[254] = len(named)
    return next_state


def _apply_var16_expression_writes(state: dict[int, int], writes: list[dict[str, Any]]) -> None:
    for row in writes:
        if not isinstance(row, dict):
            continue
        if row.get("var_type") != 16:
            continue
        index = row.get("index_const")
        if not isinstance(index, int) or index < 0:
            continue
        value = row.get("value_const")
        if isinstance(value, int):
            state[index] = value
        elif index in state:
            state.pop(index)


def _invalidate_var16_written_slots(
    state: dict[int, int],
    opcode: int,
    writer_meta: dict[int, dict[str, Any]],
) -> None:
    info = writer_meta.get(opcode)
    if not info:
        return
    if info.get("has_dynamic"):
        # Dynamic index writes (for example loops over var16 slots) are treated
        # conservatively: clear all known constants to avoid stale propagation.
        state.clear()
        return
    for index in info.get("const_indices", set()):
        if isinstance(index, int) and index in state:
            state.pop(index)


def _extract_expr_writes_meta(item: Instruction) -> list[dict[str, Any]]:
    if not item.args:
        return []
    tail = item.args[-1]
    if isinstance(tail, dict):
        writes = tail.get("expr_writes")
        if isinstance(writes, list):
            return [row for row in writes if isinstance(row, dict)]
    return []


def _extract_const_meta(item: Instruction, key: str) -> int | None:
    for arg in reversed(item.args):
        if not isinstance(arg, dict):
            continue
        value = arg.get(key)
        if isinstance(value, int):
            return value
    return None


def _append_instruction_meta(item: Instruction, **entries: int | str) -> None:
    if not entries:
        return
    if item.args and isinstance(item.args[-1], dict):
        item.args[-1].update(entries)
    else:
        item.args.append(dict(entries))


def _extract_int_literal(text: str) -> int | None:
    expr = text.strip()
    if not INT_LITERAL_RE.fullmatch(expr):
        return None
    try:
        return int(expr, 10)
    except Exception:
        return None


def _extract_resource_id_const(item: Instruction) -> int | None:
    resource_id = _extract_const_meta(item, "resource_id_const")
    if resource_id is not None:
        return resource_id
    if item.args and isinstance(item.args[0], str):
        return _extract_int_literal(item.args[0])
    return None


def _extract_resource_script_target_const(item: Instruction) -> int | None:
    value = _extract_const_meta(item, "resource_script_target_const")
    if value is not None:
        return value
    if len(item.args) >= 2 and isinstance(item.args[1], str):
        try:
            return int(item.args[1], 0)
        except Exception:
            return None
    return None


def _apply_resource_slot_writes(
    target_state: dict[int, int],
    type_state: dict[int, int],
    item: Instruction,
) -> None:
    if item.opcode not in RESOURCE_SLOT_WRITER_OPCODES:
        return
    resource_id = _extract_resource_id_const(item)
    if resource_id is None:
        # Unknown slot index write: conservatively invalidate all tracked slots.
        target_state.clear()
        type_state.clear()
        return
    if item.opcode == RESOURCE_SLOT_TYPE1_WRITER_OPCODE:
        target = _extract_resource_script_target_const(item)
        if target is not None:
            target_state[resource_id] = target
        else:
            target_state.pop(resource_id, None)
        type_state[resource_id] = 1
        return
    target_state.pop(resource_id, None)
    slot_type = RESOURCE_SLOT_TYPE_BY_OPCODE.get(item.opcode)
    if slot_type is None:
        type_state.pop(resource_id, None)
        return
    type_state[resource_id] = slot_type


def _call_like_has_fallthrough(item: Instruction) -> bool:
    if item.opcode == 0x09:
        # sub_405940 -> sub_401440(v3, v2 & 1):
        # bit0==1 keeps parent context and can return to current stream.
        # bit0==0 clears old context chain and current stream will not resume.
        resume_flag = _extract_const_meta(item, "resume_fallthrough_const")
        if resume_flag is not None:
            return bool(resume_flag)
        return True
    return item.opcode in CALL_LIKE_OPCODES


def _is_decodable_offset(data: bytes, offset: int, with_line: bool, specs: dict[int, OpcodeSpec]) -> bool:
    if not (0 <= offset < len(data)):
        return False
    try:
        decode_instruction(data, offset, with_line, specs, strict_expr=False)
    except Exception:
        return False
    return True


def _normalize_expr_for_match(expr: str) -> str:
    return "".join(expr.split())


def _infer_entry_var16_seed(
    data: bytes,
    *,
    entry: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
) -> dict[int, int]:
    """
    Infer entry var16 seeds for the common "arg-dispatch script" prologue:
    ifnot(var16[255] > 0) goto <legacy/no-arg path>
    switch(var16[0]) ...

    Runtime sets var16[255] in sub_404880 before these scripts are entered.
    For standalone file smoke/review this context is unavailable, so we can
    optionally seed var16[255]=1 when the no-arg branch is structurally dubious.
    """
    inferred: dict[int, int] = {}
    try:
        first, first_targets, _ = decode_instruction(data, entry, with_line, specs, strict_expr=False)
    except Exception:
        return inferred
    if first.opcode != 0x03:
        return inferred
    if not first.args or not isinstance(first.args[0], str):
        return inferred
    if _normalize_expr_for_match(first.args[0]) != "(var16[255]>0)":
        return inferred
    try:
        second, _second_targets, _ = decode_instruction(data, first.next_offset, with_line, specs, strict_expr=False)
    except Exception:
        return inferred
    if second.opcode != 0x05:
        return inferred
    if not second.args or not isinstance(second.args[0], str):
        return inferred
    if _normalize_expr_for_match(second.args[0]) != "var16[0]":
        return inferred
    if not first_targets:
        return inferred
    jump_target = first_targets[0]
    if _is_decodable_offset(data, jump_target, with_line, specs):
        return inferred
    if not _is_decodable_offset(data, jump_target + 2, with_line, specs):
        return inferred
    inferred[255] = 1
    return inferred


def _should_force_entry_arg_dispatch_fallthrough(
    *,
    data: bytes,
    entry: int,
    item: Instruction,
    targets: list[int],
    with_line: bool,
    specs: dict[int, OpcodeSpec],
) -> bool:
    """
    Recognize the common arg-dispatch entry guard and drop its no-arg edge:
      ifnot(var16[255] > 0) goto <legacy/no-arg path>
      switch(var16[0]) ...

    Even without explicit seed propagation this branch is usually a legacy
    path in standalone analysis. We keep the heuristic strict and only apply
    when the jump target is non-decodable while `target+2` is decodable.
    """
    if item.offset != entry or item.opcode != 0x03:
        return False
    if len(targets) < 2:
        return False
    if not item.args or not isinstance(item.args[0], str):
        return False
    if _normalize_expr_for_match(item.args[0]) != "(var16[255]>0)":
        return False
    try:
        second, _second_targets, _ = decode_instruction(
            data,
            item.next_offset,
            with_line,
            specs,
            strict_expr=False,
        )
    except Exception:
        return False
    if second.opcode != 0x05:
        return False
    if not second.args or not isinstance(second.args[0], str):
        return False
    if _normalize_expr_for_match(second.args[0]) != "var16[0]":
        return False
    jump_target = targets[0]
    if _is_decodable_offset(data, jump_target, with_line, specs):
        return False
    if not _is_decodable_offset(data, jump_target + 2, with_line, specs):
        return False
    return True


def _narrow_control_targets(item: Instruction, targets: list[int], var16_state: dict[int, int] | None = None) -> list[int]:
    if not targets:
        return targets
    if item.opcode == 0x01:
        cond_const = _extract_const_meta(item, "cond_const")
        if cond_const is not None and len(targets) >= 2:
            return [targets[0] if cond_const != 0 else targets[1]]
    elif item.opcode == 0x02:
        cond_const = _extract_const_meta(item, "cond_const")
        if cond_const is not None and len(targets) >= 2:
            return [targets[0] if cond_const != 0 else targets[1]]
    elif item.opcode == 0x03:
        cond_const = _extract_const_meta(item, "cond_const")
        if cond_const is not None and len(targets) >= 2:
            return [targets[0] if cond_const == 0 else targets[1]]
    elif item.opcode == 0x05:
        index_const = _extract_const_meta(item, "index_const")
        if index_const is None and var16_state and item.args:
            expr = item.args[0]
            if isinstance(expr, str):
                index = _extract_direct_var16_index(expr)
                if index is not None:
                    index_const = var16_state.get(index)
        if index_const is not None and len(targets) >= 1:
            case_count = len(targets) - 1
            if 0 <= index_const < case_count:
                return [targets[index_const]]
            return [targets[-1]]
    return targets


def _is_plausible_branch_entry(
    data: bytes,
    start: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    check_depth: int,
) -> bool:
    return is_plausible_entry(
        data,
        start,
        with_line,
        specs,
        strict_expr=False,
        max_chain=check_depth,
    )


def _is_plausible_control_target(
    data: bytes,
    target: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    check_depth: int,
) -> bool:
    if not (0 <= target < len(data)):
        return False
    return is_plausible_entry(
        data,
        target,
        with_line,
        specs,
        strict_expr=True,
        max_chain=check_depth,
    )


def _is_plausible_switch_case_entry(
    data: bytes,
    start: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    check_depth: int,
) -> bool:
    if not _is_plausible_control_target(data, start, with_line, specs, check_depth):
        return False
    pos = start
    seen: set[int] = set()
    try:
        for _ in range(check_depth):
            if pos in seen or pos >= len(data):
                return False
            seen.add(pos)
            item, targets, terminator = decode_instruction(
                data,
                pos,
                with_line,
                specs,
                strict_expr=False,
            )

            if item.opcode == 0x04:
                if not targets:
                    return False
                if not _is_plausible_control_target(
                    data, targets[0], with_line, specs, check_depth
                ):
                    return False

            elif item.opcode == 0x02:
                if len(targets) < 2:
                    return False
                cond_const = _extract_const_meta(item, "cond_const")
                true_ok = _is_plausible_control_target(
                    data, targets[0], with_line, specs, check_depth
                )
                false_ok = _is_plausible_control_target(
                    data, targets[1], with_line, specs, check_depth
                )
                if cond_const is None and not (true_ok and false_ok):
                    return False
                if cond_const is not None:
                    selected_ok = true_ok if cond_const != 0 else false_ok
                    if not selected_ok:
                        return False

            elif item.opcode in {0x01, 0x03}:
                if len(targets) < 2:
                    return False
                cond_const = _extract_const_meta(item, "cond_const")
                jump_ok = _is_plausible_control_target(
                    data, targets[0], with_line, specs, check_depth
                )
                fallthrough_ok = _is_plausible_control_target(
                    data, targets[1], with_line, specs, check_depth
                )
                if cond_const is None and not (jump_ok and fallthrough_ok):
                    return False
                if cond_const is not None:
                    if item.opcode == 0x01:
                        selected_ok = jump_ok if cond_const != 0 else fallthrough_ok
                    else:
                        selected_ok = jump_ok if cond_const == 0 else fallthrough_ok
                    if not selected_ok:
                        return False

            if item.opcode == 0xFF or terminator:
                return True

            next_pos = item.next_offset + (2 if with_line else 0)
            if next_pos >= len(data):
                return False
            next_opcode = data[next_pos]
            if next_opcode > 0x71 and next_opcode != 0xFF:
                return False
            pos = item.next_offset

        if pos >= len(data):
            return False
        decode_instruction(data, pos, with_line, specs, strict_expr=False)
    except Exception:
        return False
    return True


def _normalize_branch_targets(
    item: Instruction,
    targets: list[int],
    data: bytes,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    check_depth: int,
) -> list[int]:
    if item.opcode not in {0x01, 0x02, 0x03, 0x04} or not targets:
        return targets
    normalized: list[int] = []
    seen: set[int] = set()
    for target in targets:
        if not (0 <= target < len(data)):
            continue
        candidate = target
        if not _is_plausible_branch_entry(data, target, with_line, specs, check_depth):
            plus2 = target + 2
            if plus2 >= len(data):
                continue
            if not is_plausible_entry(
                data,
                plus2,
                with_line,
                specs,
                strict_expr=False,
                max_chain=check_depth,
            ):
                continue
            candidate = plus2
        if candidate in seen:
            continue
        normalized.append(candidate)
        seen.add(candidate)
    cond_const = _extract_const_meta(item, "cond_const") if item.opcode in {0x01, 0x03} else None
    if (
        item.opcode in {0x01, 0x03}
        and cond_const is None
        and item.next_offset in targets
        and 0 <= item.next_offset < len(data)
        and item.next_offset not in seen
    ):
        normalized.append(item.next_offset)
    return normalized


def _collect_switch_target_candidates(
    raw_targets: list[int],
    *,
    entry: int,
    data: bytes,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    check_depth: int,
    switch_plus2_fallback: bool,
) -> tuple[list[int], int, int | None]:
    if not raw_targets:
        return [], 0, None
    case_targets = raw_targets[:-1]
    case_count = len(case_targets)
    filtered_cases: list[int] = []
    seen: set[int] = set()
    for target in case_targets:
        if target < entry or target >= len(data):
            continue
        if _is_plausible_switch_case_entry(
            data,
            target,
            with_line,
            specs,
            check_depth=check_depth,
        ):
            if target not in seen:
                filtered_cases.append(target)
                seen.add(target)
            continue
        if not switch_plus2_fallback:
            continue
        plus2 = target + 2
        if plus2 >= len(data):
            continue
        if not is_plausible_entry(
            data,
            target,
            True,
            specs,
            strict_expr=False,
            max_chain=check_depth,
        ):
            continue
        if _is_plausible_switch_case_entry(
            data,
            plus2,
            with_line,
            specs,
            check_depth=check_depth,
        ) and plus2 not in seen:
            filtered_cases.append(plus2)
            seen.add(plus2)
    default_target = raw_targets[-1]
    default_candidate: int | None = None
    if (
        entry <= default_target < len(data)
        and _is_plausible_switch_case_entry(
            data,
            default_target,
            with_line,
            specs,
            check_depth=check_depth,
        )
    ):
        default_candidate = default_target
    return filtered_cases, case_count, default_candidate


def generic_decode(
    reader: Reader,
    opcode: int,
    spec: OpcodeSpec,
    strict_expr: bool = False,
    expr_decoder: Callable[[], str] | None = None,
) -> tuple[str, list[Any], list[int], bool]:
    args: list[Any] = []
    targets: list[int] = []
    for call in spec.call_order:
        if call == "401C60":
            if expr_decoder is None:
                args.append(decode_expression(reader, strict=strict_expr, require_single=False))
            else:
                args.append(expr_decoder())
        elif call == "4021F0":
            args.append(decode_string_expr(reader, strict_expr=strict_expr))
        elif call == "401810":
            value = reader.u24be()
            args.append(f"0x{value:06X}")
            targets.append(value)
        elif call == "4017E0":
            args.append(reader.u16be())
        elif call == "4017C0":
            args.append(reader.u8())
        elif call == "404880":
            args.append(parse_arg_bundle(reader, strict_expr=strict_expr))
    return f"op_{opcode:02X}", args, targets, False


def decode_instruction(
    data: bytes,
    pos: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    strict_expr: bool = False,
    var16_state: dict[int, int] | None = None,
) -> tuple[Instruction, list[int], bool]:
    reader = Reader(data, pos)
    line = reader.u16be() if with_line else None
    opcode = reader.u8()
    args: list[Any] = []
    targets: list[int] = []
    terminator = False
    name = f"op_{opcode:02X}"
    expr_state = dict(var16_state or {})
    expr_writes: list[dict[str, Any]] = []

    def _decode_expr() -> str:
        if var16_state is None:
            return decode_expression(reader, strict=strict_expr, require_single=False)
        text, _const, writes = decode_expression_with_const_and_writes(
            reader,
            strict=strict_expr,
            require_single=False,
            var16_state=expr_state,
        )
        _apply_var16_expression_writes(expr_state, writes)
        expr_writes.extend(writes)
        return text

    def _decode_expr_with_const() -> tuple[str, int | None]:
        if var16_state is None:
            return decode_expression_with_const(reader, strict=strict_expr, require_single=False)
        text, const_value, writes = decode_expression_with_const_and_writes(
            reader,
            strict=strict_expr,
            require_single=False,
            var16_state=expr_state,
        )
        _apply_var16_expression_writes(expr_state, writes)
        expr_writes.extend(writes)
        return text, const_value

    if opcode == 0xFF:
        name = "end"
        terminator = True
    elif opcode == 0x00:
        name = "eval"
        args = [_decode_expr()]
        if expr_writes:
            args.append({"expr_writes": expr_writes})
    elif opcode == 0x01:
        expr, cond_const = _decode_expr_with_const()
        target = reader.u24be()
        name = "if_goto"
        args = [expr, f"0x{target:06X}"]
        meta: dict[str, Any] = {}
        if cond_const is not None:
            meta["cond_const"] = cond_const
        if expr_writes:
            meta["expr_writes"] = expr_writes
        if meta:
            args.append(meta)
        targets = [target, reader.pos]
    elif opcode == 0x02:
        expr, cond_const = _decode_expr_with_const()
        target_true = reader.u24be()
        target_false = reader.u24be()
        name = "ifelse_goto"
        args = [expr, f"0x{target_true:06X}", f"0x{target_false:06X}"]
        meta = {}
        if cond_const is not None:
            meta["cond_const"] = cond_const
        if expr_writes:
            meta["expr_writes"] = expr_writes
        if meta:
            args.append(meta)
        targets = [target_true, target_false]
        terminator = True
    elif opcode == 0x03:
        expr, cond_const = _decode_expr_with_const()
        target = reader.u24be()
        name = "ifnot_goto"
        args = [expr, f"0x{target:06X}"]
        meta = {}
        if cond_const is not None:
            meta["cond_const"] = cond_const
        if expr_writes:
            meta["expr_writes"] = expr_writes
        if meta:
            args.append(meta)
        targets = [target, reader.pos]
    elif opcode == 0x04:
        target = reader.u24be()
        name = "goto"
        args = [f"0x{target:06X}"]
        targets = [target]
        terminator = True
    elif opcode == 0x05:
        expr, index_const = _decode_expr_with_const()
        count = reader.u16be()
        table = [reader.u24be() for _ in range(count)]
        name = "switch_goto"
        args = [expr, count, [f"0x{x:06X}" for x in table]]
        meta = {}
        if index_const is not None:
            meta["index_const"] = index_const
        if expr_writes:
            meta["expr_writes"] = expr_writes
        if meta:
            args.append(meta)
        targets = table + [reader.pos]
        terminator = True
    elif opcode == 0x06:
        name = "call"
        args = [parse_arg_bundle(reader, strict_expr=strict_expr, include_const=True)]
        target = reader.u24be()
        args.append(f"0x{target:06X}")
        targets = [target]
        terminator = True
    elif opcode == 0x07:
        name = "return"
        args = [_decode_expr()]
        terminator = True
    elif opcode == 0x08:
        name = "return_exit"
        args = [_decode_expr()]
        terminator = True
    elif opcode == 0x09:
        mode_expr, mode_const = _decode_expr_with_const()
        name = "load_script_by_name"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            mode_expr,
            parse_arg_bundle(reader, strict_expr=strict_expr),
        ]
        if mode_const is not None:
            args.append(
                {
                    "mode_const": mode_const,
                    "resume_fallthrough_const": mode_const & 1,
                }
            )
        terminator = True
    elif opcode == 0x0A:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "load_resource_with_args"
        args = [
            resource_expr,
            parse_arg_bundle(reader, strict_expr=strict_expr),
        ]
        args.append({"resume_fallthrough_const": 1, **({"resource_id_const": resource_const} if resource_const is not None else {})})
        terminator = True
    elif opcode == 0x0B:
        name = "set_str18"
        index_expr, index_const = _decode_expr_with_const()
        args = [
            index_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
        if index_const is not None:
            args.append({"str18_index_const": index_const})
    elif opcode == 0x0C:
        name = "append_str18"
        index_expr, index_const = _decode_expr_with_const()
        args = [
            index_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
        if index_const is not None:
            args.append({"str18_index_const": index_const})
    elif opcode == 0x0D:
        name = "strcmp_to_var0"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x0E:
        name = "strlen_to_var01"
        args = [decode_string_expr(reader, strict_expr=strict_expr)]
    elif opcode == 0x0F:
        name = "find_char_to_var0"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x10:
        name = "transform_set_str18"
        index_expr, index_const = _decode_expr_with_const()
        args = [
            index_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
        if index_const is not None:
            args.append({"str18_index_const": index_const})
    elif opcode == 0x11:
        name = "find_char_index_to_var16_0"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x12:
        name = "system_command_to_var16_0"
        args = [
            _decode_expr(),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x13:
        name = "drive_probe_to_var16_0"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
        ]
    elif opcode == 0x14:
        name = "set_window_visibility_mode"
        args = [_decode_expr()]
    elif opcode == 0x15:
        name = "collect_system_info_to_str19_var16"
    elif opcode == 0x16:
        name = "timegettime_delta_to_var16"
        args = [_decode_expr()]
    elif opcode == 0x17:
        name = "snapshot_input_state_to_var16_0_7"
    elif opcode in {0x1A, 0x1B, 0x1C, 0x27, 0x28, 0x2A, 0x46, 0x47, 0x67, 0x6C}:
        name = f"nop_{opcode:02X}"
    elif opcode == 0x18:
        name = "set_global_flags_4474F0_4474F4"
    elif opcode == 0x19:
        name = "set_flag_437040"
        args = [_decode_expr()]
    elif opcode == 0x1D:
        name = "set_obj3_flag"
        args = [_decode_expr() for _ in range(3)]
    elif opcode == 0x1E:
        name = "play_effect_slot_clamped"
        args = [_decode_expr()]
    elif opcode == 0x1F:
        name = "call_412440_to_var16_0"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x20:
        name = "reset_render_context_focus_window"
    elif opcode == 0x21:
        name = "query_40ED40_to_var16_0"
    elif opcode == 0x22:
        mode_expr, mode_const = _decode_expr_with_const()
        value_expr = _decode_expr()
        name = "call_40F110_mode_clamped_dup_value"
        args = [mode_expr, value_expr]
        if mode_const is not None:
            mode_clamped_const = 0 if mode_const < 0 else (3 if mode_const > 3 else mode_const)
            args.append(
                {
                    "mode_const": mode_const,
                    "mode_clamped_const": mode_clamped_const,
                }
            )
    elif opcode == 0x23:
        name = "query_audio_level_avg_to_var16_0"
        args = [_decode_expr()]
    elif opcode == 0x24:
        name = "obj3_lookup_call_40EAA0"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x25:
        obj_expr, resource_const = _decode_expr_with_const()
        key_expr = decode_string_expr(reader, strict_expr=strict_expr)
        value_expr = _decode_expr()
        store_flag_expr, store_flag_const = _decode_expr_with_const()
        name = "call_404410_with_optional_store_var16_0"
        args = [
            obj_expr,
            key_expr,
            value_expr,
            store_flag_expr,
        ]
        meta: dict[str, Any] = {}
        if store_flag_const is not None:
            meta["store_result_flag_const"] = store_flag_const
        if resource_const is not None:
            meta["resource_id_const"] = resource_const
        if meta:
            args.append(meta)
    elif opcode == 0x26:
        name = "obj_lookup_call_4042C0"
        args = [_decode_expr()]
    elif opcode == 0x29:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "call_404590_expr5"
        args = [
            resource_expr,
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x2B:
        obj_expr = _decode_expr()
        enabled_expr, enabled_const = _decode_expr_with_const()
        name = "obj7_set_flag_and_snapshot_to_var16_0"
        args = [obj_expr, enabled_expr]
        if enabled_const is not None:
            args.append({"enabled_const": enabled_const})
    elif opcode == 0x2C:
        name = "obj7_call_402DA0"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x2D:
        name = "obj7_call_402DD0"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x2F:
        name = "copy_obj7_to_obj2_like_402B50"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x2E:
        name = "obj7_call_402E50"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x30:
        name = "nop_30"
    elif opcode == 0x31:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "call_404600"
        args = [
            resource_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x32:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "call_404650"
        args = [
            resource_expr,
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x33:
        name = "call_403020"
        args = [_decode_expr() for _ in range(8)]
    elif opcode == 0x34:
        name = "obj7_field32_call_4029D0"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x35:
        name = "obj7_call_403AD0"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x39:
        name = "obj7_set_actions_batch"
        count = reader.u8()
        obj7_expr = _decode_expr()
        flags_expr = _decode_expr()
        rows: list[dict[str, Any]] = []
        for _ in range(count):
            rows.append(
                {
                    "name": decode_string_expr(reader, strict_expr=strict_expr),
                    "arg": _decode_expr(),
                    "enabled": _decode_expr(),
                }
            )
        args = [count, obj7_expr, flags_expr, rows]
    elif opcode == 0x3A:
        name = "call_40F530"
    elif opcode == 0x3B:
        name = "call_40F920_to_var16_0_bool"
        args = [decode_string_expr(reader, strict_expr=strict_expr)]
    elif opcode == 0x3C:
        name = "parse_datetime_to_var16_0_6"
        args = [decode_string_expr(reader, strict_expr=strict_expr)]
    elif opcode == 0x3D:
        start_expr = _decode_expr()
        count_expr, count_const = _decode_expr_with_const()
        name = "call_40F5B0_var48_batch"
        args = [start_expr, count_expr]
        if count_const is not None:
            args.append({"count_const": count_const})
    elif opcode == 0x36:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "obj_attach_glyph_like"
        args = [
            resource_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x37:
        name = "call_403BA0"
        args = [_decode_expr()]
    elif opcode == 0x38:
        name = "set_obj7_fields"
        args = [_decode_expr() for _ in range(9)]
    elif opcode == 0x3E:
        name = "enqueue_command_string"
        args = [decode_string_expr(reader, strict_expr=strict_expr)]
    elif opcode == 0x3F:
        start_expr = _decode_expr()
        count_expr, count_const = _decode_expr_with_const()
        name = "read_int_to_var16_or_var48_batch"
        args = [start_expr, count_expr]
        if count_const is not None:
            args.append({"count_const": count_const})
    elif opcode == 0x40:
        name = "store_filtered_string_to_str19_0"
        marker = reader.u8()
        args = [marker]
        if marker == 2:
            end = reader.data.index(0, reader.pos)
            raw = reader.data[reader.pos : end]
            reader.pos = end + 1
            args.append({"type": "literal", "text": raw.decode("cp932", errors="replace")})
    elif opcode == 0x41:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "obj6_blit_like"
        args = [
            resource_expr,
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x42:
        name = "obj5_draw_text_like"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x43:
        name = "obj_blit_pair_like"
        # sub_406020: 12x sub_401C60 arguments
        # (src_obj, src_rect, dst_obj, dst_rect, extra2)
        src_obj_expr = _decode_expr()
        src_x_expr = _decode_expr()
        src_y_expr = _decode_expr()
        src_w_expr = _decode_expr()
        src_h_expr = _decode_expr()
        dst_obj_expr = _decode_expr()
        dst_x_expr = _decode_expr()
        dst_y_expr = _decode_expr()
        dst_w_expr = _decode_expr()
        dst_h_expr = _decode_expr()
        extra_a_expr = _decode_expr()
        extra_b_expr = _decode_expr()
        args = [
            {
                "src_obj_expr": src_obj_expr,
                "src_x_expr": src_x_expr,
                "src_y_expr": src_y_expr,
                "src_w_expr": src_w_expr,
                "src_h_expr": src_h_expr,
                "dst_obj_expr": dst_obj_expr,
                "dst_x_expr": dst_x_expr,
                "dst_y_expr": dst_y_expr,
                "dst_w_expr": dst_w_expr,
                "dst_h_expr": dst_h_expr,
                "extra_a_expr": extra_a_expr,
                "extra_b_expr": extra_b_expr,
            }
        ]
    elif opcode == 0x44:
        name = "set_flag_40F2F0"
        args = [_decode_expr()]
    elif opcode == 0x45:
        name = "query_40F410_to_var16_0"
    elif opcode == 0x48:
        name = "profile_set_file_app"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x49:
        name = "profile_get_to_str19_0"
        args = [decode_string_expr(reader, strict_expr=strict_expr)]
    elif opcode == 0x4A:
        name = "profile_write_value"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x4B:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "call_4046E0"
        args = [
            resource_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x4C:
        name = "sleep_ms"
        args = [_decode_expr()]
    elif opcode == 0x4D:
        name = "inspect_obj_type_to_var16_0_7"
        args = [_decode_expr()]
    elif opcode == 0x4E:
        name = "set_cursor_pos_client"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x4F:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "obj4_alloc_bytes"
        args = [
            resource_expr,
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x54:
        name = "obj7_set_field28"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x55:
        name = "snapshot_input_event_to_var16_0_1"
    elif opcode == 0x56:
        name = "snapshot_keyboard_state_to_var16_0_255"
    elif opcode == 0x57:
        name = "obj5_find_name_to_var16_0"
        args = [
            _decode_expr(),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x58:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "obj_entry_set_byte_or_error"
        args = [
            resource_expr,
            decode_string_expr(reader, strict_expr=strict_expr),
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x59:
        name = "save_obj2_bitmap_to_file_to_var16_0"
        args = [
            _decode_expr(),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x5A:
        name = "obj4_read_scalar_or_cstr_to_str19_0"
        obj_expr = _decode_expr()
        offset_expr = _decode_expr()
        read_mode_expr, read_mode_const = _decode_expr_with_const()
        args = [
            obj_expr,
            offset_expr,
            read_mode_expr,
        ]
        if read_mode_const is not None:
            args.append({"read_mode_const": read_mode_const})
    elif opcode == 0x50:
        name = "obj4_write_byte"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x51:
        name = "obj4_read_byte_to_var16_0"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x52:
        name = "obj_call_40F670_or_40F6F0"
        args = [_decode_expr()]
    elif opcode == 0x53:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "obj_blob_transfer_like"
        args = [resource_expr]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x5B:
        name = "shell_execute_to_var16_0"
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            decode_string_expr(reader, strict_expr=strict_expr),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x5C:
        name = "resource_pair_op"
        args = [_decode_expr() for _ in range(6)]
    elif opcode == 0x5D:
        name = "clipboard_snapshot_to_str19"
    elif opcode == 0x5F:
        name = "joystick_button_to_var16_0"
        args = [_decode_expr()]
    elif opcode == 0x60:
        resource_expr, resource_const = _decode_expr_with_const()
        name = "obj3_write_bytes"
        args = [
            resource_expr,
            _decode_expr(),
        ]
        if resource_const is not None:
            args.append({"resource_id_const": resource_const})
    elif opcode == 0x5E:
        name = "obj_set_resource_ref_by_id"
        resource_expr, resource_const = _decode_expr_with_const()
        target = reader.u24be()
        args = [
            resource_expr,
            f"0x{target:06X}",
            {
                "resource_script_target_const": target,
                **({"resource_id_const": resource_const} if resource_const is not None else {}),
            },
        ]
    elif opcode == 0x63:
        name = "nop_63"
    elif opcode == 0x61:
        name = "lookup_table_row_to_str19"
        args = [_decode_expr()]
        mode = reader.u8()
        args.append(mode)
        if mode:
            args.append(decode_string_expr(reader, strict_expr=strict_expr))
        else:
            args.append(_decode_expr())
    elif opcode == 0x62:
        name = "call_401990_48"
        args = [_decode_expr() for _ in range(3)]
    elif opcode == 0x64:
        name = "split_string_to_str19"
        delim_expr, delim_const = _decode_expr_with_const()
        args = [
            decode_string_expr(reader, strict_expr=strict_expr),
            delim_expr,
        ]
        if delim_const is not None:
            args.append({"split_delim_const": delim_const})
    elif opcode == 0x65:
        name = "ime_set_composition_window_pos"
        args = [
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x66:
        name = "datetime_to_var16_0_6"
    elif opcode == 0x68:
        name = "nop_68"
    elif opcode == 0x69:
        name = "copy_str_to_obj4_offset"
        args = [
            _decode_expr(),
            _decode_expr(),
            decode_string_expr(reader, strict_expr=strict_expr),
        ]
    elif opcode == 0x6A:
        name = "obj4_memcpy"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x6B:
        name = "snapshot_current_message_to_str19_0"
    elif opcode == 0x6D:
        name = "clipboard_set"
        args = [decode_string_expr(reader, strict_expr=strict_expr)]
    elif opcode == 0x6E:
        name = "set_obj2_handle_global_457BD4"
        args = [_decode_expr()]
    elif opcode == 0x6F:
        name = "resource_ref_call_40D350"
        args = [
            _decode_expr(),
            _decode_expr(),
            _decode_expr(),
        ]
    elif opcode == 0x70:
        obj_expr, resource_const = _decode_expr_with_const()
        width_expr, width_const = _decode_expr_with_const()
        height_expr, height_const = _decode_expr_with_const()
        name = "obj2_resample_copy_like"
        args = [obj_expr, width_expr, height_expr]
        meta: dict[str, Any] = {}
        if width_const is not None:
            meta["width_const"] = width_const
        if height_const is not None:
            meta["height_const"] = height_const
        if resource_const is not None:
            meta["resource_id_const"] = resource_const
        if meta:
            args.append(meta)
    elif opcode == 0x71:
        name = "nop_71"
    else:
        spec = specs[opcode]
        if spec.manual:
            raise NotImplementedError(f"opcode 0x{opcode:02X} requires manual decoder ({spec.handler:06X})")
        name, args, targets, terminator = generic_decode(
            reader,
            opcode,
            spec,
            strict_expr=strict_expr,
            expr_decoder=_decode_expr,
        )
        if opcode in GENERIC_HANDLER_NAME_OPCODES:
            name = f"call_{spec.handler:06X}"

    if expr_writes:
        if args and isinstance(args[-1], dict):
            tail = args[-1]
            if "expr_writes" in tail:
                pass
            elif "cond_const" in tail or "index_const" in tail:
                tail["expr_writes"] = expr_writes
            else:
                args.append({"expr_writes": expr_writes})
        else:
            args.append({"expr_writes": expr_writes})

    item = Instruction(
        offset=pos,
        line=line,
        opcode=opcode,
        name=name,
        args=args,
        size=reader.pos - pos,
        next_offset=reader.pos,
        raw=data[pos:reader.pos].hex(" "),
    )
    return item, targets, terminator


def is_plausible_entry(
    data: bytes,
    start: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    strict_expr: bool = False,
    max_chain: int = DEFAULT_SWITCH_CHECK_DEPTH,
) -> bool:
    pos = start
    seen: set[int] = set()
    try:
        for _ in range(max_chain):
            if pos in seen or pos >= len(data):
                return False
            seen.add(pos)
            item, _targets, terminator = decode_instruction(data, pos, with_line, specs, strict_expr=strict_expr)
            if item.opcode == 0xFF or terminator:
                return True
            next_pos = item.next_offset + (2 if with_line else 0)
            if next_pos >= len(data):
                return False
            next_opcode = data[next_pos]
            if next_opcode > 0x71 and next_opcode != 0xFF:
                return False
            pos = item.next_offset
        # One-step lookahead: reject entries that only fail immediately
        # after the short plausibility window.
        if pos >= len(data):
            return False
        decode_instruction(data, pos, with_line, specs, strict_expr=strict_expr)
    except Exception:
        return False
    return True


def disasm_cfg(
    data: bytes,
    entry: int,
    with_line: bool,
    specs: dict[int, OpcodeSpec],
    limit: int,
    strict_expr: bool = False,
    follow_call_fallthrough: bool = True,
    filter_switch_targets: bool = False,
    filter_branch_targets: bool = False,
    filter_call_targets: bool = False,
    sanitize_branch_targets: bool = True,
    switch_check_depth: int = DEFAULT_SWITCH_CHECK_DEPTH,
    switch_plus2_fallback: bool = False,
    auto_filter_sparse_switch: bool = False,
    propagate_var16_const: bool = False,
    seed_var16: dict[int, int] | None = None,
    infer_entry_var16_seed: bool = False,
) -> DisasmResult:
    visited_offsets: set[int] = set()
    initial_seed = dict(seed_var16 or {})
    if infer_entry_var16_seed and 255 not in initial_seed:
        inferred_seed = _infer_entry_var16_seed(
            data,
            entry=entry,
            with_line=with_line,
            specs=specs,
        )
        initial_seed.update(inferred_seed)
    var16_state_by_offset: dict[int, dict[int, int]] = {entry: dict(initial_seed)}
    resource_slot_target_state_by_offset: dict[int, dict[int, int]] = {entry: {}}
    resource_slot_type_state_by_offset: dict[int, dict[int, int]] = {entry: {}}
    case_boundary_guard = filter_switch_targets
    known_switch_case_entries: set[int] = set()
    decoded: dict[int, Instruction] = {}
    queue = deque([entry])
    errors: list[dict[str, Any]] = []
    use_var16_state = propagate_var16_const or bool(initial_seed)
    use_resource_slot_state = propagate_var16_const
    writer_meta = _get_var16_writer_meta() if use_var16_state else {}
    while queue and len(decoded) < limit:
        start = queue.popleft()
        if start in visited_offsets or start >= len(data):
            continue
        current_state = dict(var16_state_by_offset.get(start, {}))
        current_resource_slot_target_state = dict(resource_slot_target_state_by_offset.get(start, {}))
        current_resource_slot_type_state = dict(resource_slot_type_state_by_offset.get(start, {}))
        pos = start
        while pos < len(data) and pos not in visited_offsets and len(decoded) < limit:
            # Guard against decoding through adjacent switch-case entry blocks.
            # This keeps one case path from consuming another case's byte range.
            if case_boundary_guard and pos != start and pos in known_switch_case_entries:
                break
            visited_offsets.add(pos)
            try:
                item, targets, terminator = decode_instruction(
                    data,
                    pos,
                    with_line,
                    specs,
                    strict_expr=strict_expr,
                    var16_state=current_state if use_var16_state else None,
                )
            except Exception as exc:
                errors.append({"offset": pos, "error": str(exc)})
                break
            crossed_case_boundary = False
            if case_boundary_guard:
                for boundary in known_switch_case_entries:
                    if pos < boundary < item.next_offset:
                        crossed_case_boundary = True
                        break
            if case_boundary_guard and crossed_case_boundary:
                break
            decoded[pos] = item
            raw_targets = list(targets)
            if case_boundary_guard and item.opcode == 0x05 and raw_targets:
                for case_target in raw_targets[:-1]:
                    if entry <= case_target < len(data):
                        known_switch_case_entries.add(case_target)
            if use_resource_slot_state and item.opcode == 0x0A:
                resource_id_const = _extract_resource_id_const(item)
                if resource_id_const is not None:
                    slot_type = current_resource_slot_type_state.get(resource_id_const)
                    if isinstance(slot_type, int):
                        _append_instruction_meta(item, resource_slot_type_const=slot_type)
                    resource_target = current_resource_slot_target_state.get(resource_id_const)
                    if slot_type is None or slot_type == 1:
                        if (
                            isinstance(resource_target, int)
                            and 0 <= resource_target < len(data)
                            and resource_target not in targets
                        ):
                            targets = [resource_target, *targets]
                            _append_instruction_meta(
                                item,
                                resource_slot_source="opcode_5E_state",
                                resource_script_target_const=resource_target,
                            )
                    elif slot_type == 9:
                        _append_instruction_meta(item, resource_slot_source="opcode_4B_state")
            targets = _narrow_control_targets(item, targets, var16_state=current_state if use_var16_state else None)
            if _should_force_entry_arg_dispatch_fallthrough(
                data=data,
                entry=entry,
                item=item,
                targets=targets,
                with_line=with_line,
                specs=specs,
            ):
                # Keep only fallthrough edge for the arg-dispatch prologue.
                targets = [item.next_offset]
            branch_cond_const = _extract_const_meta(item, "cond_const") if item.opcode in {0x01, 0x03} else None
            if sanitize_branch_targets:
                targets = _normalize_branch_targets(
                    item,
                    targets,
                    data,
                    with_line,
                    specs,
                    check_depth=switch_check_depth,
                )
            if filter_call_targets and item.opcode == 0x06 and targets:
                call_filtered: list[int] = []
                for target in targets:
                    if not (0 <= target < len(data)):
                        continue
                    if is_plausible_entry(
                        data,
                        target,
                        with_line,
                        specs,
                        strict_expr=True,
                        max_chain=switch_check_depth,
                    ):
                        call_filtered.append(target)
                targets = call_filtered
            if follow_call_fallthrough and _call_like_has_fallthrough(item):
                targets = [*targets, item.next_offset]
            if filter_branch_targets and item.opcode in {0x01, 0x02, 0x03, 0x04} and targets:
                branch_filtered: list[int] = []
                for target in targets:
                    if not (0 <= target < len(data)):
                        continue
                    if item.opcode in {0x01, 0x03} and target == item.next_offset:
                        branch_filtered.append(target)
                        continue
                    if is_plausible_entry(
                        data,
                        target,
                        with_line,
                        specs,
                        strict_expr=True,
                        max_chain=switch_check_depth,
                    ):
                        branch_filtered.append(target)
                if (
                    item.opcode in {0x01, 0x03}
                    and branch_cond_const is None
                    and 0 <= item.next_offset < len(data)
                    and item.next_offset not in branch_filtered
                ):
                    branch_filtered.append(item.next_offset)
                targets = branch_filtered
            if item.opcode == 0x05 and targets:
                filtered_cases, case_count, default_candidate = _collect_switch_target_candidates(
                    targets,
                    entry=entry,
                    data=data,
                    with_line=with_line,
                    specs=specs,
                    check_depth=switch_check_depth,
                    switch_plus2_fallback=switch_plus2_fallback,
                )
                if filter_switch_targets:
                    targets = [*filtered_cases]
                    if default_candidate is not None:
                        targets.append(default_candidate)
                elif (
                    auto_filter_sparse_switch
                    and case_count >= SPARSE_SWITCH_MIN_CASE_COUNT
                    and len(filtered_cases) <= SPARSE_SWITCH_MAX_PLAUSIBLE_CASES
                ):
                    # Auto-prune extremely sparse switch tables (common in this title)
                    # to avoid exploding into unreachable case bodies in default CFG.
                    targets = [*filtered_cases]
                    if default_candidate is not None:
                        targets.append(default_candidate)
                elif (
                    strict_expr
                    and case_count >= SPARSE_SWITCH_MIN_CASE_COUNT
                    and len(filtered_cases) <= SPARSE_SWITCH_MAX_PLAUSIBLE_CASES
                ):
                    # In strict expression mode, prefer conservative switch edges to
                    # avoid cascading false stack-underflow errors from sparse junk cases.
                    targets = [*filtered_cases]
                    if default_candidate is not None:
                        targets.append(default_candidate)

            next_state = dict(current_state)
            if use_var16_state:
                _apply_var16_expression_writes(next_state, _extract_expr_writes_meta(item))
                _invalidate_var16_written_slots(next_state, item.opcode, writer_meta)
            next_resource_slot_target_state = dict(current_resource_slot_target_state)
            next_resource_slot_type_state = dict(current_resource_slot_type_state)
            if use_resource_slot_state:
                _apply_resource_slot_writes(next_resource_slot_target_state, next_resource_slot_type_state, item)

            call_target_state = next_state
            call_target_value = None
            if propagate_var16_const and item.opcode == 0x06:
                call_target_state = _derive_call_target_var16_state(item, next_state)
                if len(item.args) >= 2 and isinstance(item.args[1], str):
                    try:
                        call_target_value = int(item.args[1], 0)
                    except Exception:
                        call_target_value = None

            for target in targets:
                if 0 <= target < len(data) and target not in visited_offsets:
                    target_state = next_state
                    if call_target_value is not None and target == call_target_value:
                        target_state = call_target_state
                    if target not in var16_state_by_offset:
                        var16_state_by_offset[target] = dict(target_state)
                    if use_resource_slot_state and target not in resource_slot_target_state_by_offset:
                        resource_slot_target_state_by_offset[target] = dict(next_resource_slot_target_state)
                        resource_slot_type_state_by_offset[target] = dict(next_resource_slot_type_state)
                    queue.append(target)
            forced_terminate = (
                item.opcode in {0x01, 0x03}
                and branch_cond_const is not None
                and item.next_offset not in targets
            )
            if terminator or item.opcode == 0xFF or forced_terminate:
                break
            current_state = next_state
            current_resource_slot_target_state = next_resource_slot_target_state
            current_resource_slot_type_state = next_resource_slot_type_state
            pos = item.next_offset
    return DisasmResult(
        entry=entry,
        with_line=with_line,
        decoded=[decoded[offset] for offset in sorted(decoded)],
        errors=errors,
    )


def disasm_file(
    path: Path,
    limit: int = 512,
    entry: int | None = None,
    strict_expr: bool = False,
    follow_call_fallthrough: bool = True,
    filter_switch_targets: bool = False,
    filter_branch_targets: bool = False,
    filter_call_targets: bool = False,
    sanitize_branch_targets: bool = True,
    switch_check_depth: int = DEFAULT_SWITCH_CHECK_DEPTH,
    switch_plus2_fallback: bool = False,
    auto_filter_sparse_switch: bool = False,
    propagate_var16_const: bool = False,
    seed_var16: dict[int, int] | None = None,
    infer_entry_var16_seed: bool = False,
) -> DisasmResult:
    data = path.read_bytes()
    default_entry, with_line = parse_stream_entry(data)
    specs = load_opcode_specs()
    return disasm_cfg(
        data,
        default_entry if entry is None else entry,
        with_line,
        specs,
        limit,
        strict_expr=strict_expr,
        follow_call_fallthrough=follow_call_fallthrough,
        filter_switch_targets=filter_switch_targets,
        filter_branch_targets=filter_branch_targets,
        filter_call_targets=filter_call_targets,
        sanitize_branch_targets=sanitize_branch_targets,
        switch_check_depth=switch_check_depth,
        switch_plus2_fallback=switch_plus2_fallback,
        auto_filter_sparse_switch=auto_filter_sparse_switch,
        propagate_var16_const=propagate_var16_const,
        seed_var16=seed_var16,
        infer_entry_var16_seed=infer_entry_var16_seed,
    )


def _parse_seed_var16(values: list[str]) -> dict[int, int]:
    result: dict[int, int] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"invalid --seed-var16 value: {raw!r} (expected INDEX=VALUE)")
        key_text, value_text = raw.split("=", 1)
        index = int(key_text.strip(), 0)
        value = int(value_text.strip(), 0)
        if index < 0:
            raise ValueError(f"invalid --seed-var16 index: {index}")
        result[index] = value
    return result


def build_mainline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Masquerade Himauri disassembler")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Masquerade Himauri disassembler")
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
        help="Propagate var16 constants (and 0x5E->0x0A resource slot links) to narrow CFG targets",
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


def mainline_main(argv: list[str] | None = None) -> int:
    parser = build_mainline_parser()
    args = parser.parse_args(argv)
    filter_switch_targets = args.conservative_cfg
    follow_call_fallthrough = not args.conservative_cfg
    result = disasm_file(
        args.input,
        limit=args.limit,
        entry=args.entry,
        strict_expr=args.strict_expr,
        follow_call_fallthrough=follow_call_fallthrough,
        filter_switch_targets=filter_switch_targets,
        filter_branch_targets=False,
        filter_call_targets=False,
        sanitize_branch_targets=True,
        switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        switch_plus2_fallback=False,
        auto_filter_sparse_switch=False,
        propagate_var16_const=False,
        seed_var16=None,
        infer_entry_var16_seed=False,
    )
    payload = result.to_dict()
    payload["input"] = str(args.input)
    payload["strict_expr"] = args.strict_expr
    payload["conservative_cfg"] = args.conservative_cfg
    payload["filter_switch_targets"] = filter_switch_targets
    payload["auto_filter_sparse_switch"] = False
    payload["filter_branch_targets"] = False
    payload["filter_call_targets"] = False
    payload["sanitize_branch_targets"] = True
    payload["no_call_fallthrough"] = not follow_call_fallthrough
    payload["switch_check_depth"] = DEFAULT_SWITCH_CHECK_DEPTH
    payload["switch_plus2_fallback"] = False
    payload["propagate_var16_const"] = False
    payload["seed_var16"] = {}
    payload["infer_entry_var16_seed"] = False
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] decoded: {payload['decoded_count']}")
    print(f"[ok] errors: {len(payload['errors'])}")
    print(f"[ok] output: {args.out_file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    seed_var16 = _parse_seed_var16(args.seed_var16)
    filter_switch_targets = args.conservative_cfg or args.filter_switch_targets
    follow_call_fallthrough = not (args.conservative_cfg or args.no_call_fallthrough)
    switch_plus2_enabled = args.switch_plus2_fallback and (filter_switch_targets or args.auto_filter_sparse_switch)
    result = disasm_file(
        args.input,
        limit=args.limit,
        entry=args.entry,
        strict_expr=args.strict_expr,
        follow_call_fallthrough=follow_call_fallthrough,
        filter_switch_targets=filter_switch_targets,
        filter_branch_targets=args.filter_branch_targets,
        filter_call_targets=args.filter_call_targets,
        sanitize_branch_targets=not args.no_branch_target_sanitize,
        switch_check_depth=args.switch_check_depth,
        switch_plus2_fallback=switch_plus2_enabled,
        auto_filter_sparse_switch=args.auto_filter_sparse_switch,
        propagate_var16_const=args.propagate_var16_const,
        seed_var16=seed_var16,
        infer_entry_var16_seed=args.infer_entry_var16_seed,
    )
    payload = result.to_dict()
    payload["input"] = str(args.input)
    payload["strict_expr"] = args.strict_expr
    payload["conservative_cfg"] = args.conservative_cfg
    payload["filter_switch_targets"] = filter_switch_targets
    payload["auto_filter_sparse_switch"] = args.auto_filter_sparse_switch
    payload["filter_branch_targets"] = args.filter_branch_targets
    payload["filter_call_targets"] = args.filter_call_targets
    payload["sanitize_branch_targets"] = not args.no_branch_target_sanitize
    payload["no_call_fallthrough"] = not follow_call_fallthrough
    payload["switch_check_depth"] = args.switch_check_depth
    payload["switch_plus2_fallback"] = switch_plus2_enabled
    payload["propagate_var16_const"] = args.propagate_var16_const
    payload["seed_var16"] = {str(key): value for key, value in sorted(seed_var16.items())}
    payload["infer_entry_var16_seed"] = args.infer_entry_var16_seed
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] decoded: {len(result.decoded)}")
    print(f"[ok] errors: {len(result.errors)}")
    print(f"[ok] output: {args.out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

