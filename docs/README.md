# 文档索引

## 目的

这里存放仓库级的稳定文档，不放某个单独 title 的局部状态记录。

仓库级正式项目类型只使用两类：

- 汉化项目
- 逆向项目

## 入口

- `project-types/localization.md`
  - 汉化项目的目标、目录、交付边界、验证要求。
- `project-types/reverse.md`
  - 逆向项目的目标、目录、交付边界、验证要求。
- `workflows/git-issue-pr.md`
  - issue、分支、PR、合并的协作规则。
- `workflows/hard-script-pivot.md`
  - 困难脚本遇到高复杂度状态机时，何时停止完整逆向并转向汉化优先方案。
- `skills-layout.md`
  - `skills/` 目录的推荐组织方式，以及何时新建分类或技能。

## 使用方式

进入某个 `title` 之前，先判断项目类型，再读对应文档：

- 做汉化构建链、补丁打包、runtime、译文输入时，看 `project-types/localization.md`
- 做格式逆向、反编译、回编、封包回环时，看 `project-types/reverse.md`
- 要切分支、提 issue、做 PR 时，看 `workflows/git-issue-pr.md`
- 遇到困难脚本、准备从完整逆向切到汉化优先方案时，看 `workflows/hard-script-pivot.md`
- 准备新增或整理技能时，看 `skills-layout.md`
- 如果某个目录暂时还无法归类，不要新增第三种项目类型，先记为待判定目录。

## 写作约定

- 仓库内自写文档默认使用中文。
- 同一份文档的自然语言保持单语一致，不做中英混写。
- 路径、命令、代码标识、仓库名等技术标识可保留原文。
- 外库原文档除外，但应在本仓库说明文档中标注来源。
