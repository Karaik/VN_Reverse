# SSB 验证

脚本链正式验证目标：

- `CODE.SSB` / `DATA.SSB` 可解密并建立结构化表示
- 反编译 -> 回编可跑通 unchanged roundtrip
- 文本修改后可回编
- 目标编码写回后仍可再次反编译

## 当前正式验证入口

```powershell
python .\regression_test.py
```

## 当前已覆盖

- `CODE.SSB` unchanged roundtrip
- `DATA.SSB` unchanged roundtrip
- `cp932` 路径下的日文文本回写
- `cp932` 路径下的变长日文文本追加回写
- `gbk` 目标编码写回
- 目标编码写回后再次反编译恢复文本

## 当前未覆盖

- 完整剧情文本语义级回编
- 资源层独立回封
