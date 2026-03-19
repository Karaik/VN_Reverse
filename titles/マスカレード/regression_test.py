from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from solution.common.hxp import HxpArchive, build_him4, build_him5, load_manifest
from solution.script.branch_audit import audit_file as audit_branch_file
from solution.script.branch_overview import build_overview as build_branch_overview
from solution.script.disasm import DEFAULT_SWITCH_CHECK_DEPTH, disasm_cfg, disasm_file
from solution.script.expression import decode_expression_with_const, decode_expression_with_const_and_writes
from solution.script.himauri import parse_stream_entry
from solution.script.opcodes import load_opcode_specs
from solution.script.probe import parse_himauri
from solution.script.reader import Reader
from solution.script.strings import decode_string_expr
from solution.script.switch_audit import audit_file
from solution.script.text import _transform_string_sub402280, dump_text_items


TITLE_DIR = Path(__file__).parent
TMP_DIR = TITLE_DIR / "tmp" / "formal_regression"
SCRIPT_SAMPLES = ["sc1_3", "sc24_2e033g_01_a", "scend_kingh"]
BRANCH_AUDIT_SAMPLES = ["sc24_2e034h_01_a", "sc30_1e051_b"]


def compare_bytes(left: Path, right: Path) -> dict:
    left_data = left.read_bytes()
    right_data = right.read_bytes()
    same = left_data == right_data
    first_diff = -1
    if not same:
        limit = min(len(left_data), len(right_data))
        for index in range(limit):
            if left_data[index] != right_data[index]:
                first_diff = index
                break
        if first_diff == -1 and len(left_data) != len(right_data):
            first_diff = limit
    return {
        "same": same,
        "left_size": len(left_data),
        "right_size": len(right_data),
        "first_diff": first_diff,
    }


def run_exact_roundtrip(archive_path: Path, work_dir: Path) -> dict:
    archive = HxpArchive.load(archive_path)
    manifest_path = archive.unpack(work_dir / "unpack", dump_unpacked=True)
    manifest = load_manifest(manifest_path)
    entries = []
    for entry in manifest["entries"]:
        raw_block = (manifest_path.parent / entry["raw_path"]).read_bytes()
        entries.append(
            {
                "name": entry["name"],
                "raw_block": raw_block,
                "bucket_index": entry.get("bucket_index", -1),
                "bucket_order": entry.get("bucket_order", -1),
            }
        )
    if manifest["magic"] == "Him4":
        rebuilt = build_him4(entries)
    else:
        rebuilt = build_him5(entries, manifest["bucket_count"])
    rebuilt_path = work_dir / f"{archive_path.stem}.repacked{archive_path.suffix}"
    rebuilt_path.write_bytes(rebuilt)
    return compare_bytes(archive_path, rebuilt_path)


def run_uncompressed_roundtrip(archive_path: Path, work_dir: Path, names: list[str]) -> dict:
    archive = HxpArchive.load(archive_path)
    manifest_path = archive.unpack(work_dir / "unpack", dump_unpacked=True)
    manifest = load_manifest(manifest_path)
    entries = []
    for entry in manifest["entries"]:
        unpacked_path = manifest_path.parent / entry["unpacked_path"]
        payload = unpacked_path.read_bytes() if entry["unpacked_path"] else (manifest_path.parent / entry["payload_path"]).read_bytes()
        raw_block = (0).to_bytes(4, "little") + len(payload).to_bytes(4, "little") + payload
        entries.append(
            {
                "name": entry["name"],
                "raw_block": raw_block,
                "bucket_index": entry.get("bucket_index", -1),
                "bucket_order": entry.get("bucket_order", -1),
            }
        )
    rebuilt = build_him5(entries, manifest["bucket_count"])
    rebuilt_path = work_dir / f"{archive_path.stem}.uncompressed{archive_path.suffix}"
    rebuilt_path.write_bytes(rebuilt)
    rebuilt_archive = HxpArchive.load(rebuilt_path)
    rebuilt_manifest_path = rebuilt_archive.unpack(work_dir / "unpack_rebuilt", dump_unpacked=True)
    results = {}
    for name in names:
        left = manifest_path.parent / "unpacked" / f"{name}.bin"
        right = rebuilt_manifest_path.parent / "unpacked" / f"{name}.bin"
        results[name] = compare_bytes(left, right)
    return {
        "archive_size": rebuilt_path.stat().st_size,
        "samples": results,
    }


