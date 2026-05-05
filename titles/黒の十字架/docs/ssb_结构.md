# SSB 结构

## 已确认格式

- 脚本主载体位于 `game/SCRIPT/`
- `CODE.SSB` 是 32 位词流
- `DATA.SSB` 是脚本数据载体
- `DATA.SSB` 当前使用 `XOR 0xAA` 处理
- `CODE.SSB` 中负值词是 VM 操作码，非负值词可能是立即数，也可能是 `DATA.SSB` 的 4 字节对齐偏移

## 已确认记录入口

- `AA13`
  - 当前正式主显示记录入口
- `AC07`
  - 当前正式 UI 文本记录入口
- `AC31`
  - 当前正式 `AC07` 文本簇提交点
- `8309`
  - 当前正式前置视觉链重置点
- `8351`
  - 当前正式前置视觉链条目

## `AA13` 当前正式记录模型

一条 `AA13` 记录当前已确认包含：

- `record_pc`
- `call_opcode_pc`
- `call_arg_slot_order`
- `call_arg_values`
- `slot_values`
- `active_prefix_reset_pc`
- `active_prefix_chain`
- `active_prefix_chain_count`
- `active_prefix_selector_set`
- `active_prefix_visual_mode`
- `base_visual_label_text`
- `base_grd_label_text`
- `overlay_visual_label_text`
- `overlay_grd_label_text`
- `slot_714B5_value`
- `slot_714B3_value`
- `slot_714B2_value`
- `selector`
- `display_name_word_offset`
- `display_name_byte_offset`
- `display_name_text`
- `has_display_name`
- `main_text_word_offset`
- `main_text_byte_offset`
- `main_text`
- `shadow_text_word_offset`
- `shadow_text_byte_offset`
- `shadow_text`
- `message_tag_word_offset`
- `message_tag_byte_offset`
- `message_tag_text`

## `8351` 当前正式记录模型

`active_prefix_chain` 中每条 `8351` 记录当前正式保留：

- `call_pc`
- `call_opcode_pc`
- `call_arg_slot_order`
- `call_arg_values`
- `slot_values`
- `slot_71249_value`
- `slot_71248_value`
- `slot_71246_value`
- `variant_selector_kind`
- `variant_selector_domain`
- `resource_chain_kind`
- `resource_archive_kind`
- `layer_role`
- `prefix_family_kind`
- `label_word_offset`
- `label_byte_offset`
- `label_text`
- `grd_label_text`
- `grd_resource_name`

## `AC07` 当前正式记录模型

### `ac07_ui_records`

每条 `AC07` UI 记录当前正式保留：

- `record_pc`
- `call_opcode_pc`
- `call_arg_slot_order`
- `call_arg_values`
- `slot_values`
- `marker_word_offset`
- `marker_byte_offset`
- `marker_text`
- `text_word_offset`
- `text_byte_offset`
- `text`
- `slot_714C2_value`
- `slot_714C3_value`
- `ui_record_kind`
- `record_kind`

### `ac07_visible_clusters`

每个可见文本簇当前正式保留：

- `record_kind`
- `cluster_size`
- `start_pc`
- `end_pc`
- `commit_pc`
- `markers`
- `choices`

每个 choice 当前正式保留：

- `record_pc`
- `marker_word_offset`
- `marker_byte_offset`
- `marker_text`
- `text_word_offset`
- `text_byte_offset`
- `text`

### `ac07_character_selection_records`

当前定义为：

- 一个 `AC07` 可见簇
- choice 数量不少于 2
- 整个簇共享同一个 `marker_text`

当前正式字段：

- `record_kind`
- `cluster_size`
- `start_pc`
- `end_pc`
- `marker_text`
- `choices`

### `ac07_option_clusters`

当前定义为：

- 一个 `AC07` 可见簇
- choice 数量不少于 2
- 且不是共享单一 `marker_text` 的角色选择簇

当前正式字段：

- `record_kind`
- `cluster_size`
- `start_pc`
- `end_pc`
- `commit_pc`
- `markers`
- `choices`

## 正式文本入口结构

### `text_entries`

当前字段：

- `word_offset`
- `byte_offset`
- `storage_bytes`
- `text`
- `original_text`
- `raw_hex`
- `text_reference_count`
- `main_display_reference_count`
- `main_display_name_reference_count`
- `usage`

### `translation_entries`

当前字段：

- `word_offset`
- `byte_offset`
- `storage_bytes`
- `text`
- `original_text`
- `raw_hex`
- `usage`
- `reference_count`
- `text_reference_count`
- `text_reference_pcs`
- `main_display_reference_count`
- `main_display_reference_pcs`
- `main_display_name_reference_count`
- `main_display_name_reference_pcs`

### `name_related_records`

当前统一入口只包含三类 `record_kind`：

- `aa13_display_name`
- `ac07_character_selection_name`
- `ac07_option_text`

## 目录恢复依据

当前脚本资源正式落位依据：

- `game/SCRIPT/CODE.SSB`
- `game/SCRIPT/DATA.SSB`

当前前置视觉链资源归类依据：

- `8351` 记录中的 `grd_resource_name`
- 当前样本中可与 `GRD` 视觉资源名对上

## 名字恢复依据

当前显示名恢复依据：

- `AA13` 调用参数中的显示名槽位

当前 `AC07` 角色选择名字恢复依据：

- `AC07` 可见簇
- 共享单一 `marker_text`
- 并由 `AC31` 提交闭合

当前 `AC07` 选项文本恢复依据：

- `AC07` 可见簇
- 非角色选择簇
- 并由 `AC31` 提交闭合

## 已确认结论

- `AA13` 参数槽顺序当前由子程序体自动推导
- `8351` 参数槽顺序当前由子程序体自动推导
- `AC07` 标记当前由调用前固定 VM 结构提取
- `AC07` cluster 当前按 `AC07` 连续调用与 `AC31` 提交边界分组
- `slot_71249_value` 当前样本落在 `0 / 1`
- `slot_71248_value` 当前样本恒为 `0`
- `slot_71246_value` 当前样本恒为 `90`
- `slot_714B5_value` 当前样本恒为 `0`
- `slot_714B3_value` 当前样本恒为 `0`
- `selector` 当前样本恒为 `18`
- `slot_714B2_value` 当前样本稳定出现于 `1 / 2 / 3 / 4`

## 未确认结论

- `8351 / 8309` 前置链的完整业务语义
- 全部 `AC07` UI 业务字段语义
- 全部 VM opcode 的完整语义
