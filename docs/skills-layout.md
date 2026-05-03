# skills 目录规范

## 目的

`skills/` 只负责存放给代码代理使用的技能，不承担 title 项目的状态记录，也不充当公开展示页。

## 当前推荐布局

```text
skills/
  README.md
  <category>/
    README.md
    <skill-name>/
      SKILL.md
      references/
      scripts/
      assets/
```

## 目录层级含义

### 分类目录

`<category>/` 表示技能领域，而不是具体单个技能。

示例：

- `galgame-localization/`
- `reverse-projects/`
- `reverse-engineering/`

分类目录下应有一个 `README.md`，说明：

- 这个分类解决什么问题
- 当前有哪些技能
- 何时使用这些技能
- 哪些内容不应放到这个分类里

### 叶子技能目录

`<skill-name>/` 是一个可直接被代理使用的具体技能目录。

叶子目录至少包含：

- `SKILL.md`

按需包含：

- `references/`
- `scripts/`
- `assets/`

## 两类技能

### 流程型技能

特点：

- 定义一整类项目的工作流
- 会描述目录模板、交付边界、验证要求
- 更接近“项目骨架”或“执行规范”

示例：

- `galgame-localization/vn-localization-project`

### 能力型技能

特点：

- 只解决一个局部分析任务
- 不负责定义整个项目结构
- 适合作为流程中的单一步骤使用

示例：

- `reverse-engineering/rev-symbol`
- `reverse-engineering/rev-struct`

## 什么时候新建分类

满足下面任一条件时，再考虑新增一级分类：

- 已经有两到三个以上同领域技能
- 这些技能共享术语、参考资料或使用前提
- 用一个总 README 能明显降低误用

如果只是新增一个同领域技能，优先放到已有分类下，不要急着再开新分类。

## 什么时候新建技能

适合新建独立技能的情况：

- 有稳定、可复用的输入前提
- 有明确、可重复的输出
- 有固定步骤，值得让代理复用

不适合新建技能的情况：

- 只是某个 title 的当前临时状态
- 只是一次性备注
- 只是某个项目 README 的补充说明

## 迁移建议

当前仓库建议保持：

- `galgame-localization/`：放 title 级汉化流程型技能
- `reverse-projects/`：放 title 级逆向流程型技能
- `reverse-engineering/`：放局部逆向能力型技能

后续如果出现“打包/发布/检查器”这类能跨多个 title 复用的流程，再考虑新增新的技能或扩充现有分类。
