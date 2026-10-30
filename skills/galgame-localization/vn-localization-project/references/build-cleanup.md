# 构建前清理接入

每次构建必须先检查并清理本构建器产生的旧构建目录、发布包和完整验证副本，再产生新的完整游戏副本或包。清理只处理显式输出根的直接子目录；原版、译文、静态资源、缓存输入、上传压缩包和原有存档始终保留。

`build_cleanup.py` 是仅依赖 Python 3.10 及以上版本标准库的独立模块，复制到 `solution/build/` 后可直接使用。以下示例代码放入游戏项目根目录的 `main_build.py`，命令均在游戏项目根目录执行。

## 构建器接入

在创建完整副本前调用 `cleanup_previous_outputs`。使用 `generated_output` 独占新建本轮输出目录，将复制和补丁构建放在上下文内；正常或异常退出时都会封存实际文件清单，因此普通复制失败留下的半成品也能在下一轮清理。每次构建使用新的 `run_id`，同一次运行的所有输出共用该值。

```python
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

from solution.build.build_cleanup import cleanup_previous_outputs, generated_output

ROOT = Path(__file__).resolve().parent
BUILDER_ID = "title-localization"

parser = argparse.ArgumentParser()
parser.add_argument("--keep-previous-outputs", action="store_true")
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()
run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
output_roots = [ROOT / "out"]
package = ROOT / "out" / f"package_{run_id}"

cleanup_previous_outputs(
    project_root=ROOT,
    output_roots=output_roots,
    builder_id=BUILDER_ID,
    current_run_id=run_id,
    exclude_paths=[package],
    keep_previous_outputs=args.keep_previous_outputs,
    dry_run=args.dry_run,
)
if args.dry_run:
    raise SystemExit(0)

with generated_output(
    package,
    project_root=ROOT,
    output_roots=output_roots,
    builder_id=BUILDER_ID,
    run_id=run_id,
    kind="package",
    mutable_paths=("savedata_cn/**", "override/patch.log"),
) as package:
    shutil.copytree(ROOT / "game", package, dirs_exist_ok=True)
    # Build and copy the title's patch files inside this context.
# Run smoke tests after the context has sealed the output.
```

`generated_output` 先验证路径，再通过 `mkdir(exist_ok=False)` 精确新建目录；已有目录立即失败，不会被补写标记。输出根可以不存在，由模块在验证后创建。上下文退出时核对目录身份，只封存本轮创建且仍存在的同一目录；已登记的本轮标记经核对后保留，不重复写入。复制和补丁普通异常会原样抛出，不在失败处理期间删除目录；封存同时失败时报告封存错误并保留原构建异常。强杀进程或断电可能来不及封存，这类无标记目录仍按未知内容保留，不能事后仅凭名称补标记。

所有构建写入应在上下文内完成，然后启动冒烟验证。需要提前封存时，可对本轮已新建的精确目录调用一次 `mark_generated_output`；不得使用它认领历史未知目录。需要增量写入当前输出时，整个运行都应传入 `current_run_id` 或 `exclude_paths`。`--dry-run` 只展示计划，构建入口也必须随即结束；`--keep-previous-outputs` 仅用于调试时保留旧输出。

## 认证边界

- 输出目录必须位于显式输出根之下，且是该根的直接子目录。输出根不能是项目根，也不能位于 `game/`、`game_script/`、`solution/`、`patch/`、原有存档或缓存输入等受保护路径中。
- 输出名称仅接受 `package`、`release`、`build`、`validation`、`verify`、`smoke`，或这些前缀后接 `-`、`_` 与英数字标识。输出名称不能带尾随空格、尾随点或路径跳转。
- 目录中的 `.vn-build-output.json` 必须匹配本构建器、项目绝对路径和输出相对路径；复制别处的旧标记不会授权删除。
- JSON 归属标记是可信本地构建流程的约定，不是签名，也不抵抗恶意伪造。构建代码和输出目录必须由可信进程维护；路径与文件清单检查用于防止误删。
- 普通文件使用大小和纳秒修改时间核对，不逐次哈希数 GB 原版资源。普通路径中增加手工文件或修改已登记文件时，保留整个输出目录并报告原因。
- `mutable_paths` 仅接受显式相对文件或以 `/**` 结尾的明确子树，例如 `override/patch.log`、`savedata_cn/**`。禁止 `**`、一般通配符、绝对路径和 `..`。登记这些位置意味着它们属于一次性生成副本，可随该副本清理；不得登记原版存档或用户保留的存档。
- 所有可变位置仍完整检查链接、联接点与其他重解析点。任何危险路径都会中止整批清理，不会先删掉另一部分输出。
- 独立文件、上传压缩包、无标记目录、其他构建器的目录和输入解包缓存不会被清理；禁止把整个 `out/` 或临时目录作为删除目标。
- 执行前先生成并验证完整计划，紧接删除前再次验证。递归删除始终使用同一 Python 进程中的 `shutil.rmtree`，不把路径传给另一种命令行解释器。清理期间不得有其他进程并发改写同一输出目录。

## 独立检查

```powershell
python .\solution\build\build_cleanup.py --project-root . --output-root out --builder-id title-localization --dry-run
python .\solution\build\build_cleanup.py --project-root . --output-root out --builder-id title-localization --keep-previous-outputs
```

`plan_cleanup(...)` 返回不执行删除的 `CleanupPlan`；`execute_cleanup(plan, ...)` 复核后执行。计划中的 `remove` 是拟清理路径元组，`preserve` 记录保留路径及原因。清理范围、链接或计划复核失败时抛出 `CleanupError`，文件系统操作失败时抛出 `OSError`；构建器必须使本次构建失败，不能忽略后继续产生完整副本。

旧版构建器没有标记的目录默认保留。接入时应从新输出开始登记，不得根据目录名称给历史未知内容批量补写标记。新项目生成器不会覆盖已有的清理模块或说明；更新现有项目时应先比较差异。
