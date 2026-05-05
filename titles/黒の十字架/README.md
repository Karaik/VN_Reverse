# 黒の十字架（SAISYS）

## 主入口

这个 title 当前正式完成的是 `SSB` 脚本链：

- 反编译 `CODE.SSB` / `DATA.SSB`
- 导出正式中间表示与文本表
- 修改文本后回编
- 支持 `cp932` 原编码回写
- 支持指定目标编码回写（如 `gbk`）
- 支持变长文本回写

当前 title 根目录下的正式入口只有三条：

| 入口 | 作用 |
|---|---|
| `ssb_decompile.py` | 把 `SCRIPT/` 导出为正式中间表示 |
| `ssb_compile.py` | 把 `script.json` 与文本表回编为新的 `CODE.SSB` / `DATA.SSB` |
| `regression_test.py` | 跑正式总验证 |

## 默认工作流

以下命令均以当前 title 根目录为基准执行。

### 1. 反编译脚本

```powershell
python .\ssb_decompile.py .\game\SCRIPT .\dump_ssb --text-encoding cp932
```

- 目标：导出正式可编辑中间表示
- 输入：`.\game\SCRIPT\CODE.SSB`、`.\game\SCRIPT\DATA.SSB`
- 输出：
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\script.ssbsrc`
  - `.\dump_ssb\text_entries.json`
  - `.\dump_ssb\translation_entries.json`
- 输出意义：
  - `script.json` 是正式回编输入
  - `translation_entries.json` 是默认文本修改入口

### 2. 修改文本后回编

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- 目标：把文本修改回写到新的脚本结果
- 输入：`script.json`、`translation_entries.json`
- 输出：`.\rebuild_ssb\CODE.SSB`、`.\rebuild_ssb\DATA.SSB`
- 输出意义：得到新的脚本二进制结果

### 3. 指定目标编码回写

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb_gbk --text-entries .\dump_ssb\translation_entries.json --text-encoding gbk
```

- 目标：把文本按目标编码写回
- 输入：`script.json`、`translation_entries.json`
- 输出：`.\rebuild_ssb_gbk\CODE.SSB`、`.\rebuild_ssb_gbk\DATA.SSB`
- 输出意义：验证目标编码路径而不是只做原样回填

必要时按相同编码再次反编译：

```powershell
python .\ssb_decompile.py .\rebuild_ssb_gbk .\rebuild_dump_gbk --text-encoding gbk
```

## 文本修改示例

### 就地回写示例

```powershell
@'
import json
from pathlib import Path

path = Path(r".\dump_ssb\translation_entries.json")
doc = json.loads(path.read_text(encoding="utf-8"))

for entry in doc["entries"]:
    if entry["category"] == "jp_text" and entry["storage_bytes"] >= 6:
        entry["text"] = "試験"
        break

path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

### 变长回写示例

```powershell
@'
import json
from pathlib import Path

path = Path(r".\dump_ssb\translation_entries.json")
doc = json.loads(path.read_text(encoding="utf-8"))

for entry in doc["entries"]:
    if entry["category"] == "jp_text" and entry["storage_bytes"] < len("試験追加".encode("cp932")) + 1:
        entry["text"] = "試験追加"
        break

path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

## 总验证

```powershell
python .\regression_test.py
```

当前总验证覆盖：

- `CODE.SSB` unchanged roundtrip
- `DATA.SSB` unchanged roundtrip
- 所有正式引用文本零漏提进入 `translation_entries`
- 姓名样本可写回并再次反编译恢复
- `cp932` 就地回写
- `cp932` 变长回写
- `gbk` 目标编码回写
- 目标编码写回后再次反编译恢复文本

## 当前已确认

- `CODE.SSB` / `DATA.SSB` 已可正式反编译
- 所有被脚本正式引用的 `jp_text` / `text` 条目已进入 `translation_entries`
- 姓名样本已能导出、写回并再次反编译恢复
- `cp932` 路径下的文本回写已打通
- `gbk` 目标编码写回已打通
- 变长文本回写已打通

## 当前未确认

- `CODE.SSB` 全部 opcode 的完整语义
- 说话人、正文、选项、标签的完整结构化建模
- 资源层独立回封

## 文档

- [`docs/ssb_结构.md`](./docs/ssb_结构.md)
- [`docs/ssb_用法.md`](./docs/ssb_用法.md)
- [`docs/ssb_验证.md`](./docs/ssb_验证.md)
