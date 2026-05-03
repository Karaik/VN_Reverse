# 技能总览

## 作用

`skills/` 存放给代码代理使用的仓库内技能。

这里的内容不直接等于项目代码，也不等于 title 的状态记录。它更像“可复用的方法集”。

## 当前分类

- `galgame-localization/`
  - 面向 title 级汉化项目的流程型技能。
- `reverse-projects/`
  - 面向 title 级逆向项目的流程型技能。
- `reverse-engineering/`
  - 面向局部逆向分析任务的能力型技能。
  - 当前分类内容来自外部仓库 `P4nda0s/reverse-skills`，并已按本仓库结构重写说明文档。

## 使用方式

先判断你要做的是哪类事：

- 如果是在建立或整理一个可交付的汉化项目，优先看 `galgame-localization/`
- 如果是在建立或整理一个正式逆向 title 的主入口文档和执行链，优先看 `reverse-projects/`
- 如果是在做函数、结构、调用链等局部逆向分析，优先看 `reverse-engineering/`

## 目录约定

推荐布局见：

- `../docs/skills-layout.md`

每个分类目录应有自己的 `README.md`，每个具体技能目录应包含自己的 `SKILL.md`。
