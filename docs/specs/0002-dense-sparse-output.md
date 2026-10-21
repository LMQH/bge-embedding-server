# SPEC-0002：稠密与稀疏双路输出契约

- 状态：已确认，2026-10-21。
- 关联 PRD 与需求 ID：[PRD-0002](../prd/0002-dense-sparse-embeddings.md)，REQ-013～REQ-019。
- 关联 ADR：[ADR-0005](../adr/0005-native-sparse-head.md)、[ADR-0002](../adr/0002-bge-m3-mlx.md)；dense 基础契约见 [SPEC-0001](0001-embedding-inference.md)。
- 确认依据：2026-10-21 用户确认验证深度为 M4 smoke 与 8192 tokens，并要求按推荐方案推进改造。接口字段、token id 键和全部正权重按推荐默认值定案；用户未逐项否决，后续调整按文档变更流程更新。

## 范围

在现有 `POST /v1/embeddings` 上增加可选 sparse 输出。dense 的模型、池化、维度、归一化、字段和默认行为保持 [SPEC-0001](0001-embedding-inference.md) 不变；sparse 与 dense 共享同一次模型前向。批处理、鉴权、队列、请求上限、错误类别、usage 和日志安全规则沿用 SPEC-0001。

不包含：ColBERT / multi-vector、BM25 / SPLADE / 第二模型、服务端融合排序、检索、向量库、分词或检索效果调参。

## 输入、输出与行为

### 请求

请求仍为 JSON，允许字段在 `model`、`input`、`encoding_format` 基础上增加可选的 `return_sparse`。

| 字段 | 规则 |
| --- | --- |
| model | 必填，仍只接受 `"bge-m3"` |
| input | 必填，单个字符串或非空字符串数组；规则不变 |
| encoding_format | 可选，默认 `"float"`；仍只接受 `"float"` |
| return_sparse | 可选 JSON 布尔值，默认 `false`；不做类型转换；非布尔值返回 400，`param` 为 `return_sparse` |

未知字段仍整单拒绝。`return_sparse` 的校验发生在输入文本校验之前；任一字段无效时整批失败，不开始模型推理。

### 稀疏计算

- 对每条文本，使用与 dense 相同的 `last_hidden_state`，计算逐位置权重 `ReLU(W·h + b)`。
- 按 token id 聚合：同一 token 多次出现取最大权重。
- 排除 tokenizer 的全部特殊 token id；只保留 `weight > 0` 的项。
- 不做 L2 归一化、长度归一化、IDF、top-k 或阈值截断。
- key 为十进制 token id 字符串，例如 `"81492"`；与官方 BGE-M3 `lexical_weights` 的 id 形式一致，避免 decode 字符串的同键碰撞。
- value 为有限正数，使用 JSON 数字；不返回 token 文本。
- 输出顺序按 token 首次出现；JSON 对象顺序不构成语义。
- 正常非空文本预期至少有一个正权重项；若稀疏头输出全部非正，返回空对象而不是错误。调用方不得假设一定非空。

### 响应

`return_sparse` 为 `false` 或省略时，响应与 SPEC-0001 完全一致，不出现 `sparse` 字段。

`return_sparse` 为 `true` 时，`data` 中每个条目增加 `sparse` 对象：

```json
{
  "object": "list",
  "model": "bge-m3",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.0123, -0.0456, "..."],
      "sparse": {"81492": 0.3436, "24471": 0.2400}
    }
  ],
  "usage": {"prompt_tokens": 10, "total_tokens": 10}
}
```

dense 仍为恰好 1024 个有限数值、L2 归一化；批量按输入顺序；`index` 从 0 开始。`usage` 只统计输入 token，不因 sparse 改变。

### 失败行为

