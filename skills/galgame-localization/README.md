# galgame-localization

## 作用

这个分类存放“title 级汉化项目”的流程型技能。

它解决的问题不是单个函数怎么分析，而是：

- 项目怎么落目录
- 脚本、资源、runtime、补丁怎么进入正式执行链
- 文档和回归应该怎么配套

## 当前技能

- `vn-localization-project`
  - 用于新建、迁移、整理、规范化一个视觉小说汉化项目。

## 适用场景

- 新开一个 title 的汉化工程
- 把旧的补丁链迁到项目内稳定路径
- 给已有 title 补齐文档、构建入口、回归验证
- 统一 `solution/`、`game_script/`、`patch/`、`runtime/` 的职责

## 不负责的事情

这个分类不负责：

- 单个函数的符号恢复
- 结构体重建
- 只针对某个局部逆向问题的分析任务

这类事情应放到 `reverse-engineering/`。