def run_script_smoke(
    input_path: Path,
    *,
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
    limit: int = 512,
) -> dict:
    use_filter_switch_targets = conservative_cfg or filter_switch_targets
    use_follow_call_fallthrough = not (conservative_cfg or no_call_fallthrough)
    disasm = disasm_file(
        input_path,
        limit=limit,
        strict_expr=strict_expr,
        follow_call_fallthrough=use_follow_call_fallthrough,
        filter_switch_targets=use_filter_switch_targets,
        filter_branch_targets=filter_branch_targets,
        filter_call_targets=filter_call_targets,
        sanitize_branch_targets=sanitize_branch_targets,
        switch_check_depth=switch_check_depth,
        switch_plus2_fallback=switch_plus2_fallback and (use_filter_switch_targets or auto_filter_sparse_switch),
        auto_filter_sparse_switch=auto_filter_sparse_switch,
        propagate_var16_const=propagate_var16_const,
        seed_var16=seed_var16,
        infer_entry_var16_seed=infer_entry_var16_seed,
    )
    text_dump = dump_text_items(
        input_path,
        limit=limit,
        strict_expr=strict_expr,
        conservative_cfg=conservative_cfg,
        filter_switch_targets=filter_switch_targets,
        filter_branch_targets=filter_branch_targets,
        filter_call_targets=filter_call_targets,
        sanitize_branch_targets=sanitize_branch_targets,
        no_call_fallthrough=no_call_fallthrough,
        switch_check_depth=switch_check_depth,
        switch_plus2_fallback=switch_plus2_fallback and (use_filter_switch_targets or auto_filter_sparse_switch),
        auto_filter_sparse_switch=auto_filter_sparse_switch,
        propagate_var16_const=propagate_var16_const,
        seed_var16=seed_var16,
        infer_entry_var16_seed=infer_entry_var16_seed,
    )
    unknown = sorted({instruction.opcode for instruction in disasm.decoded if instruction.name.startswith("op_")})
    return {
        "entry": disasm.entry,
        "with_line": disasm.with_line,
        "switch_check_depth": switch_check_depth if (use_filter_switch_targets or auto_filter_sparse_switch) else None,
        "filter_switch_targets": use_filter_switch_targets,
        "auto_filter_sparse_switch": auto_filter_sparse_switch,
        "filter_branch_targets": filter_branch_targets,
        "filter_call_targets": filter_call_targets,
        "sanitize_branch_targets": sanitize_branch_targets,
        "no_call_fallthrough": not use_follow_call_fallthrough,
        "switch_plus2_fallback": switch_plus2_fallback and (use_filter_switch_targets or auto_filter_sparse_switch),
        "propagate_var16_const": propagate_var16_const,
        "seed_var16": {str(key): value for key, value in sorted((seed_var16 or {}).items())},
        "infer_entry_var16_seed": infer_entry_var16_seed,
        "decoded_count": len(disasm.decoded),
        "error_count": len(disasm.errors),
        "first_error": disasm.errors[0] if disasm.errors else None,
        "unknown_opcode_count": len(unknown),
        "unknown_opcodes": [f"0x{opcode:02X}" for opcode in unknown],
        "text_count": text_dump["text_count"],
    }


