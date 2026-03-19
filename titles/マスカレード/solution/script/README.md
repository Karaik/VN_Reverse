# Himauri 脚本层

## 当前目标

当前目录只保留与下列目标直接相关的脚本层实现：

- 文本载体识别
- 文本定位
- 变长写回前的偏移重定位准备

历史研究型说明已从主线说明中移出，不再作为默认入口。

## 主线模块

- `probe.py`
  - 导出 `Himauri` 头部、额外字符串、流入口
- `reader.py`
  - 基础读取器
- `himauri.py`
  - 载体头部解析与脚本流起点识别
- `expression.py`
  - 表达式机
  - 当前只继续保留与字符串索引、常量折叠、写回副作用有关的能力
- `strings.py`
  - `sub_4021F0` 字符串参数解析
- `argpack.py`
  - `sub_404880` 参数包解析
- `opcodes.py`
  - opcode / handler 映射
- `disasm.py`
  - 导出脚本级 JSON
- `text.py`
  - 导出字面量文本与已解引用文本
- `model.py`
  - 结构模型

## 研究型模块

以下模块仍保留，但不再作为主线入口：

- `branch_audit.py`
- `branch_overview.py`
- `switch_audit.py`
- `switch_seed_sweep.py`
- `var16_writers.py`

对应入口脚本已移到：

- [`../../research/README.md`](../../research/README.md)
- [`../../research/main_disasm_full.py`](../../research/main_disasm_full.py)
- [`../../research/main_dump_text_full.py`](../../research/main_dump_text_full.py)

## 当前判断

- 现有脚本层已经足够继续做文本载体分类与偏移白名单整理。
- 当前主线不是继续扩张状态机，而是为最小静态 writer 补结构事实。

## 主线 Checklist

- [x] 可稳定导出头部与流入口
- [x] 可稳定导出脚本级 JSON
- [x] 可稳定导出当前可见文本
- [ ] 还未完成偏移重定位白名单
- [ ] 还未完成最小静态 writer
