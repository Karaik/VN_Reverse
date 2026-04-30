# Git / Issue / PR 协作规则

## 目的

这个仓库后续采用：

- 先列 issue
- 再开分支
- 完成后提 PR
- 评审后合并到主分支

规则的核心不是形式化，而是避免一个分支里同时混入多个 title、多种目标和不同层级的变更。

## 基本原则

1. 一个 issue 对应一个明确目标。
2. 一个分支只服务一个 issue。
3. 一个 PR 只解决一个 issue，不顺手夹带别的 title 或别的主题。
4. 非小修任务默认不直接向主分支提交。
5. 如果一项工作横跨多个 title 或多个主题，先拆 issue，再拆分支。

## issue 起票规则

### 什么时候必须起 issue

满足任一条件时，先起 issue：

- 会进入主库
- 会新增或重构正式执行链
- 会改目录结构、README、AGENT、skills、docs、runtime、build 流程
- 会影响某个 title 的默认用法、验证标准、交付边界

可以不单独起 issue 的情况：

- 纯错字修正
- 纯链接修正
- 不影响行为的极小文案修正

### issue 粒度

一个 issue 应只覆盖一种主题：

- 一个 title 的一个明确目标
- 一个 engine 工程的一个明确目标
- 一个 skill 分类或一个具体 skill 的一次整理
- 一次仓库级规则或协作流程调整

如果同时涉及两个以上独立目标，应拆分。

### issue 标题格式

统一格式：

```text
[type/scope] summary
```

`type` 取值建议：

- `title`
- `engine`
- `skill`
- `docs`
- `repo`

`scope` 写最小可识别范围。

示例：

```text
[title/真愛の百合は赤く染まる] 固化 patch.xp3 的正式构建输入
[title/夏幻の恋] 补齐 ADBSRC 文本变长回归
[engine/NeXAS_SPM_VIEWER] 补 JavaFX 打包与测试说明
[skill/galgame-localization] 整理流程型 skill 的目录说明
[docs/repo] 拆分仓库级 AGENT 与项目类型规则
```

### issue 正文必须写清

- 背景
- 当前状态
- 目标
- 明确不做什么
- 预期交付物
- 验证方式
- 风险或依赖

## 分支规则

### 一般规则

- 一个 issue 开一个分支。
- 一个分支只处理一个项目或一个明确子任务。
- 分支名必须能看出 issue 编号和大致范围。

### 分支命名

默认按变更范围命名：

```text
feature/titles-<issue-id>
feature/engines-<issue-id>
feature/skills-<issue-id>
feature/docs-<issue-id>
feature/repo-<issue-id>
```

示例：

```text
feature/titles-128
feature/titles-128
feature/engines-145
feature/repo-173
```

约定：

- `titles`、`engines`、`skills`、`docs`、`repo` 对应本次变更的主范围
- `<issue-id>` 必须紧跟在范围后面
- `<short-slug>` 可选，用简短英文或拼音，避免太长
- 不把多个 title 名塞进同一个 slug

如果需要区分自动化创建分支，请在 issue 或 PR 说明中标注，不在分支名中引入额外前缀。

## PR 规则

### PR 标题

建议格式：

```text
[type/scope] summary
```

通常与 issue 标题保持同主题，不强求完全一致。

### PR 正文必须写清

- 关联 issue
- 这次改了什么
- 没改什么
- 怎么验证
- 已知风险

### PR 边界

PR 里不应混入：

- 另一个 title 的顺手修改
- 无关的 README 清理
- 生成产物
- 临时缓存和本地实验文件

## 合并规则

- 默认通过 PR 合并到主分支。
- 主分支只保留经过 issue 和 PR 流程的正式结果。
- 如果发现一个 PR 实际上混了多件事，先拆再合。

## issue 拆分建议

下面这些情况应拆 issue：

- 同时改脚本链和 runtime
- 同时改两个 title
- 同时做文档分层和功能实现
- 同时做仓库规则调整和 title 内部修复

## 推荐标签

如果后续要配 labels，建议至少有：

- `type:title`
- `type:engine`
- `type:skill`
- `type:docs`
- `type:repo`
- `status:blocked`
- `status:in-progress`
- `status:review`

## 模板

仓库已提供：

- `.github/ISSUE_TEMPLATE/project-task.md`
- `.github/pull_request_template.md`
