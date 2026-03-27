# ADB 最终态验证

本页只写脚本链在最终态主流程中的验证。

## 验证入口

- `python .\regression_test.py --archives adv system`

执行基准：

- 必须在 `D:\Code\VN_Reverse\titles\夏幻の恋` 下执行

## 总验证如何覆盖 README 主流程

README 的默认主流程使用这些目录名：

- `resource_tree`
- `adv_adbsrc`
- `adv_json`
- `resource_tree_work`

总验证已经直接覆盖这条流程，而不是绕回独立样本或临时样本。

### 1. 恢复原始资源树

总验证会先恢复 `resource_tree/`，并检查：

- `adv/`
- `system/`
- `bg/`
- `ch/`
- `ev/`
- `SE/`
- `BGM/`
- `song/`
- `voice/`
- `资源清单.json`

是否都在正确位置。

### 2. 从资源树中定位脚本

总验证会检查：

- `resource_tree\adv\` 是否存在
- `resource_tree\adv\` 下是否总计有 `72` 个 `.adb`
- `resource_tree\adv\待补原名\` 是否已纳入剧情脚本入口
- `resource_tree\system\scripts\待补原名\` 是否已纳入系统脚本入口

### 3. 脚本文本导出

总验证会直接从 `resource_tree\adv\` 导出：

- `adv_adbsrc\`
- `adv_json\`

并检查：

- `ADBSRC` 导出数量是否为 `72`
- `JSON` 导出数量是否为 `72`

### 4. 脚本修改后回编

总验证会复制一份 `resource_tree_work\`，然后分别验证：

- `ADBSRC -> resource_tree_work\adv\`
- `JSON -> resource_tree_work\adv\`

验证点：

- 回编结果是否真的写回资源树中的脚本位置
- 二次反解析后，修改过的文本是否仍然存在

### 5. 脚本 roundtrip 与文本回归

总验证还覆盖：

- `ADB -> IR -> ADB`
- `ADB -> ADBSRC -> ADB`
- 正文变长回归
- 说话人名修改回归

## 当前结果

已按当前 title 根目录基准执行：

```powershell
python .\regression_test.py --archives adv system
```

当前结果：

- `PASS`