def run_expression_sanity() -> dict:
    cases = [
        {
            "name": "add_1_2",
            "expr": bytes([0x01, 0x02, 0x60, 0xFF]),
            "expected_const": 3,
        },
        {
            "name": "op40_lo0_assign_shape",
            "expr": bytes([0x1E, 0x00, 0x05, 0x40, 0xFF]),
            "expected_const": 5,
        },
        {
            "name": "op41_plus_assign_shape",
            "expr": bytes([0x05, 0x06, 0x41, 0xFF]),
            "expected_const": 11,
        },
        {
            "name": "cmp_eq_false",
            "expr": bytes([0x02, 0x01, 0x50, 0xFF]),
            "expected_const": 0,
        },
        {
            "name": "c_div_toward_zero",
            "expr": bytes([0x0D, 0xFD, 0x02, 0x69, 0xFF]),
            "expected_const": -1,
        },
        {
            "name": "c_mod_toward_zero",
            "expr": bytes([0x0D, 0xFD, 0x02, 0x6A, 0xFF]),
            "expected_const": -1,
        },
        {
            "name": "cmp_unknown_passthrough_rhs",
            "expr": bytes([0x02, 0x07, 0x56, 0xFF]),
            "expected_const": 7,
        },
        {
            "name": "op60_unknown_passthrough_rhs",
            "expr": bytes([0x03, 0x04, 0x62, 0xFF]),
            "expected_const": 4,
        },
        {
            "name": "op70_unknown_passthrough_top",
            "expr": bytes([0x05, 0x77, 0xFF]),
            "expected_const": 5,
        },
        {
            "name": "atan100_neg_rhs_quadrant",
            "expr": bytes([0x01, 0x00, 0x75, 0xFF]),
            "expected_const": 0,
        },
        {
            "name": "var16_seed_const_fold",
            "expr": bytes([0x1E, 0xFF, 0x00, 0x54, 0xFF]),
            "expected_const": 1,
            "var16_state": {255: 1},
        },
    ]
    results = []
    for case in cases:
        reader = Reader(case["expr"], 0)
        text, const_value = decode_expression_with_const(
            reader,
            strict=True,
            require_single=False,
            var16_state=case.get("var16_state"),
        )
        ok = reader.pos == len(case["expr"]) and const_value == case["expected_const"]
        results.append(
            {
                "name": case["name"],
                "text": text,
                "const": const_value,
                "expected_const": case["expected_const"],
                "var16_state": case.get("var16_state", {}),
                "final_pos": reader.pos,
                "size": len(case["expr"]),
                "ok": ok,
            }
        )
    write_case_reader = Reader(bytes([0x1E, 0x02, 0x03, 0x41, 0xFF]), 0)
    write_text, write_const, write_rows = decode_expression_with_const_and_writes(
        write_case_reader,
        strict=True,
        require_single=False,
        var16_state={2: 5},
    )
    write_ok = (
        write_case_reader.pos == 5
        and write_const == 8
        and bool(write_rows)
        and write_rows[0].get("op") == "+="
        and write_rows[0].get("var_type") == 16
        and write_rows[0].get("index_const") == 2
        and write_rows[0].get("value_const") == 8
    )
    results.append(
        {
            "name": "op41_write_capture_seeded",
            "text": write_text,
            "const": write_const,
            "expected_const": 8,
            "var16_state": {"2": 5},
            "writes": write_rows,
            "final_pos": write_case_reader.pos,
            "size": 5,
            "ok": write_ok,
        }
    )
    return {
        "all_ok": all(item["ok"] for item in results),
        "cases": results,
    }


def run_string_expr_sanity() -> dict:
    cases = [
        {
            "name": "literal_direct",
            "blob": bytes([0x41, 0x00]),
            "expect": {"type": "literal", "text": "A"},
        },
        {
            "name": "literal_empty",
            "blob": bytes([0x00]),
            "expect": {"type": "literal", "text": ""},
        },
        {
            "name": "ref_u8_str19",
            "blob": bytes([0x01, 0x05]),
            "expect": {"type": "string_table_ref", "kind": 1, "table": "str19", "index": 5},
        },
        {
            "name": "ref_u8_unknown_kind_runtime_empty",
            "blob": bytes([0x02, 0x08]),
            "expect": {
                "type": "string_table_ref",
                "kind": 2,
                "index": 8,
                "runtime_fallback": "empty_literal",
            },
        },
        {
            "name": "ref_u16_str18",
            "blob": bytes([0x09, 0x01, 0x2C]),
            "expect": {"type": "string_table_ref", "kind": 3, "table": "str18", "index": 300},
        },
        {
            "name": "ref_expr_str18_const",
            "blob": bytes([0x0F, 0x05, 0xFF]),
            "expect": {
                "type": "string_table_ref",
                "kind": 3,
                "table": "str18",
                "index_expr": "5",
                "index_const": 5,
            },
        },
    ]
    results: list[dict[str, object]] = []
    for case in cases:
        reader = Reader(case["blob"], 0)
        payload = decode_string_expr(reader, strict_expr=True)
        expected = case["expect"]
        ok = reader.pos == len(case["blob"]) and all(payload.get(key) == value for key, value in expected.items())
        results.append(
            {
                "name": case["name"],
                "payload": payload,
                "expected_subset": expected,
                "final_pos": reader.pos,
                "size": len(case["blob"]),
                "ok": ok,
            }
        )
    return {
        "all_ok": all(item["ok"] for item in results),
        "cases": results,
    }


