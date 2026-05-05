# SSB 用法

## 正式入口

- `ssb_decompile.py`
- `ssb_compile.py`
- `regression_test.py`

以下命令均以当前 title 根目录为基准执行。

## `ssb_decompile.py`

### 单目录反编译

```powershell
python .\ssb_decompile.py .\game\SCRIPT .\dump_ssb --text-encoding cp932
```

- 输入：
  - `SCRIPT/` 目录
- 输出：
  - `script.json`
  - `script.ssbsrc`
  - `text_entries.json`
  - `translation_entries.json`
  - `main_display_records.json`
  - `ac07_ui_records.json`
  - `ac07_visible_clusters.json`
  - `ac07_character_selection_records.json`
  - `ac07_option_clusters.json`
  - `name_related_records.json`
- 适用场景：
  - 导出正式中间表示
  - 进入正文/显示名修改链
  - 进入统一名字相关修改链
  - 检查 `AC07` 角色选择簇与选项簇

### 批量反编译

```powershell
python .\ssb_decompile.py .\game .\dump_batch --batch --text-encoding cp932
```

- 输入：
  - `game/` 根目录
- 输出：
  - `dump_batch/` 下按原目录镜像输出
- 适用场景：
  - 一次性导出整批脚本目录

## `ssb_compile.py`

### 回写正文/显示名

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --text-entries .\dump_ssb\translation_entries.json --text-encoding cp932
```

- 输入：
  - `script.json`
  - `translation_entries.json`
- 输出：
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景：
  - 回写 `AA13` 正文与显示名

### 回写统一名字相关记录

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --name-related-records .\dump_ssb\name_related_records.json --text-encoding cp932
```

- 输入：
  - `script.json`
  - `name_related_records.json`
- 输出：
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景：
  - 统一回写 `AA13` 显示名、`AC07` 角色选择名字、`AC07` 选项文本

### 回写 `AC07` 角色选择簇

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --ac07-character-selection .\dump_ssb\ac07_character_selection_records.json --text-encoding cp932
```

- 输入：
  - `script.json`
  - `ac07_character_selection_records.json`
- 输出：
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景：
  - 单独回写 `AC07` 角色选择名字

### 回写 `AC07` 选项簇

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb --ac07-visible-clusters .\dump_ssb\ac07_option_clusters.json --text-encoding cp932
```

- 输入：
  - `script.json`
  - `ac07_option_clusters.json`
- 输出：
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景：
  - 单独回写 `AC07` 选项文本

### 批量回编

```powershell
python .\ssb_compile.py .\dump_batch .\rebuild_batch --batch --use-default-text-entries --text-encoding cp932
```

- 输入：
  - `dump_batch/`
  - 每个 `script.json` 同级的 `translation_entries.json`
- 输出：
  - `rebuild_batch/` 下按原目录镜像输出
- 适用场景：
  - 批量回编整批脚本目录

### 指定目标编码回写

```powershell
python .\ssb_compile.py .\dump_ssb\script.json .\rebuild_ssb_gbk --text-entries .\dump_ssb\translation_entries.json --text-encoding gbk
```

- 输入：
  - `script.json`
  - `translation_entries.json`
- 输出：
  - `CODE.SSB`
  - `DATA.SSB`
- 适用场景：
  - 按指定目标编码回写正文

## 正式文本入口

### `translation_entries.json`

当前正式 `usage`：

- `main_display_text`
- `main_display_name`

### `name_related_records.json`

当前正式 `record_kind`：

- `aa13_display_name`
- `ac07_character_selection_name`
- `ac07_option_text`

## 当前边界

- `translation_entries.json` 当前只承载 `AA13` 正文与显示名
- `name_related_records.json` 当前承载统一的人名相关入口
- `ac07_character_selection_records.json` 与 `ac07_option_clusters.json` 当前用于单独检查或单独回写
- 前置视觉链保留在 `main_display_records.json` 中，但当前不作为正式翻译入口
