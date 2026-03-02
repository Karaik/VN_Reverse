## 目录说明

- `adb_decompile.py`：ADB 反编译主入口（默认输出 JSON，可选 ADBSRC）
- `adb_compile.py`：脚本编译主入口（默认输入 JSON，也支持 ADBSRC）
- `adb_to_adbsrc.py`：快捷导出 ADBSRC（等价于 `adb_decompile.py --output-format adbsrc --mode ir`）
- `adb_to_json.py`：兼容入口，等价于 `adb_decompile.py`
- `json_to_adb.py`：兼容入口，等价于 `adb_compile.py`
- `csaf_unpack.py`：CSAF 解包
- `csaf_pack.py`：CSAF 回封
- `regression_test.py`：全量回归测试
- `docs/adb_结构.md`：ADB/NBDA 结构文档
- `docs/csaf_结构.md`：CSAF 结构文档

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
- CSAF：`unpack -> pack` 字节一致（默认 `adv`、`system`）

运行：

```powershell
python .\regression_test.py
```

自定义包：

```powershell
python .\regression_test.py --archives adv bg system
```
