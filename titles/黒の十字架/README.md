# 黒の十字架（SAISYS）

## What This Title Can Do Now

当前这套逆向链已经正式支持：

- 反编译 `game/SCRIPT/CODE.SSB` 与 `DATA.SSB`
- 从真实 `AA13` 主显示记录中导出：
  - 正文
  - 显示名
- 从真实 `AC07` UI 记录中导出：
  - 可见文本簇
  - 角色选择簇
  - 选项簇
- 统一导出名字相关入口 `name_related_records.json`
- 把修改后的文本回编回新的：
  - `CODE.SSB`
  - `DATA.SSB`
- 支持 `cp932` 源编码回写
- 支持 `gbk` 目标编码回写
- 支持正文、名字、选项的变长与变短回写

## What The Default Entry Produces

默认入口是：

```powershell
python .\ssb_decompile.py .\game\SCRIPT .\dump_ssb --text-encoding cp932
```

它会生成：

- `.\dump_ssb\script.json`
- `.\dump_ssb\script.ssbsrc`
- `.\dump_ssb\text_entries.json`
- `.\dump_ssb\translation_entries.json`
- `.\dump_ssb\main_display_records.json`
- `.\dump_ssb\ac07_ui_records.json`
- `.\dump_ssb\ac07_visible_clusters.json`
- `.\dump_ssb\ac07_character_selection_records.json`
- `.\dump_ssb\ac07_option_clusters.json`
- `.\dump_ssb\name_related_records.json`

这些输出的意义是：

- `script.json`
  - 正式回编输入
- `translation_entries.json`
  - 正文与 `AA13` 显示名的正式文本入口
- `name_related_records.json`
  - 统一名字相关入口
- `ac07_option_clusters.json`
  - 选项文本入口
- 其余结构化文件
  - 用于检查记录层与回归验证

## Shortest Path For Text Work

如果只想改文本，最短路径是：

1. 反编译脚本
2. 修改以下三类入口之一：
   - `translation_entries.json`
   - `name_related_records.json`
   - `ac07_option_clusters.json`
3. 回编成新的 `CODE.SSB` / `DATA.SSB`

其中：

- 改正文：
  - `translation_entries.json`
  - `usage = "main_display_text"`
- 改 `AA13` 显示名：
  - `translation_entries.json`
  - `usage = "main_display_name"`
- 改统一名字相关文本：
  - `name_related_records.json`
  - `aa13_display_name`
  - `ac07_character_selection_name`
  - `ac07_option_text`
- 改选项：
  - `ac07_option_clusters.json`

## Default Workflow Commands

### 1. Source-Encoding Decompile

```powershell
python .\ssb_decompile.py .\game\SCRIPT .\dump_ssb --text-encoding cp932
```

- goal:
  - 把原始脚本目录导出成可读、可编辑、可回编的正式中间表示。
- input:
  - `.\game\SCRIPT\CODE.SSB`
  - `.\game\SCRIPT\DATA.SSB`
- output:
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\translation_entries.json`
  - `.\dump_ssb\name_related_records.json`
  - `.\dump_ssb\ac07_option_clusters.json`
  - 以及其他结构化辅助文件
- why the output matters:
  - 这是后续所有文本修改与回编的正式起点。

### 2. Source-Encoding Compile For Main Text And AA13 Names

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- goal:
  - 把 `translation_entries.json` 里的正文和 `AA13` 显示名写回新脚本。
- input:
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\translation_entries.json`
- output:
  - `.\rebuild_ssb\CODE.SSB`
  - `.\rebuild_ssb\DATA.SSB`
- why the output matters:
  - 得到带有文本改动的新脚本文件。

### 3. Source-Encoding Compile For Unified Name-Related Records

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --name-related-records .\dump_ssb\name_related_records.json --text-encoding cp932
```

- goal:
  - 统一回写显示名、角色选择名字等名字相关文本。
- input:
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\name_related_records.json`
- output:
  - `.\rebuild_ssb\CODE.SSB`
  - `.\rebuild_ssb\DATA.SSB`
- why the output matters:
  - 可以不分散地处理名字相关文本入口。

### 4. Source-Encoding Compile For Options

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --ac07-visible-clusters .\dump_ssb\ac07_option_clusters.json --text-encoding cp932
```

- goal:
  - 把 `AC07` 选项文本写回新脚本。
- input:
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\ac07_option_clusters.json`
- output:
  - `.\rebuild_ssb\CODE.SSB`
  - `.\rebuild_ssb\DATA.SSB`
- why the output matters:
  - 选项文本已经进入正式回写链，可以单独修改和回编。

### 5. Batch Decompile

```powershell
python .\ssb_decompile.py .\game .\dump_batch --batch --text-encoding cp932
```

