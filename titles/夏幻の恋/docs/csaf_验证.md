# 资源树恢复与封包最终态验证

本页只写封包方向在最终态主流程中的验证。

## 验证入口

- `python .\regression_test.py --archives adv system`

执行基准：

- 必须在 `D:\Code\VN_Reverse\titles\夏幻の恋` 下执行

## 总验证如何覆盖 README 主流程

README 的主流程不是先看 raw、也不是先看中间样本，而是先恢复 `resource_tree/`。  
总验证现在已经按这条默认主线验证：

### 1. 资源树恢复是否稳定

总验证会检查：

- 默认输出根是否已经是资源树
- 资源根是否齐全
- 是否仍然暴露旧的中间层根
- `资源清单.json` 是否存在

### 2. 关键已恢复原名资源是否到位

总验证会检查这些关键资源是否已经落在最终树中：

- `adv/logo.adb`
- `adv/SNR.adb`
- `system/save/save.adb`
- `system/window/menu.adb`
- `system/album/list.csv`
- `SE/sys01.ogg`
- `ev/EV01_01.png`

### 3. 未恢复原名资源是否也已先成树

总验证会检查这些位置是否存在：

- `bg/待补原名/images/...`
- `voice/待补原名/clips/...`
- `BGM/待补原名/audio/...`
- `SE/待补原名/audio/...`
- `system/_unknown_dir/待补原目录与原名/...`

也就是说，标准不是“未知资源有没有消失”，而是“未知资源是否已经先落到正确资源根和正确状态目录”。

### 4. 最终态清单是否可用

总验证会检查 `资源清单.json` 是否具备这些最终态字段：

- `original_path`
- `current_path`
- `resource_category`
- `recovery_status`
- `evidence_sources`

并检查 `evidence_sources` 是否只使用正式类别：

- `包内目录项`
- `外部索引`
- `运行时路径`
- `脚本引用`
- `系统表`
- `其他来源`

### 5. 回封验证是否仍然成立

总验证仍保留 `raw unpack -> raw pack` 的可逆验证。

说明：

- 这一步是封包层验证
- 不是用来替代资源树恢复验证
- 也不是用来替代脚本链工作流验证

## 当前结果

已按当前 title 根目录基准执行：

```powershell
python .\regression_test.py --archives adv system
```

当前结果：

- `PASS`