def run_transform_string_sanity() -> dict:
    cases = [
        {
            "name": "plain_copy",
            "source": "ABC",
            "str18": {},
            "str19": {},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": "ABC",
        },
        {
            "name": "slash_and_cr_escape",
            "source": "A\\\\B\\nC",
            "str18": {},
            "str19": {},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": "A\\B\rC",
        },
        {
            "name": "hex_escape",
            "source": "A\\'41B",
            "str18": {},
            "str19": {},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": "AAB",
        },
        {
            "name": "table_ref_str18_with_width",
            "source": "\\s5[_sg2]",
            "str18": {2: "X"},
            "str19": {},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": "    X",
        },
        {
            "name": "table_ref_str19",
            "source": "\\s[_ss1]",
            "str18": {},
            "str19": {1: "YZ"},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": "YZ",
        },
        {
            "name": "numeric_insert_i",
            "source": "\\i5[_is1]",
            "str18": {},
            "str19": {},
            "num16": {1: 42},
            "num32": {},
            "num48": {},
            "expected": "   42",
        },
        {
            "name": "numeric_insert_c",
            "source": "\\c[_is2]",
            "str18": {},
            "str19": {},
            "num16": {2: 65},
            "num32": {},
            "num48": {},
            "expected": "A",
        },
        {
            "name": "numeric_insert_z_fullwidth",
            "source": "\\z[_is3]",
            "str18": {},
            "str19": {},
            "num16": {3: 12},
            "num32": {},
            "num48": {},
            "expected": bytes((0x82, 0x50, 0x82, 0x51)).decode("cp932"),
        },
        {
            "name": "unresolved_table_ref_returns_none",
            "source": "\\s[_ss9]",
            "str18": {},
            "str19": {},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": None,
        },
        {
            "name": "unresolved_numeric_ref_returns_none",
            "source": "\\i[_is9]",
            "str18": {},
            "str19": {},
            "num16": {},
            "num32": {},
            "num48": {},
            "expected": None,
        },
    ]
    results: list[dict[str, object]] = []
    for case in cases:
        transformed = _transform_string_sub402280(
            case["source"],
            str18_state=dict(case["str18"]),
            str19_state=dict(case["str19"]),
            num16_state=dict(case["num16"]),
            num32_state=dict(case["num32"]),
            num48_state=dict(case["num48"]),
        )
        ok = transformed == case["expected"]
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "str18": case["str18"],
                "str19": case["str19"],
                "num16": case["num16"],
                "num32": case["num32"],
                "num48": case["num48"],
                "expected": case["expected"],
                "actual": transformed,
                "ok": ok,
            }
        )
    return {
        "all_ok": all(item["ok"] for item in results),
        "cases": results,
    }


def run_text_resolution_sample(unpack_dir: Path) -> dict:
    sample = unpack_dir / "sc23_3e086.bin"
    if not sample.exists():
        return {"sample_exists": False}
    payload = dump_text_items(
        sample,
        limit=512,
        conservative_cfg=True,
        filter_branch_targets=True,
        filter_call_targets=True,
        switch_check_depth=8,
        switch_plus2_fallback=True,
        propagate_var16_const=True,
        infer_entry_var16_seed=True,
    )
    resolved_items = payload.get("resolved_items", [])
    first_resolved_item = resolved_items[0] if resolved_items else None
    return {
        "sample_exists": True,
        "decoded_count": payload["decoded_count"],
        "error_count": payload["error_count"],
        "text_count": payload["text_count"],
        "resolved_ref_count": payload.get("resolved_ref_count", 0),
        "first_resolved_item": first_resolved_item,
    }


def run_call_fallthrough_sample(unpack_dir: Path) -> dict:
    sample = unpack_dir / "sc4_3.bin"
    if not sample.exists():
        return {"sample_exists": False}
    with_fallthrough = disasm_file(
        sample,
        limit=512,
        strict_expr=False,
        follow_call_fallthrough=True,
    )
    no_fallthrough = disasm_file(
        sample,
        limit=512,
        strict_expr=False,
        follow_call_fallthrough=False,
    )
    opcode09_rows: list[dict[str, object]] = []
    resume0_count = 0
    resume1_count = 0
    for item in with_fallthrough.decoded:
        if item.opcode != 0x09:
            continue
        mode_const = None
        resume_const = None
        for arg in reversed(item.args):
            if not isinstance(arg, dict):
                continue
            if mode_const is None and isinstance(arg.get("mode_const"), int):
                mode_const = int(arg["mode_const"])
            if resume_const is None and isinstance(arg.get("resume_fallthrough_const"), int):
                resume_const = int(arg["resume_fallthrough_const"])
            if mode_const is not None and resume_const is not None:
                break
        if resume_const == 0:
            resume0_count += 1
        elif resume_const == 1:
            resume1_count += 1
        opcode09_rows.append(
            {
                "offset_hex": f"0x{item.offset:06X}",
                "mode_const": mode_const,
                "resume_fallthrough_const": resume_const,
            }
        )
    return {
        "sample_exists": True,
        "with_fallthrough_decoded_count": len(with_fallthrough.decoded),
        "with_fallthrough_error_count": len(with_fallthrough.errors),
        "no_fallthrough_decoded_count": len(no_fallthrough.decoded),
        "no_fallthrough_error_count": len(no_fallthrough.errors),
        "opcode09_count": len(opcode09_rows),
        "opcode09_resume0_count": resume0_count,
        "opcode09_resume1_count": resume1_count,
        "opcode09_rows": opcode09_rows,
    }


