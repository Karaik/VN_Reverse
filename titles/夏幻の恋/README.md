# 夏幻の恋（Family Adv System）

先看这里，这个 title 的 README 先回答 4 个问题，再给命令。

### 这个 title 最终能做什么

- 恢复一棵尽可能接近原始资源工程的资源树
- 在这棵资源树里直接定位剧情脚本资源
- 把脚本文本导出成可编辑形态
- 修改文本后再回编回资源树中的脚本资源位置
- 在你确实需要生成新包时，再继续做资源回封

### 用户运行默认入口后会得到什么

- 会得到一棵恢复后的资源树
- 根目录下会直接看到 `adv`、`system`、`bg`、`ch`、`ev`、`SE`、`BGM`、`song`、`voice`
- 已恢复原名的资源会直接落成原名
- 还没有恢复原名的资源，也会先落到各自资源根下的明确占位位置
- 根目录还会有一份 [资源清单.json](/D:/Code/VN_Reverse/titles/夏幻の恋/resource_tree/资源清单.json)，用来说明当前资源树里每个条目的路径、类别、状态和证据来源

### 脚本资源在恢复后的资源树里怎么找

- 剧情脚本入口在 `adv/`
- 已恢复原名的剧情脚本会直接在 `adv/` 下
- 还没有恢复原名但已确认是剧情脚本的条目，在 `adv/待补原名/` 下
- 如果你看到的是 `system/`、`bg/`、`voice/` 这些目录，那你已经不在剧情脚本主入口上

### 如果只是想做文本修改，应该走哪条最短路径

