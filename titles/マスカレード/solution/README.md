# solution 目录

`solution` 目录只保留 `マスカレード` 当前主线所需的正式实现：

- `common/`：`Him4/Him5` 共用逻辑
- `unpack/`：解包实现
- `build/`：回封实现
- `script/`：`Himauri` 的文本载体与静态写回前置分析

## 当前口径

- 封包层已经足够稳定，可继续作为正式输入输出链使用。
- 脚本层当前重点不是继续扩张状态机研究，而是为静态变长写回补齐结构事实。
- 历史研究型说明已从主线说明中移出，不再作为默认入口。

## 交接入口

- 当前主线清单：[`../docs/checklist.md`](../docs/checklist.md)
- 当前阶段日志：[`../docs/stage_log.md`](../docs/stage_log.md)
