# VN_Reverse

游戏逆向、汉化工程、引擎工具与 `skills/` 的总入口仓库。

> [!WARNING]
> 本仓库里的项目，默认都不要当成“已经真实可用”。
>
> 目前最多只说明：
> 测试链能跑。
>
> 测试通过通常只代表：
> 能反序列化、能改文本、能处理变长、能改目标编码、能回封、回封后还能再次解开并被重新解析。
>
> 不代表：
> 真进游戏就一定正常。

> [!IMPORTANT]
> 第一次看这个仓库，先读 [`docs/README.md`](./docs/README.md)。
> 要做具体项目，再进 [`titles/`](./titles) 看对应 title 的 README。

## 你要找什么

| 入口 | 作用 |
|---|---|
| [`docs/README.md`](./docs/README.md) | 仓库级文档总入口 |
| [`titles/`](./titles) | 按 title / 项目划分的主工作目录 |
| [`engines/`](./engines) | 跨作品使用的引擎工具 |
| [`skills/README.md`](./skills/README.md) | 代理技能总入口 |
| [`AGENT.md`](./AGENT.md) | 仓库级协作规则 |

## 这个仓库里有什么

### `titles/`

按 title 或项目划分的工作目录。  
仓库级正式分类只使用两类：

- 汉化项目
- 逆向项目

### `engines/`

独立引擎工具、解析器、查看器。

