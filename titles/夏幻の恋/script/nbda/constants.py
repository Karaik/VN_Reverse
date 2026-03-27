from __future__ import annotations

import struct

ADB_MAGIC = b"NBDA"
ADB_MAGIC_U32 = struct.unpack("<I", ADB_MAGIC)[0]
HEADER_STRUCT = struct.Struct("<12I")

OPCODE_NAMES: dict[int, str] = {
    0x0001: "JUMP_RESUME",
    0x0002: "SCENE_LOAD_OR_REUSE",
    0x0003: "SCENE_NEXT",
    0x0005: "SCENE_CALL",
    0x0006: "SCENE_RETURN",
    0x0007: "JUMP_ABS",
    0x0008: "EVAL_EXPR",
    0x0009: "JUMP_IF",
    0x0010: "CMD_0010",
    0x0011: "CMD_0011",
    0x0012: "WAIT_EVENT",
    0x0013: "SET_FLAG_0013",
    0x0100: "MESSAGE_BOX",
    0x0200: "DIALOGUE_LINE",
    0x0300: "CMD_0300",
    0x0301: "CMD_0301",
    0x0303: "CMD_0303",
    0x0305: "CMD_0305",
    0x0400: "CMD_0400",
    0x0402: "CMD_0402",
    0x0404: "CMD_0404",
    0x0410: "CMD_0410",
    0x0412: "CMD_0412",
    0x0420: "CMD_0420",
    0x0422: "CMD_0422",
    0x0500: "CMD_0500",
    0x0600: "TEXT_META",
    0x0601: "TEXT_DIALOGUE",
    0x0602: "TEXT_BEGIN",
    0x0603: "TEXT_END",
    0xFFFF: "END",
}


def opcode_name(opcode: int | None) -> str:
    if opcode is None:
        return "RAW_BYTES"
    return OPCODE_NAMES.get(opcode, f"OP_{opcode:04X}")
