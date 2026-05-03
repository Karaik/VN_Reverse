# SSB 结构

## 当前已确认

- 脚本主载体位于 `game/SCRIPT/`。
- `CODE.SSB` 是索引 / 指令流入口。
- `DATA.SSB` 是脚本数据载体。
- 引擎内对脚本数据使用 `XOR 0xAA` 处理。
- `CODE.SSB` 以 32 位词流组织。
- `CODE.SSB` 中负值词是操作码，非负值词既可能是立即数，也可能是 `DATA.SSB` 的 4 字节对齐偏移。
- `DATA.SSB` 解密后前段存在大量资源名和系统字符串，后段存在剧情文本与说话人名。
- 当前已确认至少一部分操作码直接把 `DATA.SSB` 中的字符串取出用于显示。
- 当前已确认可把“显示相关引用字符串”从全部字符串中单独分离成高优先级文本表。
- 当前已确认可进一步把翻译文本表按用途粗分为：
  - `dialogue`
  - `choice`
  - `system_or_label`
  - `choice_or_label`
- 当前已确认还可以从 `choice_or_label` 中进一步稳定拆出一类 `table_entry_label`。
- 当前已确认还可以从 `dialogue` 中进一步拆出一小批 `table_entry_dialogue`。

## 当前未确认

- `CODE.SSB` 记录的完整字段语义。
- `DATA.SSB` 中文本块、字符串表、控制流数据的精确边界。
- 指令参数和文本操作码的完整映射。