- `NeXAS_DX` 用于在 NeXAS 游戏资源与 JSON 之间转换，各作支持的格式见[中文说明](https://github.com/Karaik/NeXAS_DX/blob/d2b5a9f53c86cc36ec17c27baf8f187454b409b9/README_zh.md)。
- `NeXAS_SPM_VIEWER` 用于浏览 `.spm` 的页面、动画和命中区域，支持逐帧查看及 PNG 导出。[查看器项目](https://github.com/Karaik/NeXAS_SPM_VIEWER)

### `skills/`

给代码代理使用的流程型技能与能力型技能。

- [`skills/galgame-localization`](./skills/galgame-localization)
- [`skills/reverse-projects`](./skills/reverse-projects)
- [`skills/reverse-engineering`](./skills/reverse-engineering)

### `docs/`

仓库级规则、项目类型规则、工作流文档、技能布局说明。

## 文档入口

- 仓库级规则：[`AGENT.md`](./AGENT.md)
- 文档索引：[`docs/README.md`](./docs/README.md)
- 汉化项目的构建、验证与旧输出清理见[汉化项目规则](./docs/project-types/localization.md)。
- 逆向项目规则：[`docs/project-types/reverse.md`](./docs/project-types/reverse.md)
- 协作约定：[`docs/workflows/git-issue-pr.md`](./docs/workflows/git-issue-pr.md)
- 困难脚本转向策略：[`docs/workflows/hard-script-pivot.md`](./docs/workflows/hard-script-pivot.md)
- `skills/` 目录规范：[`docs/skills-layout.md`](./docs/skills-layout.md)
- 技能总览：[`skills/README.md`](./skills/README.md)

## 作品一览

`main` 的 `titles/` 下有 6 个主库直接维护的项目和 6 个汉化子模块。下表按各项目的说明和验证记录列出可用范围。

### 仓库内项目

| 项目说明 | 类型 | 引擎 | 当前范围 |
|---|---|---|---|
| [夏幻の恋](./titles/夏幻の恋/README.md) | 逆向项目 | Family Adv System | 恢复 CSAF 资源树，批量导出和回编 ADB 脚本，按需回封修改后的资源。 |
| [黒の十字架](./titles/黒の十字架/README.md) | 逆向项目 | SAISYS | 已验证 `CODE.SSB`、`DATA.SSB` 回环，以及正文、显示名和选项的变长回写。 |
| [月神楽](./titles/月神楽/README.md) | 逆向项目 | Studio_e-go_V2 | 批量处理 `game00.dat` 和 `game01.dat` 中的 `script/*.scr`，已核对其中全部非 ASCII 文本槽位。 |
| [２４時君のハートは盗まれる～怪盗ジェイド～](./titles/２４時君のハートは盗まれる～怪盗ジェイド～/README.md) | 逆向项目 | Yuka engine | YKC 资源包解包与回封，YKS 脚本支持 JSON 和指令源码两种回编路径。 |
| [比翼は愛薊の彼方へ 久遠の想](./titles/比翼は愛薊の彼方へ%20久遠の想/README.md) | 逆向项目 | NEJII | RK1 资源包回封、脚本变长回写和目标编码回写。 |
| [ユニオリズム・カルテットB2-STYLE](./titles/ユニオリズム・カルテットB2-STYLE/README.md) | 汉化项目 | YU-RIS | 已生成补丁包，并在游戏正文验证过一段中文。全量译文回归和姓名框显示仍待验证。[验证记录](./titles/ユニオリズム・カルテットB2-STYLE/docs/验证.md) |

### 汉化项目子模块

作品名链接到子库首页。本地检出时，Git 使用主库记录的提交。标为「私有」的子库需要相应的 GitHub 读取权限。

| 子库首页 | 引擎 | 本地目录（相对于 `titles/`） | 仓库状态 | 内容和发布情况 |
|---|---|---|---|---|
| [虫爱少女](https://github.com/Karaik/mushiai_chineseization) | SystemNNN | `mushiai_chineseization` | 公开，已归档 | 本篇的 JavaFX 汉化文本编辑器和人员名单。[编辑器 v1.0.6](https://github.com/Karaik/mushiai_chineseization/releases/tag/v1.0.6) |
| [虫爱少女（完全版）](https://github.com/Karaik/mushiai_fd_chineseization) | SystemNNN | `mushiai_fd_chineseization` | 私有 | 1.0.0 已发布，收录六部 FD／特典和完全版内本篇的适配补丁。[绯月首发帖](https://kf.miaola.work/read.php?tid=1086472&sf=661) · [GitHub Release](https://github.com/Karaik/mushiai_fd_chineseization/releases/tag/v1.0.0) |
| [真愛の百合は赤く染まる](https://github.com/Karaik/manakashi_chineseization) | KiriKiri | `真愛の百合は赤く染まる` | 私有 | 剧本正文和选项的回填、文本检查、界面资源与 XP3 补丁构建。 |
| [D.C.4 Fortunate Departures](https://github.com/Karaik/dc4_fd_chineseization) | KiriKiri | `dc4_fd_chineseization` | 公开，已归档 | 全年龄版的汉化技术工具。可从自备原版提取文本和图片，当前归档保留工具源码。 |
| [D.C.4 Sweet Harmony](https://github.com/Karaik/dc4_sh_chineseization) | KiriKiri | `dc4_sh_chineseization` | 私有 | 已验证剧本与系统文本回填、图片回封，以及中文样例在游戏内的显示。 |
| [D.C.5 to 4 Luminous Memories](https://github.com/Karaik/dc5_to4_chineseization) | KiriKiri | `dc5_to4_chineseization` | 私有 | 已验证资源文件名恢复、剧本文本和图片回交，以及补丁构建。 |

### 历史开发记录与待整理作品

- 《マスカレード》（SHSystem）的历史提交 `d21dcd9` 保留了 Him4/Him5 资源包的解包与回封工具，以及 Himauri 脚本的文本导出工具。变长写回的进度记录在 Issue #1。[历史版本的项目说明](https://github.com/Karaik/VN_Reverse/blob/d21dcd96644478c187a1bb3e05f1545b93ee0b8b/titles/マスカレード/README.md) · [Issue #1](https://github.com/Karaik/VN_Reverse/issues/1)
- 《ガイザード・ファンディスク ～僕らの想いを詰め込んで～》和《臨海合宿》目前是待整理的占位题目。

## 推荐阅读顺序

### 看仓库

1. 从 [`docs/README.md`](./docs/README.md) 找到任务对应的工作流
2. 参与维护时阅读仓库协作规则 [`AGENT.md`](./AGENT.md)
3. 如果任务涉及提交边界、issue / PR、验证说明，再看 [`docs/workflows/git-issue-pr.md`](./docs/workflows/git-issue-pr.md)
4. 然后按项目类型进入对应规则

### 做 title

1. 先判断它是汉化项目还是逆向项目
2. 再看对应类型文档
3. 如果脚本逆向遇到高复杂度状态机或难以完整回编，先看 [`docs/workflows/hard-script-pivot.md`](./docs/workflows/hard-script-pivot.md)
4. 最后看该 title 自己的 README 和本地规则

### 整理 skills

1. 先看 [`skills/README.md`](./skills/README.md)
2. 再看 [`docs/skills-layout.md`](./docs/skills-layout.md)

## 初始化

克隆主库即可取得仓内项目和文档。以下命令同时初始化两个公开的 NeXAS 工具子模块。

```bash
git clone https://github.com/Karaik/VN_Reverse.git
cd VN_Reverse
git submodule update --init --recursive -- engines/NeXAS/NeXAS_DX engines/NeXAS/NeXAS_SPM_VIEWER
```

作品子模块也可按上表路径单独初始化，例如 `git submodule update --init --recursive -- titles/dc4_fd_chineseization`。有全部子库读取权限时，在主库根目录同步并检出所有登记版本。

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

<details>
<summary>目录概览</summary>

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
|   |-- reverse-projects/
|   `-- reverse-engineering/
`-- titles/
    |-- dc4_fd_chineseization/
    |-- dc4_sh_chineseization/
    |-- dc5_to4_chineseization/
    |-- mushiai_chineseization/
    |-- mushiai_fd_chineseization/
    |-- 真愛の百合は赤く染まる/
    |-- ユニオリズム・カルテットB2-STYLE/
    |-- 夏幻の恋/
    |-- 黒の十字架/
    |-- 月神楽/
    |-- ２４時君のハートは盗まれる～怪盗ジェイド～/
    `-- 比翼は愛薊の彼方へ 久遠の想/
```

</details>
