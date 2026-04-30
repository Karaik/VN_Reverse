# ユニオリズム・カルテットB2-STYLE

## 项目定位

这是一个 `YU-RIS` 汉化项目。

正式入口在项目根目录：

- `main_key.py`
- `main_unpack.py`
- `main_translate.py`
- `main_build.py`
- `regression_test.py`

正式实现放在 `solution/`，原文和译文输入输出放在 `game_script/`。

## 游戏资源放置

本项目不提交游戏资源。

拉下项目后，需要把原版游戏资源按相对路径放到 `game/` 下，至少需要：

- `game/UQB2S.exe`
- `game/pac/update1.ypf`
- `game/pac/ysbin.ypf`
- 其他原版运行所需的 `DLL / wav / dat / save / pac` 文件

默认约定就是直接把原版游戏根目录内容放进 `game/`。

## 默认使用流程

1. `python .\\main_key.py`
2. `python .\\main_unpack.py`
3. 检查 `game_script/original_script/`
4. `python .\\main_translate.py`
5. 填写或更新 `game_script/translated_script/`
6. `python .\\main_build.py`
7. 在最新 `out/release_时间戳/` 中直接启动 `UQB2S_chs.exe`

## 输出目录

`main_build.py` 会生成两类产物：

- `out/release_时间戳/`
  - 本地自测用的完整可运行副本
- `out/package_时间戳/`
  - 分发用的最小补丁包

当前补丁形态是：

- `UQB2S_chs.exe`
- `patch_chs.dll`
- `patch_chs/pac/update1.ypf`

## 目录说明

- `game/`
  - 原版游戏资源放置目录
- `game_script/original_script/`
  - 正式导出的原文三行文本、机翻 `json`、人名表
- `game_script/translated_script/`
  - 正式译文输入
- `solution/`
  - 正式实现
- `docs/`
  - 结构、验证、使用说明
- `tools/`
  - 外部参考与对照实现，不是正式入口

## 外部工具 / 外部参考

### `tools/YURIS_TOOLS-main`

来源：

- <https://github.com/jyxjyx1234/YURIS_TOOLS/tree/348b30bda623c99782d0fe396068d8801d25096b>

主要用途：

- `YSTB` 文本提取与回填
- 三行文本与 `json` 之间的转换
- `name_define` 相关文件处理
- `GBK` 路径和中文显示相关处理

### `tools/RxYuris-main`

来源：

- <https://github.com/ZQF-ReVN/RxYuris/tree/f3d87c05e621789275e82cf73dfc24b9351d5380>

主要用途：

- `YSTL` 结构解析
- `YSTB` xor key 相关处理
- `YSCM` 命令表解析
- `YSTB/YSTL` 的 v5 结构读取
- `YPF` 索引和部分包处理逻辑参考

### `tools/GPPCLI`

来源：

- <https://github.com/julixian/GalTranslPP/tree/0c7472bf8cdb03b26b23a109ab7eeb04f1d3a0f6>

主要用途：

- 机翻流程参考
- prompt / 字典 / 批处理配置参考
- 批量翻译输入输出约定参考
