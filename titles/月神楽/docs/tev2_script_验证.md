# TE_V2 脚本验证

本文只写最终态验证。

## 总入口

```powershell
python .\regression_test.py
```

## 当前正式覆盖

- 批量反编译
- 批量回编
- `BtText.dat` roundtrip
- `tiName*.dat` roundtrip 与目标编码回写
- `tiBalloon*.dat` roundtrip 与目标编码回写
- `.scr` 名字 / 正文 / 对话 / 选项回写
- `.scr` 全量非 ASCII 零漏提校验
- `.scr` 全量回写快验
- `decoded-binary` / `raw-binary`

## 当前本地结果

- 默认总验证 `PASS`
- 本地默认总验证耗时约 20~26 秒
- `game00 + game01` 的 `.scr` 非 ASCII 漏提数为 0

## 说明

默认总入口当前是正式快验，不再包含历史性的高成本样例长文回归。
正式快验只保留当前主路径必须覆盖的结构校验与回写校验。
