# reverse-engineering

## 作用

这个分类存放“局部逆向分析”的能力型技能。

它们不负责定义整个 title 项目的目录结构，也不负责汉化交付链；它们只解决某一步分析任务。

## 来源

- 上游仓库：[`P4nda0s/reverse-skills`](https://github.com/P4nda0s/reverse-skills)
- 当前仓库保留目的：作为本仓库内的 `reverse-engineering` 技能分类入口
- 当前说明状态：本 README 已改写为适配 `VN_Reverse` 的分类说明，不再保留上游的插件市场展示写法

## 当前技能

- `rev-symbol`
  - 通过导出代码、字符串、导入导出表等信息恢复函数符号。
- `rev-struct`
  - 通过函数中的内存访问模式推断结构体布局。

## 适用场景

- 已经有可读的反编译结果，需要继续分析具体函数
- 想从调用关系、常量、字符串中恢复更可信的语义命名
- 想从偏移访问、调用链中还原数据结构

## 输入前提

当前这组技能默认围绕 IDA-NO-MCP 导出的目录工作。

典型输入包括：

- `decompile/`
- `strings.txt`
- `imports.txt`
- `exports.txt`
- `memory/`

## 不负责的事情

这个分类不负责：

- 新建一个 title 的整体目录骨架
- 规定补丁打包、runtime、发布物布局
- 承担 title 的长期项目状态记录

如果目标是整理一个正式汉化项目，应该优先看：

- `../galgame-localization/README.md`