- 先恢复资源树
- 再直接进入 `resource_tree\adv\`
- 导出 `ADBSRC` 或 `JSON`
- 修改文本
- 把回编结果写回 `resource_tree_work\adv\`

这条最短路径之外的内容，都不是默认文本修改主线。

## 文本用户最短路径

如果你的目标只是：

- 提取文本
- 修改文本
- 回编脚本

那你最少只需要走这 4 步：

1. 恢复资源树  
   运行 `recover_resources.py`，拿到 `resource_tree\adv\`
2. 导出文本  
   对 `resource_tree\adv\` 运行 `adb_to_adbsrc.py` 或 `adb_to_json.py`
3. 准备工作树  
   复制 `resource_tree\` 到 `resource_tree_work\`
4. 回编回脚本资源  
   用 `adb_compile.py` 把修改结果写回 `resource_tree_work\adv\`

如果你只是做文本提取和回编：

- 不需要先研究 raw
- 不需要先研究封包底层
- 不需要先去看 `bg`、`ch`、`BGM`、`SE`、`song`、`voice`
- 也不需要先进入 `system` 里的非脚本资源

## 恢复后看到的关键目录是什么意思

- `resource_tree\adv\`
  - 剧情脚本主入口
  - 如果你是来做文本提取、文本修改、脚本回编，通常先看这里
- `resource_tree\adv\待补原名\`
  - 已确认属于剧情脚本，但还没恢复完整原名的脚本
  - 这些文件仍然属于脚本链输入，不需要你再自己猜
- `resource_tree\system\`
  - 系统脚本、系统配置、系统图片、菜单资源
  - 只有当你在处理系统文本或系统界面资源时，才需要从这里继续往下看
- `resource_tree\system\scripts\待补原名\`
  - 已确认属于系统脚本，但还没恢复完整原名的脚本
- `resource_tree\ev\`
  - 已恢复名字的事件图资源
- `resource_tree\bg\`、`resource_tree\ch\`、`resource_tree\BGM\`、`resource_tree\SE\`、`resource_tree\song\`、`resource_tree\voice\`
  - 各自对应背景、立绘、BGM、音效、歌曲、语音资源根
  - 如果你只是做文本修改，通常不用先碰这些目录

## 哪些目录通常不用碰

- `bg\待补原名\`
- `ch\待补原名\`
- `BGM\待补原名\`
- `SE\待补原名\`
- `song\待补原名\`
- `voice\待补原名\`

这些目录里的资源已经确认了大类归属，但当前主线不是文本修改入口。  
除非你在做更深层的图片、音频、语音逆向，否则一般不用先碰。

## 哪些目录只是暂存位置

- 任意资源根下的 `待补原名\`
  - 表示资源归属已经确认，但原始文件名还没恢复完整
- `system\_unknown_dir\待补原目录与原名\`
  - 表示这批资源连最终目录归属都还没完全恢复，只是先落在 `system` 这棵树下

这些目录不是让你自己猜用途的地方，而是正式的“待补恢复位置”：

- 已经确定它们属于哪一类资源
- 已经确定它们应该挂在哪棵资源树下
- 只是还没有把原始名字或原始目录完全补齐

## 默认主线

这个 title 的唯一默认主线只有 5 步：

1. 恢复原始资源树
2. 从资源树进入脚本链
3. 导出文本
4. 修改并回编
5. 视需要再回封资源

这份 README 只写这条主线。  
更深层的结构、验证和内部实现细节，去看 `docs/`。

## 1. 恢复原始资源树

```powershell
python .\recover_resources.py .\game .\resource_tree
```

- 这一步要达到什么目标  
  恢复当前 title 的原始资源树。
- 输入应该是什么  
  `.\game\` 目录下的游戏资源包。
- 输出会落到哪里  
  `.\resource_tree\` 目录树，以及根目录中的 `资源清单.json`。
- 这个输出接下来有什么用  
  它是后续所有流程的正式输入；如果你的目标是文本处理，下一步直接进入 `.\resource_tree\adv\`。

## 2. 从资源树进入脚本链

脚本链的正式输入来自恢复后的资源树：

- 剧情脚本位置：`.\resource_tree\adv\`
- 未恢复原名但已确认是剧情脚本的位置：`.\resource_tree\adv\待补原名\`

这一层不需要你再去别的目录猜脚本在哪里。  
下一步直接导出文本。

## 3. 导出文本

如果你要给人直接阅读和修改，优先导出 `ADBSRC`：

```powershell
python .\adb_to_adbsrc.py .\resource_tree\adv .\adv_adbsrc
```

- 这一步要达到什么目标  
  把剧情脚本导出成人可直接阅读和修改的文本形态。
- 输入应该是什么  
  `.\resource_tree\adv\`
- 输出会落到哪里  
  `.\adv_adbsrc\`
- 这个输出接下来有什么用  
  直接修改 `.\adv_adbsrc\` 中的文本，然后回编回资源树。

如果你要做结构化处理，导出 `JSON`：

```powershell
python .\adb_to_json.py .\resource_tree\adv .\adv_json
```

- 这一步要达到什么目标  
  把剧情脚本导出成结构化文本形态。
- 输入应该是什么  
  `.\resource_tree\adv\`
- 输出会落到哪里  
  `.\adv_json\`
- 这个输出接下来有什么用  
  修改 `.\adv_json\` 中的内容，然后回编回资源树。

怎么选：

- 人工阅读、人工改写：优先 `ADBSRC`
- 程序化处理、批量转换：优先 `JSON`

## 4. 修改并回编

先复制一份工作用资源树：

```powershell
Copy-Item -Recurse .\resource_tree .\resource_tree_work
```

- 这一步要达到什么目标  
  准备一棵可写的工作资源树。
- 输入应该是什么  
  第 1 步恢复得到的 `.\resource_tree\`
- 输出会落到哪里  
  `.\resource_tree_work\`
- 这个输出接下来有什么用  
  回编结果会写回这棵工作树，而不是覆盖原始恢复结果。

如果你改的是 `ADBSRC`：

```powershell
python .\adb_compile.py .\adv_adbsrc .\resource_tree_work\adv --input-format adbsrc
```

- 这一步要达到什么目标  
  把修改后的 ADBSRC 回编回资源树中的脚本资源位置。
- 输入应该是什么  
  `.\adv_adbsrc\` 中你已经修改过的 `.adbsrc`
- 输出会落到哪里  
  `.\resource_tree_work\adv\` 中对应位置的 `.adb`
- 这个输出接下来有什么用  
  继续检查脚本结果；如果你确实要生成新包，再进入第 5 步。

如果你改的是 `JSON`：

```powershell
python .\adb_compile.py .\adv_json .\resource_tree_work\adv --input-format json
```

- 这一步要达到什么目标  
  把修改后的 JSON 回编回资源树中的脚本资源位置。
- 输入应该是什么  
  `.\adv_json\` 中你已经修改过的 `.json`
- 输出会落到哪里  
  `.\resource_tree_work\adv\` 中对应位置的 `.adb`
- 这个输出接下来有什么用  
  继续检查脚本结果；如果你确实要生成新包，再进入第 5 步。

## 5. 视需要再回封资源

只有在你真的改动了 `.\resource_tree_work\` 里的内容，并且需要生成新包时，才需要这一步。  
如果你只是查看、导出、修改、验证文本，不需要默认走回封。

- 这一步要达到什么目标  
  在你确实需要生成新包时，把资源树中的改动重新回到资源包层。
- 输入应该是什么  
  你已经修改过的工作资源树，以及与之对应的回封输入。
- 输出会落到哪里  
  你的目标资源包输出位置。
- 这个输出接下来有什么用  
  进入你自己的运行验证或交付流程。

说明：

- 这一步不是人人都必须走的默认步骤
- 也不是当前 README 主流程里保留的默认命令
- 只有在你确实要生成新包时，再进入：
  [docs/csaf_用法.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/csaf_用法.md)

## 需要时再跑总验证

```powershell
python .\regression_test.py --archives adv system
```

- 这一步要达到什么目标  
  验证最终态工作流当前仍然可用。
- 输入应该是什么  
  当前 title 根目录下的正式实现和 `.\game\` 样本。
- 输出会落到哪里  
  命令行验证结果；通过时会输出 `PASS`。
- 这个输出接下来有什么用  
  如果通过，就说明资源树恢复、脚本入口、文本导出与回编、最终清单都还在；如果不过，就先修实现或文档。

## 文档入口

- 文档索引  
  [docs/README.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/README.md)
- 脚本结构  
  [docs/adb_结构.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/adb_结构.md)
- 脚本用法  
  [docs/adb_用法.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/adb_用法.md)
- 脚本验证  
  [docs/adb_验证.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/adb_验证.md)
- 封包结构  
  [docs/csaf_结构.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/csaf_结构.md)
- 封包用法  
  [docs/csaf_用法.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/csaf_用法.md)
- 封包验证  
  [docs/csaf_验证.md](/D:/Code/VN_Reverse/titles/夏幻の恋/docs/csaf_验证.md)
