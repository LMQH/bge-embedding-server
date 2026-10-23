# 术语表

更新日期：2026-10-23。覆盖本文档与接口中的项目自定术语；通用概念（如 transformer、tokenize）不在此列。

| 术语 | 含义 |
| --- | --- |
| dense | 每条输入一个 1024 维浮点向量，CLS 池化 + L2 归一化，用于语义相似度 |
| sparse | 每条输入一组 token 级正权重（`ReLU(W·h + b)`，同 token 取最大），键为十进制 token id 字符串；用于词面 / BM25 风格混合检索。契约见 [SPEC-0002](../specs/0002-dense-sparse-output.md) |
| 稀疏头 | 产生 sparse 输出的小投影层（`sparse_linear.safetensors`），是服务启动前置；见 [模型说明](../../models/README.md) |
| 执行位 | 同时执行模型前向的请求槽位，固定为 1（单 worker 单模型串行） |
| 等待位 | 执行位之外的有界 FIFO 等待槽位，默认 19；等待超 30 秒返回 429 `queue_timeout` |
| 批内合批 | 同一请求内的未命中文本按 token 长度分桶、右 padding 后合并为一次前向。见 [ADR-0007](../adr/0007-batch-inference.md) |
| 跨请求微合批 | 等待队列中兼容请求（同 `return_sparse`）按最多 15ms 窗口合并为一次前向，上限 16 条 / 8192 token。见 [ADR-0008](../adr/0008-cross-request-micro-batching.md) |
| 合批 padding 预算 | 每组合批后允许的 padding token 上限（8192）；超预算的单条单独执行 |
| FP16 attention | 注意力 Q/K/V 以半精度计算以利用 Apple GPU；CLS、归一化与 sparse 头仍为 FP32 |
| 融合注意力内核 | Metal 上的 fused attention 实现，配合逐层 `mx.eval` 控制峰值内存。背景见 [PLAN-0003](../plans/0003-fused-attention.md) |
| 结果缓存 | 进程内按 token 序列 + `return_sparse` 为键的 LRU，容量按估算字节计；重启即清空。见 [SPEC-0003](../specs/0003-result-cache.md) |
| 全命中请求 | 批内所有文本缓存命中，直接返回、不占用执行位或等待位 |
| `wait_ms` / `exec_ms` | 请求日志字段：排队等待耗时 / 推理执行耗时 |
| `ahead` / `dedup` | 入队瞬间前方任务数 / 请求内去重掉的重叠文本数 |
| 8bit 权重 | MLX 量化的 BGE-M3 快照（`mlx-community/bge-m3-mlx-8bit`），与官方 fp16 不保证逐位一致 |
