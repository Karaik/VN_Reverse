# 脚本层

这里是 `ADB / NBDA` 脚本链的正式实现归宿。

本层只放与脚本主链路直接相关的代码，例如：

- 脚本解析与反编译
- 脚本编译与回写
- IR / 可读源码格式
- 文本、人名、偏移与索引重算

本层不放：

- `IDA` 导出、探针、审计脚本
- 临时实验输出
- 仍冻结为 legacy 基线的旧平铺实现

当前 legacy 参考位置：

- `../tmp/legacy_20260326_snapshot/nbda/`
- `../tmp/legacy_20260326_snapshot/adb_decompile.py`
- `../tmp/legacy_20260326_snapshot/adb_compile.py`

## 当前迁移状态

- 脚本链已完成主要实现向本层的正式迁入
- 当前已迁入本层的部分：
  - `adb_decompile_app.py`
  - `adb_compile_app.py`
  - `adb_to_adbsrc_app.py`
  - `script/nbda/`
  - 根入口的 CLI 编排逻辑
- 当前根目录仍保留的：
  - 兼容入口脚本
  - `nbda/` 兼容薄壳

这意味着：

- legacy 快照不是脚本链当前运行时依赖
- 当前默认脚本实现已经由 `script/` 正式层接住
- 根目录 `nbda/` 仅保留兼容导入作用，不再承载复杂实现
