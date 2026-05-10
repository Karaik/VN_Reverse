# TE_V2 脚本结构

本文只写格式、字段、恢复依据、已确认和未确认结论。

## 分层

- 外层容器层
  - `*.scr`
  - `BtText.dat`
- 内层文本层
  - `SCR` 解码后五段结构
  - `TXT0` 字符串池

## `BtText.dat`

已确认头部：
- `TSCR`
- `u32 total_size`
- `u32 raw_entry_count`
- `u32 key_seed`

已确认结构：
- 头后主体经 `mode-5 word-swap xor` 解码
- 解码后根容器为 `TUTA`
- `TUTA` 内含 `TXT0`
- `TXT0` 为偏移表 + 字符串池

已确认字段：
- `TXT0.size`
- `TXT0.entry_count`
- `TXT0.relative_offsets[]`

## `*.scr`

已确认头部：
- `magic = SCR `
- `u32 version`
- `u32 codec_mode = 2`
- `u32 key_seed`
- `u32 decoded_payload_size`

已确认结构：
- 头后主体经 `mode-2` 解码
- 解码后主体可稳定拆成五段
  - `sec1`
  - `sec2`
  - `sec3`
  - `sec4`
  - `sec5`

已确认恢复依据：
- `sec3` 命令流中存在稳定的字符串槽位
- 正式提取逻辑基于命令槽位结构，不依赖实际游戏文本匹配
- 所有已成功解码的非 ASCII 字符串槽位都必须进入正式导出链

已确认文本类别：
- `name`
- `dialogue`
- `text`
- `choice`
- `system`

已确认目录归属：
- `script/*.scr`

## 名字恢复依据

- 主角名和角色名当前都走 `.scr` 正式链
- 不依赖 `tiNameSp.dat` 作为名字主链

## 已确认结论

- `game00.dat` 与 `game01.dat` 内存在正式脚本载体
- `game02.dat ~ game04.dat` 当前未发现 `script/*.scr`
- `SCR` 非 ASCII 文本槽位零漏提校验已在本地通过
- `SCR` 全量回写快验已在本地通过

## 未确认结论

- 完整 VM opcode / operand 语义
- `Script.dat` 是否为独立主脚本包
