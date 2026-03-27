# 资源树恢复与封包用法

本页只保留封包方向的正式入口和正式工作流。

## 正式入口

- `recover_resources.py`
  - 默认入口
  - 恢复整棵原始资源树
- `csaf_unpack.py`
  - 单包入口
  - 只在你明确只处理某一个 archive 时使用
- `csaf_pack.py`
  - 回封入口
  - 只在你真的需要生成包或验证 pack/unpack 时使用

## 正式工作流

### 1. 默认入口：恢复整棵资源树

```powershell
python .\recover_resources.py .\game .\resource_tree
```

- 输入  
  `.\game\` 下的 archive 集合
- 输出  
  `.\resource_tree\`
- 用途  
  把资源先恢复成最终树，再从树里定位脚本、图片、系统资源

### 2. 单包入口：只恢复某一个 archive

```powershell
python .\csaf_unpack.py .\game\adv .\adv_tree
```

- 输入  
  单个 archive，例如 `.\game\adv`
- 输出  
  对应 archive 的恢复结果树
- 用途  
  当你只想单独看某一个包时使用

### 3. 回封入口：只在真的需要生成包时使用

```powershell
python .\csaf_pack.py .\work\adv_raw\raw_index.json .\work\adv.repack
```

- 输入  
  raw archive manifest
- 输出  
  回封后的 archive
- 用途  
  验证 pack/unpack 可逆，或在你明确需要生成 archive 时使用

## 不属于默认工作流的内容

- raw 层
- hash 命名
- 底层 block 语义
- 调试清单

这些都不再是 README 主流程入口，只保留在更深层结构/验证说明里。
