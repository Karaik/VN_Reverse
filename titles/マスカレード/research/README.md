# research 入口

这里存放 `マスカレード` 的研究型入口脚本。

这些脚本没有被删除，只是从项目根目录移走，避免继续占据主线入口：

- `main_branch_audit.py`
- `main_branch_overview.py`
- `main_disasm_full.py`
- `main_dump_text_full.py`
- `main_switch_audit.py`
- `main_switch_seed_sweep.py`
- `main_var16_writers.py`

当前主线请优先使用：

- `main_unpack.py`
- `main_repack.py`
- `main_probe.py`
- `main_disasm.py`
- `main_dump_text.py`
- `regression_test.py`

## 当前定位

- 这些研究型入口仍然可以回看和复跑。
- 但它们不再作为静态文本写回主线的默认入口。
- 历史研究快照只保留本地备份，不作为远端默认入口。
