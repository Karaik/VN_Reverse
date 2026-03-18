# VN_Reverse

游戏逆向、汉化工程、引擎工具与 `skills/` 目录的总入口仓库。

这个仓库不是单一类型项目仓库，而是一个混合仓库。当前主要承担四件事：

1. 提供跨仓入口
2. 给不同项目类型建立清晰边界
3. 沉淀仓库级规则与文档
4. 保证多仓联动时可复现

## 初始化

```bash
git clone --recurse-submodules <仓库地址>
cd VN_Reverse
git submodule sync --recursive
git submodule update --init --recursive
```

## 文档入口

- 仓库级规则：[`AGENT.md`](./AGENT.md)
- 文档索引：[`docs/README.md`](./docs/README.md)
- 汉化项目规则：[`docs/project-types/localization.md`](./docs/project-types/localization.md)
- 逆向项目规则：[`docs/project-types/reverse.md`](./docs/project-types/reverse.md)
- 协作流程：[`docs/workflows/git-issue-pr.md`](./docs/workflows/git-issue-pr.md)
- 困难脚本转向策略：[`docs/workflows/hard-script-pivot.md`](./docs/workflows/hard-script-pivot.md)
- `skills/` 目录规范：[`docs/skills-layout.md`](./docs/skills-layout.md)
- 技能总览：[`skills/README.md`](./skills/README.md)

## 目录角色

### engines

引擎层独立工程、解析器、查看器。

- `NeXAS`
  - [`engines/NeXAS/NeXAS_DX`](./engines/NeXAS/NeXAS_DX)
  - [`engines/NeXAS/NeXAS_SPM_VIEWER`](./engines/NeXAS/NeXAS_SPM_VIEWER)

### skills

给代码代理使用的流程型技能与能力型技能。

- [`skills/galgame-localization`](./skills/galgame-localization)
- [`skills/reverse-engineering`](./skills/reverse-engineering)

### titles

按 title 或项目划分的工作目录。

仓库级正式分类只使用两类：

- 汉化项目
- 逆向项目

## titles 一览

| 类型 | 引擎 | 项目/游戏 | 路径 | 内部 README | 备注 |
|---|---|---|---|---|---|
| `汉化项目` | `SystemNNN` | `虫爱少女` 文本编辑器 | [`mushiai_chineseization`](./titles/mushiai_chineseization) | [`README.md`](./titles/mushiai_chineseization/README.md) | 当前形态是汉化相关工具入口 |
| `汉化项目` | `SystemNNN` | `虫爱少女 FD 汉化项目` | [`mushiai_fd_chineseization`](./titles/mushiai_fd_chineseization) | [`README.md`](./titles/mushiai_fd_chineseization/README.md) | |
| `汉化项目` | `KiriKiri` | `真愛の百合は赤く染まる` | [`真愛の百合は赤く染まる`](./titles/真愛の百合は赤く染まる) | [`README.md`](./titles/真愛の百合は赤く染まる/README.md) | |
| `逆向项目` | `Family Adv System` | `夏幻の恋` | [`夏幻の恋`](./titles/夏幻の恋) | [`README.md`](./titles/夏幻の恋/README.md) | |
| `逆向项目` | `Yuka engine` | `２４時君のハートは盗まれる～怪盗ジェイド～` | [`２４時君のハートは盗まれる～怪盗ジェイド～`](./titles/２４時君のハートは盗まれる～怪盗ジェイド～) | [`README.md`](./titles/２４時君のハートは盗まれる～怪盗ジェイド～/README.md) | |
| `逆向项目` | `NEJII` | `比翼は愛薊の彼方へ 久遠の想` | [`比翼は愛薊の彼方へ 久遠の想`](./titles/比翼は愛薊の彼方へ%20久遠の想) | [`README.md`](./titles/比翼は愛薊の彼方へ%20久遠の想/README.md) | |
| `逆向项目` | `SHSystem` | `マスカレード` | [`マスカレード`](./titles/マスカレード) | [`README.md`](./titles/マスカレード/README.md) | |

尚未正式归类的目录只保留在下方目录概览中，不在仓库级分类表里单独立类。

## 推荐阅读顺序

### 看仓库

1. 先读 [`AGENT.md`](./AGENT.md)
2. 再看 [`docs/README.md`](./docs/README.md)
3. 如果任务要进入主库，先看 [`docs/workflows/git-issue-pr.md`](./docs/workflows/git-issue-pr.md)
4. 然后按项目类型进入对应规则

### 做 title

1. 先判断它是汉化项目还是逆向项目
2. 再看对应类型文档
3. 如果脚本逆向遇到高复杂度状态机或难以完整回编，先看 [`docs/workflows/hard-script-pivot.md`](./docs/workflows/hard-script-pivot.md)
4. 最后看该 title 自己的 README 和本地规则

### 整理 skills

1. 先看 [`skills/README.md`](./skills/README.md)
2. 再看 [`docs/skills-layout.md`](./docs/skills-layout.md)

## 目录概览

```text
VN_Reverse/
|-- AGENT.md
|-- docs/
|   |-- README.md
|   |-- project-types/
|   |   |-- localization.md
|   |   `-- reverse.md
|   |-- skills-layout.md
|   `-- workflows/
|       |-- git-issue-pr.md
|       `-- hard-script-pivot.md
|-- engines/
|   `-- NeXAS/
|       |-- NeXAS_DX/
|       `-- NeXAS_SPM_VIEWER/
|-- skills/
|   |-- README.md
|   |-- galgame-localization/
|   `-- reverse-engineering/
`-- titles/
    |-- mushiai_chineseization/
    |-- mushiai_fd_chineseization/
    |-- 真愛の百合は赤く染まる/
    |-- 夏幻の恋/
    |-- ２４時君のハートは盗まれる～怪盗ジェイド～/
    |-- 比翼は愛薊の彼方へ 久遠の想/
    |-- マスカレード/
    |-- ガイザード・ファンディスク ～僕らの想いを詰め込んで～/
    `-- 臨海合宿/
```