- goal:
  - 批量导出 `game/` 下所有脚本目录。
- input:
  - `.\game\`
- output:
  - `.\dump_batch\`
- why the output matters:
  - 适合一次性处理整批脚本目录。

### 6. Batch Compile

```powershell
python .\ssb_compile.py .\dump_batch .\rebuild_batch --batch --use-default-text-entries --text-encoding cp932
```

- goal:
  - 批量把整批 `script.json` 回编回脚本文件。
- input:
  - `.\dump_batch\`
  - 每个 `script.json` 同级的 `translation_entries.json`
- output:
  - `.\rebuild_batch\`
- why the output matters:
  - 适合批量回写多个脚本目录。

### 7. Target-Encoding Compile

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb_gbk --text-entries .\dump_ssb\translation_entries.json --text-encoding gbk
```

- goal:
  - 按目标编码 `gbk` 回写文本。
- input:
  - `.\dump_ssb\script.json`
  - `.\dump_ssb\translation_entries.json`
- output:
  - `.\rebuild_ssb_gbk\CODE.SSB`
  - `.\rebuild_ssb_gbk\DATA.SSB`
- why the output matters:
  - 目标编码写回链已经正式可用。

### 8. Target-Encoding Re-Decompile Verification

```powershell
python .\ssb_decompile.py .\rebuild_ssb_gbk .\rebuild_dump_gbk --text-encoding gbk
```

- goal:
  - 验证目标编码回写后的脚本仍可再次反编译。
- input:
  - `.\rebuild_ssb_gbk\CODE.SSB`
  - `.\rebuild_ssb_gbk\DATA.SSB`
- output:
  - `.\rebuild_dump_gbk\`
- why the output matters:
  - 证明 `gbk` 目标编码写回后仍可正确读回。

### 9. Specified Text Entry Patch Example

```powershell
@'
import json
from pathlib import Path

path = Path(r".\dump_ssb\translation_entries.json")
doc = json.loads(path.read_text(encoding="utf-8"))

for entry in doc["entries"]:
    if entry["usage"] == "main_display_text" and entry["storage_bytes"] >= len("試験".encode("cp932")) + 1:
        entry["text"] = "試験"
        break

path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- goal:
  - 修改一条正文文本并回编。
- input:
  - `.\dump_ssb\translation_entries.json`
  - `.\dump_ssb\script.json`
- output:
  - `.\rebuild_ssb\CODE.SSB`
  - `.\rebuild_ssb\DATA.SSB`
- why the output matters:
  - 给出一条完整可执行的指定文本回写链。

### 10. Variable-Length Text Patch Example

```powershell
@'
import json
from pathlib import Path

path = Path(r".\dump_ssb\translation_entries.json")
doc = json.loads(path.read_text(encoding="utf-8"))

for entry in doc["entries"]:
    if entry["usage"] == "main_display_text" and entry["storage_bytes"] < len("試験追加".encode("cp932")) + 1:
        entry["text"] = "試験追加"
        break

path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- goal:
  - 修改一条需要变长回写的正文文本并回编。
- input:
  - `.\dump_ssb\translation_entries.json`
  - `.\dump_ssb\script.json`
- output:
  - `.\rebuild_ssb\CODE.SSB`
  - `.\rebuild_ssb\DATA.SSB`
- why the output matters:
  - 给出一条完整可执行的变长文本回写链。

## Current Verified Facts

当前正式验证已经覆盖并通过：

- unchanged roundtrip
  - `CODE.SSB`
  - `DATA.SSB`
- batch decompile
- batch compile
- `AA13` 正文回写
- `AA13` 正文变短回写
- `AA13` 正文变长回写
- `AA13` 显示名回写
- `AA13` 显示名变短回写
- `AA13` 显示名变长回写
- `AC07` 选项回写
- `AC07` 选项变短回写
- `AC07` 选项变长回写
- `AC07` 角色选择簇回写
- `name_related_records` 统一回写
- `name_related_records` 名字变短回写
- `name_related_records` 名字变长回写
- `gbk` 目标编码回写
- `gbk` 目标编码回写后的再次反编译验证

总验证入口：

```powershell
python .\regression_test.py
```

## Current Unconfirmed / Unfinished Boundaries

当前还没有正式确认：

- `8351 / 8309` 前置链的完整业务语义
- 全部 `AC07` UI 字段语义
- 全部 VM opcode 的完整语义
- 资源层独立封包 / 回封

## Docs Links

- [`docs/ssb_结构.md`](./docs/ssb_结构.md)
- [`docs/ssb_用法.md`](./docs/ssb_用法.md)
- [`docs/ssb_验证.md`](./docs/ssb_验证.md)
