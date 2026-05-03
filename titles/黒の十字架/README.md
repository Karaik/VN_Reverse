# 黒の十字架（SAISYS）

## 工具说明

| 工具 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `ssb_decompile.py` | 反编译 `CODE.SSB` / `DATA.SSB`，导出 `json` 与 `ssbsrc` 及文本表 | `SCRIPT/` 目录 | `script.json` + `script.ssbsrc` + `text_entries.json` + `translation_entries.json` |
| `ssb_compile.py` | 编译 `script.json`，支持从文本表回写 | `script.json` + 可选文本表 | `CODE.SSB` + `DATA.SSB` |
| `regression_test.py` | 回归测试（unchanged roundtrip、日文回写、变长回写、目标编码写回） | `game/SCRIPT/` | `PASS` 或失败信息 |

## 文档入口

| 文档 | 说明 |
|---|---|
| [`README.md`](./README.md) | 工具总览与命令 |
| [`docs/ssb_结构.md`](./docs/ssb_结构.md) | `CODE.SSB` / `DATA.SSB` 结构与当前结论 |
| [`docs/ssb_用法.md`](./docs/ssb_用法.md) | 正式脚本入口、参数、编码写回、文本表示 |
| [`docs/ssb_验证.md`](./docs/ssb_验证.md) | 当前脚本链验证覆盖与未覆盖边界 |

## 用法

以下命令均以当前 title 根目录为基准执行。

### 1) 脚本反编译（默认 `cp932`）

```powershell
python .\ssb_decompile.py .\game\SCRIPT .\dump_ssb --text-encoding cp932
```

- 目标
  - 把 `CODE.SSB` / `DATA.SSB` 导出成正式可编辑中间表示
- 输入
  - `.\game\SCRIPT\CODE.SSB`
  - `.\game\SCRIPT\DATA.SSB`
- 输出
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\script.ssbsrc`
  - `.\dump_ssb\text_entries.json`
  - `.\dump_ssb\translation_entries.json`
- 输出意义
  - `script.json` 是正式回编输入
  - `translation_entries.json` 是默认文本修改入口

### 2) 脚本编译（默认 `cp932`）

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- 目标
  - 按当前源编码路径回写脚本文本
- 输入
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\translation_entries.json`
- 输出
  - `.\rebuild_ssb\CODE.SSB`
  - `.\rebuild_ssb\DATA.SSB`
- 输出意义
  - 这是按 `cp932` 路径写回后的新脚本结果

### 3) 指定回写编码（GBK 示例）

源脚本文本为日文编码（`win-31j/sjis/cp932`）时，回写可显式指定目标编码：

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb_gbk --text-entries .\dump_ssb\translation_entries.json --text-encoding gbk
```

- 目标
  - 把文本按 `gbk` 目标编码写回新的 `DATA.SSB`
- 输入
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\translation_entries.json`
- 输出
  - `.\rebuild_ssb_gbk\CODE.SSB`
  - `.\rebuild_ssb_gbk\DATA.SSB`
- 输出意义
  - 这是目标编码写回结果，不只是源编码原样回填

必要时按相同编码再次反编译校验文本：

```powershell
python .\ssb_decompile.py .\rebuild_ssb_gbk .\rebuild_dump_gbk --text-encoding gbk
```

- 目标
  - 校验 `gbk` 写回后的脚本仍可再次反编译
- 输入
  - `.\rebuild_ssb_gbk\CODE.SSB`
  - `.\rebuild_ssb_gbk\DATA.SSB`
- 输出
  - `.\rebuild_dump_gbk\script.json`
  - `.\rebuild_dump_gbk\script.ssbsrc`
  - `.\rebuild_dump_gbk\text_entries.json`
  - `.\rebuild_dump_gbk\translation_entries.json`
- 输出意义
  - 这是目标编码写回链可再次反序列化的直接证据

### 4) 指定日文文本回写示例

```powershell
@'
import json
from pathlib import Path

path = Path(r".\dump_ssb\translation_entries.json")
doc = json.loads(path.read_text(encoding="utf-8"))

for entry in doc["entries"]:
    if entry["usage"] in {"dialogue", "choice", "choice_or_label"} and entry["category"] == "jp_text" and entry["storage_bytes"] >= 6:
        entry["text"] = "試験"
        break

path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

### 5) 变长日文文本回写示例

```powershell
@'
import json
from pathlib import Path

path = Path(r".\dump_ssb\translation_entries.json")
doc = json.loads(path.read_text(encoding="utf-8"))

for entry in doc["entries"]:
    if entry["usage"] in {"dialogue", "choice", "choice_or_label"} and entry["category"] == "jp_text" and entry["storage_bytes"] < len("試験追加".encode("cp932")) + 1:
        entry["text"] = "試験追加"
        break

path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

### 6) 回归测试

```powershell
python .\regression_test.py
```

覆盖项：

- `CODE.SSB` unchanged roundtrip
- `DATA.SSB` unchanged roundtrip
- `cp932` 路径下的日文文本就地回写
- `cp932` 路径下的变长日文文本追加回写
- `gbk` 目标编码写回
- 目标编码写回后再次反编译恢复文本

## 当前已验证结论

- `CODE.SSB` / `DATA.SSB` 已可正式反编译
- `cp932` 路径下的文本回写已打通
- `gbk` 目标编码写回已打通
- 日文文本 `試験` 已实测可写回
- 变长日文文本 `試験追加` 已实测可写回
- 目标编码写回后再次反编译仍能恢复文本

## 当前未确认 / 未完成

- 还没有完整剧情文本语义级回编
- 说话人和正文还没建成正式配对模型
- 资源层独立回封还没完成
