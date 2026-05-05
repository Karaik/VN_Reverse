# SSB 用法

当前正式脚本入口：

- `ssb_decompile.py`
- `ssb_compile.py`

以下命令均以当前 title 根目录为基准执行。

## `ssb_decompile.py`

### 默认 `cp932` 反编译

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
- 适用场景：
  - 导出正式中间表示
  - 审查词流
  - 进入正式文本修改链

### 目标编码回写后的再次反编译

```powershell
python .\ssb_decompile.py .\rebuild_ssb_gbk .\rebuild_dump_gbk --text-encoding gbk
```

- 输入：
  - `rebuild_ssb_gbk\CODE.SSB`
  - `rebuild_ssb_gbk\DATA.SSB`
- 输出：
  - `rebuild_dump_gbk\` 下的四类正式导出
- 适用场景：
  - 校验目标编码写回结果仍可再次反编译

## `ssb_compile.py`

### 默认 `cp932` 编译

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
  - 按源编码路径回写脚本文本

### 指定回写编码（GBK 示例）

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
  - 把文本按目标编码写回

## 文本表修改建议

- 默认修改入口是 `translation_entries.json`。
- 当前正式筛选条件优先看结构字段：
  - `category`
  - `storage_bytes`
  - `main_display_reference_count`
  - `text_reference_count`
- 不建议再依赖旧的 `dialogue / choice / choice_or_label` 口径做脚本批处理，因为当前 title 还没有把这几类语义完整建模稳定。
