# TE_V2 脚本用法

本文只写正式入口、参数、输入输出和适用场景。

## `tev2_decompile.py`

```powershell
python .\tev2_decompile.py <input> <output> --batch --mode decoded --text-encoding cp932
```

适用场景：
从资源树批量导出正式可编辑文本。

输入：
- 单个 `.scr/.dat`
- 或解包后的 `files\` 资源树

输出：
- `decoded` 模式输出 JSON
- `decoded-binary` 模式输出解码后二进制
- `raw` 模式输出容器层 JSON
- `raw-binary` 模式输出原始字节

正式参数：
- `--batch`
- `--mode decoded|raw|decoded-binary|raw-binary`
- `--text-encoding cp932|gbk|...`

正式示例：

```powershell
python .\tev2_decompile.py .\pak0_game00\files .\text_dump --batch --mode decoded --text-encoding cp932
```

## `tev2_compile.py`

```powershell
python .\tev2_compile.py <input> <output> --batch --mode decoded --text-encoding gbk
```

适用场景：
把 JSON 文本批量回编成正式资源。

输入：
- `decoded` 模式输入编辑后的 JSON
- `decoded-binary` 模式输入解码后二进制，且必须带 `--source`
- `raw` / `raw-binary` 模式输入原始导出结果

输出：
- `.scr`
- `.dat`
- 或对应的二进制重建结果

正式参数：
- `--batch`
- `--mode decoded|raw|decoded-binary|raw-binary`
- `--text-encoding cp932|gbk|...`
- `--source <files_root>` 仅 `decoded-binary` 批量模式需要

指定目标编码回写示例：

```powershell
python .\tev2_compile.py .\text_dump .\text_rebuild --batch --mode decoded --text-encoding gbk
```

## 文本载体

正式文本载体：
- `script/*.scr`
- `data/BtText.dat`
- `data/tiName*.dat`
- `data/tiBalloon*.dat`

当前脚本正式覆盖范围：
- `game00.dat`
- `game01.dat`

当前未发现脚本载体的资源包：
- `game02.dat`
- `game03.dat`
- `game04.dat`
