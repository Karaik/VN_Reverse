# HXP 结构

## 结论

- `Initial.hxp` 使用 `Him4`
- `DATA/*.hxp` 使用 `Him5`
- 条目头结构一致：
  - `compressed_flag`（`u32le`）
  - `unpacked_size`（`u32le`）
  - `payload`
- `Him5` 原样回封必须保持原始 bucket 分组和 bucket 内记录顺序

## Him4

### 文件头

| 偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| `0x00` | `char[4]` | `magic` | 固定 `Him4` |
| `0x04` | `u32le` | `entry_count` | 条目数量 |
| `0x08` | `u32le[entry_count]` | `entry_offsets` | 条目偏移表 |

### 条目布局

| 条目内偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| `+0x00` | `u32le` | `compressed_flag` | `0`=未压缩，非 `0`=压缩 |
| `+0x04` | `u32le` | `unpacked_size` | 解压后大小 |
| `+0x08` | `byte[]` | `payload` | 压缩或未压缩数据 |

### 回归

- 样本：`game/Initial.hxp`
- 结果：`unpack -> repack` 字节一致

## Him5

### 文件头

| 偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| `0x00` | `char[4]` | `magic` | 固定 `Him5` |
| `0x04` | `u32le` | `bucket_count` | bucket 数量 |
| `0x08` | `bucket_count * 8` | `bucket_table` | 每个 bucket 的 `size + offset` |

### bucket 表项

| 表项内偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| `+0x00` | `u32le` | `bucket_size` | bucket 数据块大小 |
| `+0x04` | `u32le` | `bucket_offset` | bucket 数据块偏移 |

### bucket 记录

| 记录内偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| `+0x00` | `u8` | `record_len` | 记录总长度 |
| `+0x01` | `u32be` | `entry_offset` | 物理条目偏移 |
| `+0x05` | `char[]` | `name` | ASCII 名称，以 `0x00` 结束 |

bucket 数据块以单字节 `0x00` 结束。

### 条目块

| 条目内偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| `+0x00` | `u32le` | `compressed_flag` | `0`=未压缩，非 `0`=压缩 |
| `+0x04` | `u32le` | `unpacked_size` | 解压后大小 |
| `+0x08` | `byte[]` | `payload` | 压缩或未压缩数据 |

### 原样回封约束

- 保留原始 `bucket_index`
- 保留原始 `bucket_order`
- 不按文件名重排
- bucket 内 `entry_offset` 按 `u32be` 回写

### 回归

- 样本：`game/DATA/Masq_scn.hxp`
- 结果：
  - 原样 `unpack -> repack` 字节一致
  - 非压缩重建后，抽样条目再解包内容一致

## 名称哈希

`Him5` 通过可执行文件里的 `0x408CC0` 哈希将条目名映射到 bucket。

```text
value = 0
factor = 1
for signed_byte in name:
  value ^= factor * signed_byte
  factor += 499
return value ^ (value >> 11)
```

实现位置：`solution/common/hxp.py`。

## 压缩

当 `compressed_flag != 0` 时，payload 走可执行文件 `0x408520` 解压流程。

当前状态：

- 解压：已完成
- 压缩条目解包：已完成
- 重压缩：已完成（对齐 `0x407EC0`）
- 可编辑回封路径：
  - 非压缩重建（`--rebuild-uncompressed`）
  - 压缩重建（`--rebuild-compressed`）
- 已验证样本：`game/DATA/Masq_scn.hxp` 在压缩重建模式可字节一致

## Checklist

- [x] `Him4` 结构确认并实现
- [x] `Him5` 结构确认并实现
- [x] `Him4/Him5` 原样回封字节一致
- [x] 名称哈希对齐 `0x408CC0`
- [x] `0x408520` 解压实现
- [x] `0x407EC0` 重压缩实现

全局进度见 [`checklist.md`](./checklist.md)。
