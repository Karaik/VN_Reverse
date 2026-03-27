# 封包层

这里是 `CSAF` 封包链的正式实现归宿。

## 当前命名边界

- `csaf_raw.py`
  - 当前已实现的 raw archive 层
  - 负责包头、目录区、extra 区、block 切分、raw 清单生成与 raw 回封
- `csaf_decoded.py`
  - 运行时 decoded payload 层
  - 基于 `4062C0 -> 4061A0 -> 415500 -> 414DD0 -> 417040` 这条真实处理链实现
  - 不与 raw 层实现混写

## 根入口边界

- 根目录 `csaf_unpack.py`
  - 只负责 CLI 参数解析与转调
- 根目录 `csaf_pack.py`
  - 只负责 CLI 参数解析与转调

真正的 archive 核心逻辑应继续沉在本层，不再堆回根脚本。

## 本层适合放

- `CSAF` 外层结构解析
- raw / decoded 层的明确分离实现
- block 级处理
- 清单模型与回封共享逻辑

## 本层不放

- `IDA` 导出与逆向审计材料
- 一次性解包产物
- 仍冻结为 legacy 基线的旧平铺实现

当前 legacy 参考位置：

- `../tmp/legacy_20260326_snapshot/csaf_unpack.py`
- `../tmp/legacy_20260326_snapshot/csaf_pack.py`

## 当前迁移状态

- 封包链当前已经由正式层接住：
  - `archive/csaf_raw.py`
  - `archive/csaf_decoded.py`
- 根目录 `csaf_unpack.py` / `csaf_pack.py` 目前只是薄入口
- legacy 快照中的 `csaf_unpack.py` / `csaf_pack.py` 现已退化为历史对照实现

因此：

- legacy 快照对封包链仍然有参考价值
- 但它已经不是当前封包链的运行时依赖

## 最小验证边界

封包层后续必须同时维护两类验证：

- `raw unpack -> raw pack`
  - 验证 raw archive 层可逆
  - 标准是整包字节完全一致
- `decoded output -> runtime payload`
  - 验证 decoded 层与真实载荷一致
  - 标准是与 HOOK 包体或运行时载荷对照一致
  - 当前仓库内还补了一条刚性自校验：decoded extra region 的 MD5 必须与 archive 头部 checksum 一致

这两类验证的结论不能互相替代：

- raw 可逆，不等于 decoded 正确
- decoded 正确，也不自动证明 raw 回封路径已满足字节级一致
