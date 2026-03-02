# 比翼は愛薊の彼方へ 久遠の想（NEJII）

## 工具说明

| 工具 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `nejii_unpack.py` | 解包 RK1 资源包，导出解压后文件与清单 | `.dat/.vdt/.cdt/.ovd/.pdt` 文件或目录 | `manifest.json` + `files/` + `packed/` |
| `nejii_pack.py` | 按清单回封 RK1 资源包 | `manifest.json` 文件或目录 | 资源包文件 |
| `nejii_decompile.py` | 脚本反编译，支持 `json` 与 `nejsrc` | `.bin` 文件或目录 | `.json`（默认）或 `.nejsrc` |
| `nejii_compile.py` | 脚本编译，支持 `json` 与 `nejsrc` | `.json/.nejsrc` 文件或目录 | `.bin` |
| `regression_test.py` | 回归测试（封包回环、脚本双路径回环、文本变长、编码回写、过滤回写） | `game/` | `PASS` 或失败信息 |

## 文档入口

| 文档 | 说明 |
|---|---|
| [`README.md`](./README.md) | 工具总览与命令 |
| [`docs/rk1_结构.md`](./docs/rk1_结构.md) | RK1 资源包结构与回封规则 |
| [`docs/script_bin_结构.md`](./docs/script_bin_结构.md) | NEJII 脚本 BIN 指令结构与 JSON/NEJSRC 模型 |

## 用法

以下命令均使用相对路径。

### 1) 解包资源包

```powershell
python .\nejii_unpack.py .\game\script.dat .\out\script_unpack
```

目录递归：

```powershell
python .\nejii_unpack.py .\game .\out\archives_unpack
```

### 2) 回封资源包

```powershell
python .\nejii_pack.py .\out\script_unpack\manifest.json .\out\script.repack.dat
```

目录递归：

```powershell
python .\nejii_pack.py .\out\archives_unpack .\out\archives_repack
```

### 3) 脚本反编译（默认 JSON）

```powershell
python .\nejii_decompile.py .\out\script_unpack\files\0100.BIN .\out\0100.BIN.json --text-encoding cp932
```

目录递归：

```powershell
python .\nejii_decompile.py .\out\script_unpack\files .\out\bin_json --output-format json --text-encoding cp932
```

### 4) 脚本反编译（指令源码 NEJSRC）

```powershell
python .\nejii_decompile.py .\out\script_unpack\files\0100.BIN .\out\0100.BIN.nejsrc --output-format nejsrc --text-encoding cp932
```

### 5) 脚本编译（默认 JSON 输入）

```powershell
python .\nejii_compile.py .\out\0100.BIN.json .\out\0100.from_json.BIN --input-format json --text-encoding cp932
```

### 6) 脚本编译（NEJSRC 输入）

```powershell
python .\nejii_compile.py .\out\0100.BIN.nejsrc .\out\0100.from_src.BIN --input-format nejsrc --text-encoding cp932
```

### 7) 指定回写编码（GBK 示例）

源脚本文本为日文编码（`win-31j/sjis/cp932`）时，回写可显式指定目标编码：

```powershell
python .\nejii_compile.py .\out\0100.BIN.json .\out\0100.from_json.gbk.BIN --input-format json --text-encoding gbk
```

必要时按相同编码反编译校验文本：

```powershell
python .\nejii_decompile.py .\out\0100.from_json.gbk.BIN .\out\0100.from_json.gbk.BIN.json --text-encoding gbk
```

### 8) filter_text 过滤回写（控制符保留源编码）

在待编译文件同级目录放置 `filter_text.txt`（UTF-8，每行一个过滤词）。  
命中任一过滤项时，该文本按源编码回写，不使用目标编码。

示例（与 `0100.BIN.json` 同目录）：

```text
\n
@w
ぁ
```

```powershell
python .\nejii_compile.py .\out\0100.BIN.json .\out\0100.filtered.BIN --input-format json --text-encoding gbk
```

### 9) key 文件约定

如果后续确认该 title 存在解密 key，单独放在项目根目录 `key.txt`，工具从该文件读取，不把 key 写死到代码中。

### 10) 回归测试

```powershell
python .\regression_test.py
```

覆盖项：

- `RK1`：`unpack -> pack` 字节一致
- `BIN JSON`：`parse -> compile` 字节一致（全量 `script.dat` 内 `.BIN`）
- `NEJSRC`：`parse -> src -> parse -> compile` 字节一致（全量 `script.dat` 内 `.BIN`）
- 文本变长：修改可编辑文本后回编，再反编译文本一致
- 编码回写：`cp932` 脚本改文后以 `gbk` 回写，再按 `gbk` 反编译可读
- 过滤回写：命中 `filter_text.txt` 的文本按源编码回写
