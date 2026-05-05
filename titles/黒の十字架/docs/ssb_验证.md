# SSB 验证

## 正式验证入口

```powershell
python .\regression_test.py
```

## 当前总验证覆盖

- `CODE.SSB` unchanged roundtrip
- `DATA.SSB` unchanged roundtrip
- 批量反编译可发现脚本目录并镜像导出
- 批量回编可发现 `script.json` 并镜像回编
- 单样本下批量回编结果与原始脚本一致
- `AA13` 正文可导出
- `AA13` 显示名可导出
- `AA13` 显示名可回写
- `AA13` 正文可回写
- `AA13` 正文可变长回写
- `gbk` 目标编码正文可回写
- 目标编码回写后可再次反编译恢复文本
- `AC07` 角色选择簇可回写
- `AC07` 选项簇可回写
- `name_related_records.json` 统一回写可用

## 当前总验证证明了什么

- 反编译与回编基础链路可跑通
- 批量入口不是空壳
- `AA13` 正文和显示名已经进入正式文本链
- `AC07` 角色选择簇与选项簇已经进入正式结构化回写链
- `name_related_records.json` 已经是正式统一入口之一
- 指定目标编码写回链已经可用
- 变长回写链已经可用

## 当前总验证没有证明什么

- 没有证明 `8351 / 8309` 前置链业务语义已经完整逆完
- 没有证明全部 `AC07` UI 字段语义已经完整逆完
- 没有证明全部 VM opcode 语义已经完整逆完
- 没有证明资源层独立回封

## 当前补充实测

除总验证外，当前还已补做结构化写回实测：

- `name_related_records -> ac07_character_selection_name -> 回编 -> 再反编译`
  - 已通过
- `ac07_option_clusters -> 回编 -> 再反编译`
  - 已通过
- `ac07_character_selection_records -> 回编 -> 再反编译`
  - 已通过

## 当前验证边界

- 当前验证关注的是：
  - 正式反编译入口
  - 正式回编入口
  - 正式文本入口
  - 正式结构化写回入口
- 当前验证不把旧的文本特征匹配、硬编码标签识别当作验收内容
