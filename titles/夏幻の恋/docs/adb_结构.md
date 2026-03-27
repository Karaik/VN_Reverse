# ADB 结构

本页只保留 `NBDA` 脚本格式本身，以及脚本资源在资源树中的恢复依据。

## 文件布局

- 头部固定 `0x30` 字节（12 个 `u32`，小端）
- `header[0] = 0x4144424E`（ASCII: `NBDA`）
- `header[1] = 0x00010000`
- `header[4] = section0_size`
- `header[5] = index_count`
- `header[6] = section1_size`

总长度关系：

`0x30 + section0_size + index_count*4 + section1_size + tail_size`

## 头字段

| 偏移 | 类型 | 名称 | 说明 |
|---|---|---|---|
| `0x00` | `u32` | `magic` | 固定 `NBDA` |
| `0x04` | `u32` | `version` | 固定 `0x00010000` |
| `0x08` | `u32` | `unk_08` | 未确认 |
| `0x0C` | `u32` | `unk_0C` | 未确认 |
| `0x10` | `u32` | `section0_size` | section0 字节数 |
| `0x14` | `u32` | `index_count` | 索引数量 |
| `0x18` | `u32` | `section1_size` | section1 字节数 |
| `0x1C` | `u32` | `unk_1C` | 未确认 |
| `0x20` | `u32` | `unk_20` | 未确认 |
| `0x24` | `u32` | `unk_24` | 未确认 |
| `0x28` | `u32` | `unk_28` | 未确认 |
| `0x2C` | `u32` | `unk_2C` | 未确认 |

## 数据区

1. `section0`
2. `index_u32[]`
3. `section1`
4. `tail`

## 索引与槽位模型

- `index_u32[i]` 指向 `section1` 内槽位偏移
- 多个索引可以指向同一槽位
- `entries[]` 保存执行序列
- `slots[]` 保存去重后的槽位数据

## 文本模型

### `0x0601` 正文槽位

| 顺序 | 类型 | 字段 | 说明 |
|---|---|---|---|
| 1 | `u16` | `opcode` | 固定 `0x0601` |
| 2 | `u16` | `speaker_u16` | 当前保留原字段值，稳定语义尚未完全确认 |
| 3 | `u16` | `text_len_u16` | UTF-16 code unit 数 |
| 4 | `u16[text_len]` | `text` | 正文内容 |
| 5 | `u16` | `terminator` | 固定 `0x0000` |
| 6 | `u16[]` | `suffix_words` | 后缀参数 |

### `0x0600` 说话人名槽位

| 顺序 | 类型 | 字段 | 说明 |
|---|---|---|---|
| 1 | `u16` | `opcode` | 固定 `0x0600` |
| 2 | `u16` | `kind_u16` | 当前样本稳定为 `0x0000` |
| 3 | `u16` | `name_len_plus_terminator` | 名字长度加结尾 `0x0000` |
| 4 | `u16[name_len]` | `speaker_name` | 说话人名字 |
| 5 | `u16` | `terminator` | 固定 `0x0000` |

## 编码

- 文本编码：UTF-16LE
- 可编辑文本长度字段按 UTF-16 code unit 计数
- `.adv` 名称在回到脚本资源时会规范化为 `.adb`

## 命名恢复依据

脚本资源名字恢复当前主要来自：

- 运行时路径中的明文脚本名
- 系统配置表中的脚本路径
- 资源树中已恢复表项对脚本名的反向引用

当前已确认的例子：

- `adv\logo.adb`
- `adv\SNR.adb`
- `system\save\save.adb`
- `system\window\menu.adb`

## 目录恢复依据

- 剧情脚本归属 `adv/`
- 未恢复原名但已确认是剧情脚本的条目归属 `adv/待补原名/`
- 系统脚本归属 `system/...`
- 未恢复原名但已确认是系统脚本的条目归属 `system/scripts/待补原名/`

## 已确认结论

- 剧情脚本可以从恢复后的资源树 `adv/` 直接进入脚本链
- `0x0600` 与 `0x0601` 已经可以在正式模型中建立关联
- `JSON` 与 `ADBSRC` 都能回编

## 未确认结论

- `speaker_u16` 的稳定语义仍未完全确认
- 是否还存在非 `0x0600` 的名字来源，仍未完全排除
