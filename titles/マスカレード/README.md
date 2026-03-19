# マスカレード（SHSystem）

## 当前主线

这个目录现在只围绕一个目标收敛：

- 为 `Himauri` 的静态文本写回准备最小必要的逆向基础

不再把以下内容作为主线入口：

- 深层 branch / switch 状态机研究
- type7 / type8 的业务细节继续扩张
- 与文本写回无直接关系的研究型统计

这些内容已经从主线文档移出，不再作为默认入口。

## 主入口工具

| 工具 | 作用 |
|---|---|
| `main_unpack.py` | 解包 `Him4/Him5` 资源包 |
| `main_repack.py` | 按清单回封 `Him4/Him5` 资源包 |
| `main_probe.py` | 探测 `Himauri` 头部与脚本流入口 |
| `main_disasm.py` | 导出脚本级反汇编结果 |
| `main_dump_text.py` | 导出当前可见的字面量文本 |
| `regression_test.py` | 回归测试：封包回环 + 脚本抽样验证 |

研究型入口已移到：

- [`research/README.md`](./research/README.md)

主线 CLI 现在只保留常用参数；完整研究参数入口见：

- [`research/main_disasm_full.py`](./research/main_disasm_full.py)
- [`research/main_dump_text_full.py`](./research/main_dump_text_full.py)

## 当前判断

- `Him4/Him5` 解包 / 回封闭环已经足够稳定。
- `Himauri` 目前已经能稳定导出：
  - 头部与流入口
  - 指令级 JSON（带 `offset` / `next_offset`）
  - 当前可见的字面量文本
- 变长文本写回仍未完成。
- 当前障碍不再是“能不能找到文本”，而是“变长写回后如何静态重定位偏移”。

## 关键文档

| 文档 | 说明 |
|---|---|
| [`docs/hxp_结构.md`](./docs/hxp_结构.md) | `Him4/Him5` 结构与回封规则 |
| [`docs/exe_分析.md`](./docs/exe_分析.md) | `SHSystem` 关键读取函数 |
| [`docs/script_格式.md`](./docs/script_格式.md) | 面向文本写回的 `Himauri` 结构说明 |
| [`docs/checklist.md`](./docs/checklist.md) | 当前主线 checklist |
| [`docs/stage_log.md`](./docs/stage_log.md) | 当前阶段交接日志 |

## 现在最常用的命令

### 1. 解包脚本包

```powershell
python .\main_unpack.py .\game\DATA\Masq_scn.hxp .\tmp\scn_unpack --dump-unpacked
```

### 2. 导出脚本级反汇编

```powershell
python .\main_disasm.py .\tmp\scn_unpack\unpacked\sc1_3.bin .\tmp\disasm_sc1_3.json
```

### 3. 导出当前可见文本

```powershell
python .\main_dump_text.py .\tmp\scn_unpack\unpacked\sc1_3.bin .\tmp\text_sc1_3.json
```

### 4. 跑回归

```powershell
python .\regression_test.py
```

## 当前边界

- 允许继续确认与文本载体、文本引用、偏移重定位直接相关的事实。
- 不再把“完整状态机语义”当作默认推进方向。
- 只对白名单里的偏移字段做后续静态写回设计；未确认字段一律不放行。