| HTTP | code | 场景 |
| --- | --- | --- |
| 400 | invalid_request | `return_sparse` 不是布尔值；其他请求校验失败仍按 SPEC-0001 |
| 400 | input_too_long / batch_limit_exceeded | 沿用 SPEC-0001 |
| 401 | invalid_api_key | 沿用 SPEC-0001 |
| 413 | request_too_large | 沿用 SPEC-0001 |
| 429 | queue_full / queue_timeout | 沿用 SPEC-0001 |
| 503 | model_unavailable | 沿用 SPEC-0001 |
| 500 | inference_failed | 模型异常、dense 或 sparse 数值不符合契约 |

sparse 计算失败时整批返回 500，不返回部分结果。错误 message 不包含正文、权重、Key 或本地路径。

## 约束

- 模型资产：本地模型目录必须包含官方 BGE-M3 稀疏头转换出的 `sparse_linear.safetensors`；缺失、形状错误或无法加载时服务启动失败，不静默降级为空 sparse。
- 来源固定：官方 BGE-M3 检查点固定 revision，转换文件校验 SHA-256；运行时不下载、不训练、不修改主体量化。
- 无新增运行时依赖；不引入 Torch 或第二个模型进程。
- 资源沿用现有 8192 tokens / 条、32768 tokens / 请求、16 条 / 批、20 个位置；sparse 不改变队列与并发模型。
- 性能：稀疏头是每 token 一次 1024 维投影，不得引入明显延迟或内存回退；以 M4 8192 tokens 实测为准。
- 隐私：不持久化输入或输出；日志不记录正文、dense/sparse 权重或 Key，只允许条数、耗时、状态等安全元数据。
- 兼容性：`return_sparse` 与 `sparse` 是扩展，不是 OpenAI 标准字段；高层 SDK 可能需要原始 HTTP 或额外字段透传。默认 dense-only 调用不受影响。

## 验收场景

| 场景 ID | 需求 ID | 前置条件与输入 | 预期结果 | 验证方式 |
| --- | --- | --- | --- | --- |
| AC-201 | REQ-013、REQ-015 | 不传或传 `return_sparse=false` 的中英文单条/批量 | 200；无 `sparse` 字段；dense 1024 有限且 L2 归一化；usage 与顺序不变 | 单元测试与 M4 smoke |
| AC-202 | REQ-013、REQ-016 | `return_sparse=true`，中文与英文单条 | 200；sparse 非空；key 为数字字符串；value 有限且 >0；特殊 token 不出现；dense 有效 | 真实本地推理与 M4 smoke |
| AC-203 | REQ-013、REQ-016 | `return_sparse=true`，中英混合批量 | 每项都有独立 sparse；顺序与 index 正确；usage 为总 token 数 | 单元测试与 M4 smoke |
| AC-204 | REQ-015 | `return_sparse` 为字符串、数字、null、数组或对象 | 400 `invalid_request`，`param=return_sparse`，不发生推理 | 单元测试 |
| AC-205 | REQ-017 | 8192 tokens，`return_sparse=true` | 200；usage 为 8192；dense 与 sparse 有效；无 OOM；记录峰值内存与耗时 | M4 实测 |
| AC-206 | REQ-014、REQ-017 | 稀疏头缺失或损坏 | 服务启动失败并给出安全错误；healthz 不可用；不返回空 sparse 降级 | 本地负向检查 |
| AC-207 | REQ-015 | 同一输入在改造前后各取 dense | 余弦 ≥ 0.9999；预期逐位一致 | 本地真实推理 |
| AC-208 | REQ-018 | 发送含哨兵文本的请求并检查日志 | 日志不含正文、权重、Key 或底层异常 | 现有日志测试 |
| AC-209 | REQ-019 | 文档与索引 | SPEC、PLAN、连接说明、HANDOFF 与索引一致 | 审阅与链接检查 |

## 未决事项与关联计划

- 无阻塞性未决项。8192 tokens 的 M4 实测与部署证据记录在 [PLAN-0007](../plans/0007-dense-sparse-output.md)。
- 与官方 fp16 全模型的数值对照不在本轮范围；8bit encoder + 官方 fp16 头的质量差异作为残余风险记录。
