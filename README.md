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

- [`engines/NeXAS/NeXAS_DX`](./engines/NeXAS/NeXAS_DX)
- [`engines/NeXAS/NeXAS_SPM_VIEWER`](./engines/NeXAS/NeXAS_SPM_VIEWER)

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
- 汉化项目规则：[`docs/project-types/localization.md`](./docs/project-types/localization.md)
- 逆向项目规则：[`docs/project-types/reverse.md`](./docs/project-types/reverse.md)
- 协作约定：[`docs/workflows/git-issue-pr.md`](./docs/workflows/git-issue-pr.md)
- 困难脚本转向策略：[`docs/workflows/hard-script-pivot.md`](./docs/workflows/hard-script-pivot.md)
- `skills/` 目录规范：[`docs/skills-layout.md`](./docs/skills-layout.md)
- 技能总览：[`skills/README.md`](./skills/README.md)

## titles 一览

完成度说明：

- `完成`
  - 指对应项目类型已经达到规则文档里定义的正式测试链要求。
  - 汉化项目见：[汉化项目规则](./docs/project-types/localization.md)
  - 逆向项目见：[逆向项目规则](./docs/project-types/reverse.md)
- 如果还没达到规则里的完整回环或完整验证，就不写“完成”，只写当前实际做到哪一步。

### 仓库内项目

| 类型 | 引擎 | 项目/游戏 | 路径 | 内部 README | 完成度 |
|---|---|---|---|---|---|
| `逆向项目` | `Family Adv System` | `夏幻の恋` | [`夏幻の恋`](./titles/夏幻の恋) | [`README.md`](./titles/夏幻の恋/README.md) | `资源树 + 脚本链已通` |
| `逆向项目` | `SAISYS` | `黒の十字架` | [`黒の十字架`](./titles/黒の十字架) | [`README.md`](./titles/黒の十字架/README.md) | `脚本链已通；零漏提已验证` |
| `逆向项目` | `Studio_e-go_V2` | `月神楽` | [`月神楽`](./titles/月神楽) | [`README.md`](./titles/月神楽/README.md) | `文本汉化链已通；以文本为主` |
| `逆向项目` | `Yuka engine` | `２４時君のハートは盗まれる～怪盗ジェイド～` | [`２４時君のハートは盗まれる～怪盗ジェイド～`](./titles/２４時君のハートは盗まれる～怪盗ジェイド～) | [`README.md`](./titles/２４時君のハートは盗まれる～怪盗ジェイド～/README.md) | `资源包 + 脚本链已通` |
| `逆向项目` | `NEJII` | `比翼は愛薊の彼方へ 久遠の想` | [`比翼は愛薊の彼方へ 久遠の想`](./titles/比翼は愛薊の彼方へ%20久遠の想) | [`README.md`](./titles/比翼は愛薊の彼方へ%20久遠の想/README.md) | `资源包 + 脚本链已通` |
| `逆向项目` | `SHSystem` | `マスカレード` | [`マスカレード`](./titles/マスカレード) | [`README.md`](./titles/マスカレード/README.md) | `资源链已通；脚本仍在探针阶段` |
| `汉化项目` | `YU-RIS` | `ユニオリズム・カルテットB2-STYLE` | [`ユニオリズム・カルテットB2-STYLE`](./titles/ユニオリズム・カルテットB2-STYLE) | [`README.md`](./titles/ユニオリズム・カルテットB2-STYLE/README.md) | `完成` |

### 外部库（submodule）

| 类型 | 引擎 | 项目/游戏 | 路径 | 内部 README | 完成度 |
|---|---|---|---|---|---|
| `汉化项目` | `SystemNNN` | `虫爱少女` 文本编辑器 | [`mushiai_chineseization`](./titles/mushiai_chineseization) | [`README.md`](./titles/mushiai_chineseization/README.md) | `外部库；当前形态是汉化相关工具入口` |
| `汉化项目` | `SystemNNN` | `虫爱少女 FD 汉化项目` | [`mushiai_fd_chineseization`](./titles/mushiai_fd_chineseization) | [`README.md`](./titles/mushiai_fd_chineseization/README.md) | `外部库` |
| `汉化项目` | `KiriKiri` | `真愛の百合は赤く染まる` | [`真愛の百合は赤く染まる`](./titles/真愛の百合は赤く染まる) | [`README.md`](./titles/真愛の百合は赤く染まる/README.md) | `外部库` |

### 待归类 / 待整理

| 项目/游戏 | 路径 | 完成度 |
|---|---|---|
| `ガイザード・ファンディスク ～僕らの想いを詰め込んで～` | [`ガイザード・ファンディスク ～僕らの想いを詰め込んで～`](./titles/ガイザード・ファンディスク%20～僕らの想いを詰め込んで～) | `待归类；当前只有最小 README` |
| `臨海合宿` | [`臨海合宿`](./titles/臨海合宿) | `待归类；当前只有最小 README` |

## 推荐阅读顺序

### 看仓库

1. 先读 [`AGENT.md`](./AGENT.md)
2. 再看 [`docs/README.md`](./docs/README.md)
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

```bash
git clone --recurse-submodules <仓库地址>
cd VN_Reverse
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
    |-- mushiai_chineseization/
    |-- mushiai_fd_chineseization/
    |-- 真愛の百合は赤く染まる/
    |-- 夏幻の恋/
    |-- 黒の十字架/
    |-- 月神楽/
    |-- ２４時君のハートは盗まれる～怪盗ジェイド～/
    |-- 比翼は愛薊の彼方へ 久遠の想/
    |-- マスカレード/
    |-- ガイザード・ファンディスク ～僕らの想いを詰め込んで～/
    `-- 臨海合宿/
```

</details>
