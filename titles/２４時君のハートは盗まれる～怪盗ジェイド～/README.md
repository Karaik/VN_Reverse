# ２４時君のハートは盗まれる～怪盗ジェイド～（Yuka engine）

## 工具说明

| 工具 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `ykdat_unpack.py` | 解包 `YKC` 资源包，导出文件和清单 | `.dat` 包文件 | `manifest.json` + `files/` |
| `ykdat_pack.py` | 按清单回封 `YKC` 资源包 | `manifest.json` + `files/` | `.dat` |
| `yks_decompile.py` | 脚本反编译，支持 `json` 与 `ykssrc` | `.yks` 文件或目录 | `.json`（默认）或 `.ykssrc` |
| `yks_compile.py` | 脚本编译，支持 `json` 与 `ykssrc` | `.json/.ykssrc` 文件或目录 | `.yks` |
| `regression_test.py` | 全量回归：`YKC` 回环、`YKS` 双路径回环、文本变长回归 | `game/` | `PASS` 或失败信息 |

## 文档入口

| 文档 | 说明 |
|---|---|
| [`README.md`](./README.md) | 工具总览与命令 |
| [`docs/ykc_结构.md`](./docs/ykc_结构.md) | YKC 资源包结构与封包规则 |
| [`docs/yks_结构.md`](./docs/yks_结构.md) | YKS 脚本结构、JSON/指令源码模型 |

## 用法

以下命令均使用相对路径。

### 1) 资源包解包

```powershell
python .\ykdat_unpack.py .\game\jade01.dat .\out\jade01_unpack
```

### 2) 资源包回封

```powershell
python .\ykdat_pack.py .\out\jade01_unpack\manifest.json .\out\jade01.repack.dat
```

### 3) 脚本反编译（默认 JSON）

```powershell
python .\yks_decompile.py .\out\jade01_unpack\files\Jade\J1010.yks .\out\J1010.yks.json --text-encoding cp932
```

目录递归：

```powershell
python .\yks_decompile.py .\out\jade01_unpack\files .\out\yks_json --output-format json --text-encoding cp932
```

### 4) 脚本反编译（指令源码 YKSRC）

```powershell
python .\yks_decompile.py .\out\jade01_unpack\files\Jade\J1010.yks .\out\J1010.ykssrc --output-format ykssrc --text-encoding cp932
```

### 5) 脚本编译（默认 JSON 输入）

```powershell
python .\yks_compile.py .\out\J1010.yks.json .\out\J1010.from_json.yks --input-format json --text-encoding cp932
```

### 6) 脚本编译（YKSRC 输入）

```powershell
python .\yks_compile.py .\out\J1010.ykssrc .\out\J1010.from_src.yks --input-format ykssrc --text-encoding cp932
```

### 7) 指定回写编码（GBK 示例）

源脚本文本为日文编码（`win-31j/sjis/cp932`）时，回写可显式指定目标编码：

```powershell
python .\yks_compile.py .\out\J1010.yks.json .\out\J1010.from_json.gbk.yks --input-format json --text-encoding gbk
```

必要时按相同编码反编译校验文本：

```powershell
python .\yks_decompile.py .\out\J1010.from_json.gbk.yks .\out\J1010.from_json.gbk.yks.json --text-encoding gbk
```

### 8) filter_text 过滤回写（控制符保留源编码）

如果文本里混有控制符/指令片段，需要命中后继续按源编码回写：

1. 在待编译文件同级目录放置 `filter_text.txt`（UTF-8，每行一个过滤词）。
2. 命中任一行子串的文本，不用目标编码回写，而是改用源编码（例如 `cp932`）回写。

示例（与 `case.yks.json` 同目录）：

```text
\\n
@w
ぁ
```

```powershell
python .\yks_compile.py .\out\case.yks.json .\out\case.gbk.yks --input-format json --text-encoding gbk
```

### 9) 回归测试

```powershell
python .\regression_test.py
```

覆盖项：

- `YKC`：`unpack -> pack` 字节一致
- `YKS JSON`：`parse -> compile` 字节一致（全量 `.yks`）
- `YKSRC`：`parse -> ykssrc -> parse -> compile` 字节一致（全量 `.yks`）
- 文本变长：修改可编辑 token 文本后回编，再次反编译文本一致
- 编码回写：`cp932` 脚本改文后以 `gbk` 回写，再按 `gbk` 反编译可读
- 过滤回写：命中 `filter_text.txt` 的文本以源编码回写，不受目标编码覆盖
