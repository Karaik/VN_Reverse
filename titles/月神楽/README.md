# 月神楽（Studio_e-go_V2）

这个 title 当前已经收束到一条正式汉化主路径：

1. 从资源包恢复资源树
2. 从资源树批量导出脚本文本
3. 修改 JSON 文本
4. 批量回编回 `.scr/.dat`
5. 按需回填到你的资源树或后续封包链

当前脚本正式覆盖范围是 `game00.dat` 与 `game01.dat` 中的 `script/*.scr`。
本地结构校验结果是：这两处脚本里的非 ASCII 文本槽位零漏提，默认总验证可在 1 分钟内完成。

**文本汉化最短路径**

先解出目标资源包：

```powershell
python .\tev2_unpack.py .\game\game00.dat .\pak0_game00
```

目标：
把原始资源包恢复成可直接浏览的资源树。
输入：
`game00.dat` 或 `game01.dat`。
输出：
`.\pak0_game00\files\`。
下一步：
把这棵资源树作为脚本导出输入。

批量导出文本：

```powershell
python .\tev2_decompile.py .\pak0_game00\files .\text_dump --batch --mode decoded --text-encoding cp932
```

目标：
把可编辑文本导出成 JSON。
输入：
解包后的 `files\` 资源树。
输出：
`.\text_dump\script\*.json`
`.\text_dump\data\*.json`
下一步：
直接修改这些 JSON 里的 `text` 字段。

批量回编文本：

```powershell
python .\tev2_compile.py .\text_dump .\text_rebuild --batch --mode decoded --text-encoding gbk
```

目标：
把修改后的 JSON 回编成 `.scr/.dat` 资源。
输入：
批量导出的 JSON 目录。
输出：
`.\text_rebuild\script\*.scr`
`.\text_rebuild\data\*.dat`
下一步：
把这些结果覆盖回你的资源树，再进入你自己的封包链。

**正式入口**

`tev2_unpack.py`

```powershell
python .\tev2_unpack.py .\game\game01.dat .\pak0_game01
```

目标：
恢复 `game01.dat` 的资源树。
输入：
单个 `gameXX.dat`。
输出：
目标目录下的 `manifest.json` 与 `files\`。
下一步：
对 `files\` 继续做批量导出或二进制导出。

`tev2_decompile.py`

```powershell
python .\tev2_decompile.py .\pak0_game01\files .\text_dump_game01 --batch --mode decoded --text-encoding cp932
```

目标：
批量导出正式可编辑文本。
输入：
资源树根目录。
输出：
镜像结构的 JSON 目录。
下一步：
修改 JSON 后用 `tev2_compile.py` 回编。

指定目标编码回写示例：

```powershell
python .\tev2_compile.py .\text_dump_game01 .\text_rebuild_game01 --batch --mode decoded --text-encoding gbk
```

目标：
按指定目标编码批量回编。
输入：
JSON 文本目录。
输出：
批量回编后的 `.scr/.dat`。
下一步：
回填到资源树并进入封包链。

二进制模式仍然保留，但只作为正式辅助入口：

```powershell
python .\tev2_decompile.py .\pak0_game00\files .\decoded_dump --batch --mode decoded-binary
python .\tev2_compile.py .\decoded_dump .\decoded_rebuild --batch --mode decoded-binary --source .\pak0_game00\files
python .\tev2_decompile.py .\pak0_game00\files .\raw_dump --batch --mode raw-binary
python .\tev2_compile.py .\raw_dump .\raw_rebuild --batch --mode raw-binary
```

**默认验证**

```powershell
python .\regression_test.py
```

目标：
验证默认正式主路径。
输入：
当前 title 根目录下的 `game00.dat` / `game01.dat`。
输出：
终端 `PASS`。
下一步：
若通过，可按 README 主路径直接做文本汉化。

当前默认验证本地覆盖：

- `game00 + game01` 的脚本文本零漏提校验
- `.scr` 全量回写快验
- `BtText.dat / tiName*.dat / tiBalloon*.dat` roundtrip 与编码回写
- 批量导出 / 批量回编 / 二进制辅助模式

**文档**

- [docs/README.md](D:/Code/VN_Reverse/titles/月神楽/docs/README.md)
- [docs/tev2_script_结构.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_script_结构.md)
- [docs/tev2_script_用法.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_script_用法.md)
- [docs/tev2_script_验证.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_script_验证.md)
- [docs/tev2_archive_结构.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_archive_结构.md)
- [docs/tev2_archive_用法.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_archive_用法.md)
- [docs/tev2_archive_验证.md](D:/Code/VN_Reverse/titles/月神楽/docs/tev2_archive_验证.md)
