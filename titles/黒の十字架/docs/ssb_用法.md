# SSB 用法

当前正式脚本入口：

- `ssb_decompile.py`
- `ssb_compile.py`

## `ssb_decompile.py`

### 默认 `cp932` 反编译

```powershell
python .\ssb_decompile.py .\game\SCRIPT .\dump_ssb --text-encoding cp932
```

- 输入
  - 包含 `CODE.SSB` / `DATA.SSB` 的脚本目录
- 输出
  - `script.json`
  - `script.ssbsrc`
  - `text_entries.json`
  - `translation_entries.json`
- 适用场景
  - 想导出正式中间表示
  - 想审查脚本词流
  - 想进入正式文本修改链

### 目标编码回写后的反编译校验

```powershell
python .\ssb_decompile.py .\rebuild_ssb_gbk .\rebuild_dump_gbk --text-encoding gbk
```

- 输入
  - `.\rebuild_ssb_gbk\CODE.SSB`
  - `.\rebuild_ssb_gbk\DATA.SSB`
- 输出
  - `rebuild_dump_gbk\` 下的四类正式导出
- 适用场景
  - 校验 `gbk` 写回后仍可再次反编译

## `ssb_compile.py`

### 默认 `cp932` 编译

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- 输入
  - `script.json`
  - `translation_entries.json`
- 输出
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景
  - 按源编码路径回写日文文本

### 指定回写编码（GBK 示例）

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb_gbk --text-entries .\dump_ssb\translation_entries.json --text-encoding gbk
```

- 输入
  - `script.json`
  - `translation_entries.json`
- 输出
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景
  - 把日文脚本改文后按 `gbk` 目标编码写回

### 指定日文文本回写示例

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

### 变长日文文本回写示例

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
