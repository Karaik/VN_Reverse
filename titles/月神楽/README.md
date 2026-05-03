# 月神楽（Studio_e-go_V2）

当前 title 按逆向项目处理，当前正式目标是：

- 导出可编辑文本
- 支持文本回写
- 支持长文本扩容与短文本缩短
- 用正式验证确认这些链路可重复通过

当前正式文本模型只包含**结构化反序列化确认过的可汉化文本**。  
不再把正则扫到的伪候选当成正式文本。

## 当前能做什么

- `tiNameSp.dat` / `tiBalloonSp.dat` 这类固定表可反编译、回编、`gbk` 写回
- `BtText.dat` 可反编译、回编、可变长回写、`gbk` 写回
- `*.scr` 可结构化导出文本候选、回写、扩容、缩短

## 文本最短路径

如果你只是要做汉化文本处理，最短路径是：

1. 解出资源
2. 导出文本
3. 修改 JSON
4. 回编
5. 跑验证

## 正式入口

### 1. 解出资源

```powershell
python .\tev2_unpack.py .\game\game00.dat .\pak0_game00
```

输入：
- `.\game\game00.dat`

输出：
- `.\pak0_game00\manifest.json`
- `.\pak0_game00\files\`

意义：
- 提供正式文本链所需的 `data/` 和 `script/` 资源树

### 2. 导出固定表文本

```powershell
python .\tev2_decompile.py .\pak0_game00\files\data\tiNameSp.dat .\table_dump\tiNameSp.json --text-encoding cp932
```

### 3. 回编固定表文本

```powershell
python .\tev2_compile.py .\table_dump\tiNameSp.json .\table_rebuild\tiNameSp.dat --text-encoding cp932
```

### 4. 导出 `BtText.dat`

```powershell
python .\tev2_decompile.py .\pak0_game00\files\data\BtText.dat .\bttext_probe\BtText.json --text-encoding cp932
```

### 5. 回编 `BtText.dat`

```powershell
python .\tev2_compile.py .\bttext_probe\BtText.json .\bttext_probe\BtText_rebuild.dat --text-encoding cp932
```

### 6. 导出 `.scr` 文本候选

```powershell
python .\tev2_decompile.py .\pak0_game00\files\script\start.scr .\scr_probe\start.json --text-encoding cp932
```

输出意义：
- 当前只导出结构化反序列化确认过的 `.scr` 文本节点

### 7. 回编 `.scr`

```powershell
python .\tev2_compile.py .\scr_probe\start.json .\scr_probe\start_patched.scr --text-encoding cp932
```

### 8. 修改单条文本

```powershell
python .\tev2_patch_text.py .\scr_probe\start.json .\scr_probe\start_patched.json --entry-index 0 --text "TEST OVER"
```

### 9. 长度检查

```powershell
python .\tev2_check_text_fit.py .\scr_probe\start.json --entry-offset 361 --text "終幕" --text-encoding cp932
python .\tev2_fit_report.py .\scr_probe\start.json .\scr_probe\start_fit_report.json --extra-bytes 4 --text-encoding cp932
```

## 正式验证

### 默认总回归

```powershell
python .\regression_test.py
```

覆盖：
- 固定表 roundtrip
- `BtText.dat` roundtrip / 可变长 / `gbk`
- `.scr` 文本导出 / 回写 / 长文本扩容

### 重型验证入口

全脚本正文首/末条长文本：

```powershell
python .\tev2_all_scripts_edge_regression.py --chunk-index 0 --chunk-count 3
python .\tev2_all_scripts_edge_regression.py --chunk-index 1 --chunk-count 3
python .\tev2_all_scripts_edge_regression.py --chunk-index 2 --chunk-count 3
```

混合型脚本正文首/末条长文本：

```powershell
python .\tev2_mixed_scripts_edge_regression.py
```

全脚本正文分层点位长文本：

```powershell
python .\tev2_all_scripts_stratified_regression.py --chunk-index <0-based> --chunk-count <N> [--script-start <i>] [--script-end <j>]
```

全脚本正文单条长文本：

```powershell
python .\tev2_all_scripts_single_entry_regression.py --chunk-index <0-based> --chunk-count <N> [--script-start <i>] [--script-end <j>] [--entry-start <a>] [--entry-end <b>]
```

全脚本正文单条短文本：

```powershell
python .\tev2_all_scripts_single_entry_short_regression.py --chunk-index <0-based> --chunk-count <N> [--script-start <i>] [--script-end <j>] [--entry-start <a>] [--entry-end <b>]
```

## 当前边界

- 当前目标是“文本汉化链可用”，不是完整 `.scr` opcode / operand 语义恢复
- `Script.dat` 仍未正式收敛成独立总脚本包结论
- 当前正式文本模型只包含结构化确认过的文本节点

## 文档

- [docs/README.md](D:/Code/VN_Reverse/titles/月神楽/docs/README.md)
- [docs/tev2_script_结构.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_script_结构.md)
- [docs/tev2_script_用法.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_script_用法.md)
- [docs/tev2_script_验证.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_script_验证.md)
