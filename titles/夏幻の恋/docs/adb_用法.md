# ADB 用法

本页只保留脚本链的正式入口和正式工作流。  
脚本链的输入只认恢复后的资源树，不再从独立样本或临时样本开始。

## 正式入口

- `adb_to_adbsrc.py`
  - 默认的人类可读文本导出入口
- `adb_to_json.py`
  - 结构化文本导出入口
- `adb_compile.py`
  - 把 `ADBSRC` / `JSON` 回编成 `.adb`
- `adb_decompile.py`
  - 低层总入口
  - 只在需要手动切换 `ir/raw` 或 `json/adbsrc` 时使用
- `json_to_adb.py`
  - `JSON -> ADB` 兼容入口
- `adb_to_asm.py`
  - 历史别名
  - 当前行为等价 `adb_to_adbsrc.py`

## 正式工作流

### 1. 输入来自哪里

脚本链的正式输入来自恢复后的资源树：

- 剧情脚本  
  `resource_tree\adv\`
- 未恢复原名但已确认是剧情脚本  
  `resource_tree\adv\待补原名\`
- 系统脚本  
  `resource_tree\system\`
- 未恢复原名但已确认是系统脚本  
  `resource_tree\system\scripts\待补原名\`

不要再把下面这些当脚本入口：

- raw 解包结果
- 临时样本目录
- 独立测试样本目录
- 树外的 hash / bin 堆

### 2. 导出给人阅读的文本

```powershell
python .\adb_to_adbsrc.py .\resource_tree\adv .\adv_adbsrc
```

- 输入  
  `.\resource_tree\adv\`
- 输出  
  `.\adv_adbsrc\`
- 用途  
  人读、人工改写、核对说话人和上下文

### 3. 导出给程序处理的文本

```powershell
python .\adb_to_json.py .\resource_tree\adv .\adv_json
```

- 输入  
  `.\resource_tree\adv\`
- 输出  
  `.\adv_json\`
- 用途  
  批量处理、字段检查、程序化转换

### 4. 回编回资源树中的脚本位置

如果你改的是 `ADBSRC`：

```powershell
python .\adb_compile.py .\adv_adbsrc .\resource_tree_work\adv --input-format adbsrc
```

如果你改的是 `JSON`：

```powershell
python .\adb_compile.py .\adv_json .\resource_tree_work\adv --input-format json
```

说明：

- 修改发生在 `ADBSRC` / `JSON` 这层
- 回编结果回到 `resource_tree_work\adv\` 中对应脚本位置
- 不是回到一个独立“样本目录”

## JSON 与 ADBSRC 的角色

- `ADBSRC`
  - 优先给人看
  - 适合人工改写
- `JSON`
  - 优先给程序处理
  - 适合批量转换和字段检查

## 不属于正式工作流的入口

- `adb_decompile.py --mode raw`
  - 低层视图，不是默认文本入口
- 任何来自 raw 包体的 `.bin`
  - 都不应直接喂给 `adb_*`
