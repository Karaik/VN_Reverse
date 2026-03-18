# 汉化项目规则

## 适用范围

适用于以“可维护的汉化构建链”和“可发布的汉化交付物”为目标的 title 项目。

典型信号：

- 存在 `main_build.py`
- 存在 `game_script/translated_script/`
- 存在 `solution/patch/`、`solution/runtime/`
- README 关注构建顺序、补丁输入、输出目录、冒烟测试

## 目标

汉化项目的完成标准不是“已经看懂格式”，而是：

- 译文输入路径稳定
- 构建链可重复执行
- 补丁资源与 runtime 来源清楚
- 可产出可验证的汉化包
- 增量更新文本和静态资源时不需要重新摸索流程

## 推荐目录

```text
title-root/
  README.md
  main_key.py
  main_unpack.py
  main_build.py
  game/
  game_script/
    translated_script/
  solution/
    decrypt/
    unpack/
    build/
    patch/
    runtime/
```

说明：

- 根目录只保留直接入口和必要说明。
- 真正的实现、静态补丁资源、runtime 源码、key 材料优先放在 `solution/` 下。
- `game/` 视为本地输入，不应被 README 描述成可提交产物。

## 必须回答的问题

每个汉化项目都应明确写清：

- 原版输入在哪里
- 译文输入在哪里
- 静态补丁资源在哪里
- runtime 是否需要从源码编译
- 输出目录长什么样
- 如何做只改文本、只改静态资源、首次完整构建

## 脚本与资源要求

- 如果脚本格式仍需要逆向，先补齐可编辑 roundtrip，再宣称脚本链完成。
- 如果脚本文本使用 `cp932`、`Shift_JIS`、`win-31j` 这类编码，必须有明确的回写编码策略；如需 `gbk` 路径，要在文档里显式写例子。
- 如果存在 `filter_text.txt` 语义，必须把过滤回写规则写进文档，并覆盖回归测试。
- 如果最终交付不只靠资源覆盖，还需要 `exe`、`dll` 或 proxy DLL，必须说明编译来源和验证方式。

## 验证要求

最少应覆盖：

- 文本输入到脚本回填的验证
- 资源或补丁包重建后的验证
- runtime 二进制构建或导出验证
- 最终可运行汉化包的冒烟验证

## 不要混入的内容

- 不要把纯逆向研究日志当成汉化项目的主流程文档。
- 不要把临时目录、手工搬运目录写成正式默认路径。
- 不要把“给 AI 的执行说明”继续塞到 README 的折叠块里。

## 对应 skill

如果是在搭建或整理这类项目，优先使用：

- `skills/galgame-localization/vn-localization-project/SKILL.md`
