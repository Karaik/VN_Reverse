# VN_Reverse

本人自用的游戏逆向与资源工程总入口仓库。

这个仓库不负责实现所有工具本体，主要做三件事：

1. 放入口
2. 定协作方式
3. 保证多仓联动时可复现

## 命令集

```bash
git clone --recurse-submodules <仓库地址>
cd VN_Reverse
git submodule sync --recursive
git submodule update --init --recursive
```

## 一览

### engines

- `NeXAS`
  - `NeXAS_DX`  
    路径：[`engines/NeXAS/NeXAS_DX`](./engines/NeXAS/NeXAS_DX)
  - `NeXAS_SPM_VIEWER`  
    路径：[`engines/NeXAS/NeXAS_SPM_VIEWER`](./engines/NeXAS/NeXAS_SPM_VIEWER)
- `SystemNNN`
  - 预留入口，后续按同层级追加模块。

### titles

| 引擎 | 游戏/项目 | 路径 | 内部 README | 结构文档（非子库） |
|---|---|---|---|---|
| `SystemNNN` | `mushiai_chineseization` | [`titles/mushiai_chineseization`](./titles/mushiai_chineseization) | [`README.md`](./titles/mushiai_chineseization/README.md) | |
| `Family Adv System` | `夏幻の恋` | [`titles/夏幻の恋`](./titles/夏幻の恋) | [`README.md`](./titles/夏幻の恋/README.md) | [`adb_结构.md`](./titles/夏幻の恋/docs/adb_结构.md)、[`csaf_结构.md`](./titles/夏幻の恋/docs/csaf_结构.md) |

## 目录

```text
VN_Reverse/
|-- engines/
|   |-- NeXAS/
|   |   |-- NeXAS_DX/
|   |   `-- NeXAS_SPM_VIEWER/
|   `-- SystemNNN/
|-- titles/
|   |-- mushiai_chineseization/
|   `-- 夏幻の恋/
|-- .gitmodules
|-- .gitignore
`-- README.md
```
