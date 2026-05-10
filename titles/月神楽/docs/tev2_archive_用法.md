# TE_V2 资源包用法

本文只写正式入口、参数、输入输出和适用场景。

## `tev2_unpack.py`

```powershell
python .\tev2_unpack.py <archive> <output_dir>
```

适用场景：
把 `gameXX.dat` 恢复成资源树。

输入：
- 单个 `gameXX.dat`

输出：
- `<output_dir>\manifest.json`
- `<output_dir>\files\`

正式示例：

```powershell
python .\tev2_unpack.py .\game\game00.dat .\pak0_game00
python .\tev2_unpack.py .\game\game01.dat .\pak0_game01
```

## 当前资源包范围

- `game00.dat`
- `game01.dat`
- `game02.dat`
- `game03.dat`
- `game04.dat`

其中当前正式脚本链只直接进入：
- `game00.dat`
- `game01.dat`
