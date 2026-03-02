# 夏幻の恋（Family Adv System）

Family Adv System 引擎的游戏，目前只针对《夏幻の恋》完成验证。

## 工具说明

| 工具 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `adb_decompile.py` | ADB 反编译主入口，支持 JSON 与 ADBSRC 两种格式 | `.adb` 文件或目录 | `.json`（默认）或 `.adbsrc` |
| `adb_compile.py` | 脚本编译主入口，支持 JSON 与 ADBSRC 两种输入 | `.json` / `.adbsrc` 文件或目录 | `.adb` |
| `adb_to_adbsrc.py` | ADBSRC 快捷导出入口（内部调用 `adb_decompile.py`） | `.adb` 文件或目录 | `.adbsrc` |
| `adb_to_json.py` | 兼容入口，行为等价 `adb_decompile.py` | `.adb` 文件或目录 | `.json` |
| `json_to_adb.py` | 兼容入口，行为等价 `adb_compile.py` | `.json` 文件或目录 | `.adb` |
| `csaf_unpack.py` | 解包 CSAF 资源包并生成清单 | `adv/system` 等包文件 | `manifest.json` + `files/` |
| `csaf_pack.py` | 按清单回封 CSAF 资源包 | `manifest.json` + `files/` | CSAF 包文件 |
| `regression_test.py` | 全量回归测试（raw/ir/adbsrc/文本变长/csaf） | 游戏目录 | `PASS` 或失败信息 |

## 文档入口

| 文档 | 说明 |
|---|---|
| [`README.md`](./README.md) | 本工具总览与用法 |
| [`docs/adb_结构.md`](./docs/adb_结构.md) | NBDA/ADB 脚本结构、指令模型、ADBSRC 规则 |
| [`docs/csaf_结构.md`](./docs/csaf_结构.md) | CSAF 封包结构与回封规则 |

## 代码分层

- CLI 层：`adb_decompile.py`、`adb_compile.py`、`adb_to_adbsrc.py`
- 核心层（`nbda/`）：
  - `decompile.py`：ADB -> raw/ir
  - `compile.py`：raw/ir -> ADB
  - `adbsrc.py`：ir <-> ADBSRC
  - `binary.py`：二进制辅助
  - `constants.py`：格式常量和 opcode 名称

## 环境

- Python 3.10+

## 用法

以下命令均使用相对路径。

### 1) 反编译 ADB（默认 JSON）

单文件：

```powershell
python .\adb_decompile.py ".\game\Family Adv System\Logo.adb" .\out\Logo.adb.json
```

目录递归：

```powershell
python .\adb_decompile.py ".\game\Family Adv System" .\out\adb_json
```

默认输出规则：

- 文件输入：`<name>.adb.json`
- 目录输入：`<input_dir>_json/`，保留相对路径

### 2) 反编译 ADB 为指令源码（ADBSRC）

单文件：

```powershell
python .\adb_decompile.py ".\game\Family Adv System\Logo.adb" .\out\Logo.adbsrc --output-format adbsrc --mode ir
```

目录递归：

```powershell
python .\adb_decompile.py ".\game\Family Adv System" .\out\adb_src --output-format adbsrc --mode ir
```

快捷命令（等价）：

```powershell
python .\adb_to_adbsrc.py ".\game\Family Adv System" .\out\adb_src
```

默认输出规则：

- 文件输入：`<name>.adbsrc`
- 目录输入：`<input_dir>_adbsrc/`，保留相对路径

### 3) 编译脚本为 ADB（默认 JSON 输入）

单文件：

```powershell
python .\adb_compile.py .\out\Logo.adb.json .\out\Logo.rebuild.adb
```

目录递归：

```powershell
python .\adb_compile.py .\out\adb_json .\out\adb_rebuild
```

默认输出规则：

- 输入 `*.json`：去掉 `.json` 得到输出名
- 目录输入：默认输出到 `<input_dir>_adb/`，保留相对路径

### 4) 从 ADBSRC 编译为 ADB

单文件：

```powershell
python .\adb_compile.py .\out\Logo.adbsrc .\out\Logo.from_src.adb --input-format adbsrc
```

目录递归：

```powershell
python .\adb_compile.py .\out\adb_src .\out\adb_from_src --input-format adbsrc
```

`--input-format auto` 时会按扩展名自动识别 `.json` / `.adbsrc`。

### 5) CSAF 解包与回封

解包：

```powershell
python .\csaf_unpack.py .\game\adv .\out\adv_unpacked
```

回封：

```powershell
python .\csaf_pack.py .\out\adv_unpacked\manifest.json .\out\adv_repack
```

重算头部 MD5：

```powershell
python .\csaf_pack.py .\out\adv_unpacked\manifest.json .\out\adv_repack --update-checksum
```

## 回归测试

覆盖项：

- ADB raw：`parse_adb -> compile_adb` 字节一致
- ADB ir：`parse_adb_ir -> compile_adb` 字节一致
- ADBSRC：`parse_adb_ir -> render_ir_adbsrc -> parse_adbsrc -> compile_adb` 字节一致
- 文本变长：修改 `0x0601` 文本后重新编译，验证可再次反编译且文本一致（覆盖长度/偏移重算）
- CSAF：`unpack -> pack` 字节一致（默认 `adv`、`system`）

运行：

```powershell
python .\regression_test.py
```

自定义包：

```powershell
python .\regression_test.py --archives adv bg system
```