def run_resource_slot_propagation_sanity() -> dict:
    # Synthetic stream:
    #  0x5E: bind resource slot 3 to script offset 0x001B
    #  0x0A: load slot 3 with args -> should infer target 0x001B when propagation is on
    #  0xFF: fallthrough endpoint
    #  0x71: target body
    #  0xFF: target endpoint
    target = 0x001B
    stream = bytes(
        [
            0x5E,
            0x03,
            0xFF,
            (target >> 16) & 0xFF,
            (target >> 8) & 0xFF,
            target & 0xFF,
            0x0A,
            0x03,
            0xFF,
            0x00,
            0xFF,
            0x71,
            0xFF,
        ]
    )
    payload = b"Himauri\x00" + (16 + len(stream)).to_bytes(3, "big") + bytes([0]) + bytes(4) + stream
    entry, with_line = parse_stream_entry(payload)
    specs = load_opcode_specs()
    without_prop = disasm_cfg(
        payload,
        entry,
        with_line,
        specs,
        limit=64,
        strict_expr=False,
        follow_call_fallthrough=True,
        propagate_var16_const=False,
    )
    with_prop = disasm_cfg(
        payload,
        entry,
        with_line,
        specs,
        limit=64,
        strict_expr=False,
        follow_call_fallthrough=True,
        propagate_var16_const=True,
    )
    target_reached_without = any(item.offset == target for item in without_prop.decoded)
    target_reached_with = any(item.offset == target for item in with_prop.decoded)
    resource_target_const = None
    for item in with_prop.decoded:
        if item.opcode != 0x0A:
            continue
        for arg in reversed(item.args):
            if not isinstance(arg, dict):
                continue
            value = arg.get("resource_script_target_const")
            if isinstance(value, int):
                resource_target_const = value
                break
        break
    return {
        "sample_exists": True,
        "target_offset_hex": f"0x{target:06X}",
        "without_propagate_decoded_count": len(without_prop.decoded),
        "without_propagate_error_count": len(without_prop.errors),
        "with_propagate_decoded_count": len(with_prop.decoded),
        "with_propagate_error_count": len(with_prop.errors),
        "target_reached_without_propagate": target_reached_without,
        "target_reached_with_propagate": target_reached_with,
        "opcode0A_resource_target_const": resource_target_const,
        "all_ok": (
            not target_reached_without
            and target_reached_with
            and resource_target_const == target
        ),
    }


def run_resource_slot_type_sanity() -> dict:
    # Synthetic stream:
    #  0x4B: bind slot 3 to DLL object (type 9)
    #  0x0A: load slot 3 with args -> should report slot type 9 and no script target
    stream = bytes(
        [
            0x4B,
            0x03,
            0xFF,
            0x61,
            0x00,
            0x0A,
            0x03,
            0xFF,
            0x00,
            0xFF,
        ]
    )
    payload = b"Himauri\x00" + (16 + len(stream)).to_bytes(3, "big") + bytes([0]) + bytes(4) + stream
    entry, with_line = parse_stream_entry(payload)
    specs = load_opcode_specs()
    with_prop = disasm_cfg(
        payload,
        entry,
        with_line,
        specs,
        limit=64,
        strict_expr=False,
        follow_call_fallthrough=True,
        propagate_var16_const=True,
    )
    slot_type_const = None
    slot_source = None
    resource_target_const = None
    for item in with_prop.decoded:
        if item.opcode != 0x0A:
            continue
        for arg in reversed(item.args):
            if not isinstance(arg, dict):
                continue
            if slot_type_const is None and isinstance(arg.get("resource_slot_type_const"), int):
                slot_type_const = int(arg["resource_slot_type_const"])
            if slot_source is None and isinstance(arg.get("resource_slot_source"), str):
                slot_source = str(arg["resource_slot_source"])
            if resource_target_const is None and isinstance(arg.get("resource_script_target_const"), int):
                resource_target_const = int(arg["resource_script_target_const"])
        break
    return {
        "sample_exists": True,
        "decoded_count": len(with_prop.decoded),
        "error_count": len(with_prop.errors),
        "resource_slot_type_const": slot_type_const,
        "resource_slot_source": slot_source,
        "resource_script_target_const": resource_target_const,
        "all_ok": (
            slot_type_const == 9
            and slot_source == "opcode_4B_state"
            and resource_target_const is None
        ),
    }


def run_archive_script_coverage(
    unpack_dir: Path,
    *,
    limit: int = 256,
    filter_branch_targets: bool = False,
    filter_call_targets: bool = False,
    sanitize_branch_targets: bool = True,
    switch_check_depth: int = DEFAULT_SWITCH_CHECK_DEPTH,
    infer_entry_var16_seed: bool = False,
) -> dict:
    files = sorted(unpack_dir.glob("*.bin"))
    unknown_files: list[str] = []
    unknown_opcodes: set[int] = set()
    total_errors = 0
    error_rows: list[dict[str, object]] = []
    for path in files:
        result = disasm_file(
            path,
            limit=limit,
            strict_expr=False,
            follow_call_fallthrough=False,
            filter_switch_targets=True,
            filter_branch_targets=filter_branch_targets,
            filter_call_targets=filter_call_targets,
            sanitize_branch_targets=sanitize_branch_targets,
            switch_check_depth=switch_check_depth,
            infer_entry_var16_seed=infer_entry_var16_seed,
        )
        total_errors += len(result.errors)
        if result.errors:
            error_rows.append(
                {
                    "name": path.name,
                    "error_count": len(result.errors),
                    "decoded_count": len(result.decoded),
                    "first_error_offset": result.errors[0]["offset"],
                    "first_error_offset_hex": f"0x{result.errors[0]['offset']:06X}",
                    "first_error": result.errors[0]["error"],
                }
            )
        current_unknown = sorted({item.opcode for item in result.decoded if item.name.startswith("op_")})
        if current_unknown:
            unknown_files.append(path.name)
            unknown_opcodes.update(current_unknown)
    error_rows.sort(key=lambda row: int(row["error_count"]), reverse=True)
    return {
        "file_count": len(files),
        "limit": limit,
        "unknown_file_count": len(unknown_files),
        "unknown_files_preview": unknown_files[:20],
        "unknown_opcode_count": len(unknown_opcodes),
        "unknown_opcodes": [f"0x{value:02X}" for value in sorted(unknown_opcodes)],
        "total_error_count": total_errors,
        "error_file_count": len(error_rows),
        "top_error_files": error_rows[:20],
        "filter_branch_targets": filter_branch_targets,
        "filter_call_targets": filter_call_targets,
        "sanitize_branch_targets": sanitize_branch_targets,
        "switch_check_depth": switch_check_depth,
        "infer_entry_var16_seed": infer_entry_var16_seed,
    }


def run_archive_named_opcode_coverage(
    unpack_dir: Path,
    *,
    limit: int = 1024,
    switch_check_depth: int = 8,
) -> dict:
    files = sorted(unpack_dir.glob("*.bin"))
    unresolved_name_counter: Counter[str] = Counter()
    unresolved_opcode_counter: Counter[int] = Counter()
    unresolved_rows: list[dict[str, object]] = []
    total_decoded = 0
    total_errors = 0
    for path in files:
        result = disasm_file(
            path,
            limit=limit,
            strict_expr=False,
            follow_call_fallthrough=False,
            filter_switch_targets=True,
            filter_branch_targets=True,
            filter_call_targets=True,
            sanitize_branch_targets=True,
            switch_check_depth=switch_check_depth,
            switch_plus2_fallback=True,
            propagate_var16_const=True,
            infer_entry_var16_seed=True,
        )
        total_decoded += len(result.decoded)
        total_errors += len(result.errors)
        local_rows: list[dict[str, object]] = []
        for item in result.decoded:
            if item.name.startswith("call_") or item.name.startswith("op_"):
                unresolved_name_counter[item.name] += 1
                unresolved_opcode_counter[item.opcode] += 1
                local_rows.append(
                    {
                        "offset_hex": f"0x{item.offset:06X}",
                        "opcode_hex": f"0x{item.opcode:02X}",
                        "name": item.name,
                    }
                )
        if local_rows:
            unresolved_rows.append(
                {
                    "file": path.name,
                    "count": len(local_rows),
                    "items": local_rows[:16],
                }
            )
    unresolved_rows.sort(key=lambda row: int(row["count"]), reverse=True)
    return {
        "file_count": len(files),
        "limit": limit,
        "switch_check_depth": switch_check_depth,
        "decoded_count": total_decoded,
        "error_count": total_errors,
        "unresolved_name_count": sum(unresolved_name_counter.values()),
        "unresolved_names": [
            {"name": name, "count": count}
            for name, count in unresolved_name_counter.most_common()
        ],
        "unresolved_opcode_count": len(unresolved_opcode_counter),
        "unresolved_opcodes": [
            {"opcode_hex": f"0x{opcode:02X}", "count": count}
            for opcode, count in unresolved_opcode_counter.most_common()
        ],
        "files_with_unresolved_count": len(unresolved_rows),
        "files_with_unresolved_preview": unresolved_rows[:20],
    }


def main() -> int:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    initial = run_exact_roundtrip(TITLE_DIR / "game" / "Initial.hxp", TMP_DIR / "initial")
    scn = run_exact_roundtrip(TITLE_DIR / "game" / "DATA" / "Masq_scn.hxp", TMP_DIR / "scn")
    uncompressed = run_uncompressed_roundtrip(
        TITLE_DIR / "game" / "DATA" / "Masq_scn.hxp",
        TMP_DIR / "scn_uncompressed",
        SCRIPT_SAMPLES,
    )
    probe_target = TMP_DIR / "scn" / "unpack" / "unpacked" / "sc1_3.bin"
    probe = parse_himauri(probe_target.read_bytes())
    conservative_samples = {
        name: run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / f"{name}.bin",
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        )
        for name in SCRIPT_SAMPLES
    }
    conservative_plus2_samples = {
        name: run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / f"{name}.bin",
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            switch_plus2_fallback=True,
        )
        for name in SCRIPT_SAMPLES
    }
    switch_filtered_samples = {
        name: run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / f"{name}.bin",
            filter_switch_targets=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        )
        for name in SCRIPT_SAMPLES
    }
    switch_filtered_plus2_samples = {
        name: run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / f"{name}.bin",
            filter_switch_targets=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            switch_plus2_fallback=True,
        )
        for name in SCRIPT_SAMPLES
    }
    switch_audit_samples = {}
    for name in SCRIPT_SAMPLES:
        audit = audit_file(
            TMP_DIR / "scn" / "unpack" / "unpacked" / f"{name}.bin",
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        )
        switch_audit_samples[name] = {
            "switch_count": audit["switch_count"],
            "switches": [
                {
                    "switch_offset_hex": item["switch_offset_hex"],
                    "entry_path_has_var16_writer": item["entry_path_has_var16_writer"],
                    "entry_path_var16_writer_offsets_hex": item["entry_path_var16_writer_offsets_hex"],
                    "entry_cfg_has_var16_writer": item["entry_cfg_has_var16_writer"],
                    "entry_cfg_var16_writer_offsets_hex": item["entry_cfg_var16_writer_offsets_hex"],
                    "case_count": item["case_count"],
                    "below_entry": item["summary"]["below_entry"],
                    "plausible": item["summary"]["plausible"],
                    "strict_plausible": item["summary"]["strict_plausible"],
                    "line_mode_plausible": item["summary"]["line_mode_plausible"],
                    "plus2_plausible": item["summary"]["plus2_plausible"],
                    "plausible_indices": item["summary"]["plausible_indices"],
                    "strict_plausible_indices": item["summary"]["strict_plausible_indices"],
                    "plus2_plausible_indices": item["summary"]["plus2_plausible_indices"],
                }
                for item in audit["switches"]
            ],
        }
    branch_audit_samples = {}
    for name in BRANCH_AUDIT_SAMPLES:
        audit = audit_branch_file(
            TMP_DIR / "scn" / "unpack" / "unpacked" / f"{name}.bin",
            conservative_cfg=True,
            sanitize_branch_targets=False,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        )
        branch_audit_samples[name] = {
            "branch_count": audit["branch_count"],
            "summary": audit["summary"],
            "disasm": audit["disasm"],
        }
    branch_overview = build_branch_overview(
        TMP_DIR / "scn" / "unpack" / "unpacked",
        limit=256,
        switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        sample_limit=100,
    )
    branch_overview["unpack_dir"] = str((TMP_DIR / "scn" / "unpack" / "unpacked").relative_to(TITLE_DIR))
    summary = {
        "initial_exact": initial,
        "masq_scn_exact": scn,
        "masq_scn_uncompressed": uncompressed,
        "probe": {
            "declared_size": probe["declared_size"],
            "actual_size": probe["actual_size"],
            "flag": probe["flag"],
            "string_count": probe["string_count"],
        },
        "expression_sanity": run_expression_sanity(),
        "string_expr_sanity": run_string_expr_sanity(),
        "transform_string_sanity": run_transform_string_sanity(),
        "text_resolution_sample": run_text_resolution_sample(
            TMP_DIR / "scn" / "unpack" / "unpacked",
        ),
        "call_fallthrough_sample": run_call_fallthrough_sample(
            TMP_DIR / "scn" / "unpack" / "unpacked",
        ),
        "resource_slot_propagation_sanity": run_resource_slot_propagation_sanity(),
        "resource_slot_type_sanity": run_resource_slot_type_sanity(),
        "script_smoke": run_script_smoke(probe_target),
        "script_smoke_auto_sparse_switch": run_script_smoke(
            probe_target,
            auto_filter_sparse_switch=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        ),
        "script_smoke_auto_sparse_switch_plus2": run_script_smoke(
            probe_target,
            auto_filter_sparse_switch=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            switch_plus2_fallback=True,
        ),
        "script_smoke_strict_expr_auto_sparse_switch": run_script_smoke(
            probe_target,
            strict_expr=True,
            auto_filter_sparse_switch=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        ),
        "script_smoke_strict_expr": run_script_smoke(probe_target, strict_expr=True),
        "script_smoke_switch_filtered": run_script_smoke(
            probe_target,
            filter_switch_targets=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        ),
        "script_smoke_switch_filtered_plus2": run_script_smoke(
            probe_target,
            filter_switch_targets=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            switch_plus2_fallback=True,
        ),
        "script_smoke_conservative_cfg": run_script_smoke(
            probe_target,
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        ),
        "script_smoke_conservative_cfg_plus2": run_script_smoke(
            probe_target,
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            switch_plus2_fallback=True,
        ),
        "script_smoke_conservative_cfg_branch_filtered": run_script_smoke(
            probe_target,
            conservative_cfg=True,
            filter_branch_targets=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        ),
        "script_smoke_conservative_cfg_branch_call_filtered": run_script_smoke(
            probe_target,
            conservative_cfg=True,
            filter_branch_targets=True,
            filter_call_targets=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
        ),
        "script_smoke_conservative_cfg_seed_var16_0_12": run_script_smoke(
            probe_target,
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            seed_var16={0: 12},
        ),
        "script_smoke_sc24_2e034h_seed255_1_no_branch_sanitize": run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / "sc24_2e034h_01_a.bin",
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            sanitize_branch_targets=False,
            seed_var16={255: 1},
        ),
        "script_smoke_sc24_2e034h_seed255_0_no_branch_sanitize": run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / "sc24_2e034h_01_a.bin",
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            sanitize_branch_targets=False,
            seed_var16={255: 0},
        ),
        "script_smoke_sc24_2e034h_no_branch_sanitize_infer_entry_seed": run_script_smoke(
            TMP_DIR / "scn" / "unpack" / "unpacked" / "sc24_2e034h_01_a.bin",
            conservative_cfg=True,
            switch_check_depth=DEFAULT_SWITCH_CHECK_DEPTH,
            sanitize_branch_targets=False,
            infer_entry_var16_seed=True,
        ),
        "script_smoke_conservative_cfg_samples": conservative_samples,
        "script_smoke_conservative_cfg_plus2_samples": conservative_plus2_samples,
        "script_smoke_switch_filtered_samples": switch_filtered_samples,
        "script_smoke_switch_filtered_plus2_samples": switch_filtered_plus2_samples,
        "switch_audit_samples": switch_audit_samples,
        "branch_audit_samples": branch_audit_samples,
        "branch_overview": branch_overview,
        "archive_script_coverage": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
        ),
        "archive_script_coverage_no_branch_sanitize": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
            sanitize_branch_targets=False,
        ),
        "archive_script_coverage_no_branch_sanitize_infer_entry_seed": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
            sanitize_branch_targets=False,
            infer_entry_var16_seed=True,
        ),
        "archive_script_coverage_branch_filtered": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
            filter_branch_targets=True,
        ),
        "archive_script_coverage_branch_call_filtered": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
            filter_branch_targets=True,
            filter_call_targets=True,
        ),
        "archive_script_coverage_branch_filtered_depth8": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
            filter_branch_targets=True,
            switch_check_depth=8,
        ),
        "archive_script_coverage_branch_filtered_depth16": run_archive_script_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=256,
            filter_branch_targets=True,
            switch_check_depth=16,
        ),
        "archive_named_opcode_coverage": run_archive_named_opcode_coverage(
            TMP_DIR / "scn" / "unpack" / "unpacked",
            limit=1024,
            switch_check_depth=8,
        ),
    }
    summary_path = TMP_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary_path.relative_to(TITLE_DIR))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
