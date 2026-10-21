# ADR-0005：稀疏输出采用 BGE-M3 原生稀疏头

## 状态

已接受，2026-10-21。依据：用户确认 [PRD-0002](../prd/0002-dense-sparse-embeddings.md) 的范围变更，并选定“方案 A：BGE-M3 稀疏头”。

## 上下文

PRD-0002 要求一次请求同时返回 dense 与 sparse。可选路径包括：BM25（依赖语料统计和独立索引）、SPLADE 等第二稀疏模型（额外权重、内存与延迟）、调用方侧 BM25（不满足同请求输出），以及 BGE-M3 自带的稀疏头。

BGE-M3 的 dense 与 sparse 共享同一 encoder；sparse 头只作用于已经计算出的 last_hidden_state。当前本地 8bit 快照在转换时没有包含该头，但官方 BGE-M3 检查点单独提供该头，体量很小，可以补入现有模型目录，而不重新转换模型或加载第二个模型。

## 决策

- sparse 词权重来自 BGE-M3 原生稀疏头，与 dense 使用同一次前向的 hidden state；不引入 BM25、SPLADE 或第二个模型。
- 稀疏头作为独立的模型资产，从官方 BGE-M3 检查点固定 revision 获取并校验完整性；不重新训练、不修改主体量化。
- 服务在同一个嵌入请求中按调用方选择返回两路；dense 的既有语义和默认行为保持不变。接口字段与稀疏表示由 [SPEC-0002](../specs/0002-dense-sparse-output.md) 定义。
- 不实现服务端融合、检索或语料统计；调用方负责混合检索与排序。

## 替代方案

- BM25：需要维护语料统计和独立索引，且不是单次模型前向的一部分；不满足“一次请求、同一模型”的目标。未采用。
- SPLADE 或其他学习型稀疏模型：需要第二个模型，增加内存、延迟与权重管理；与 M4 16GB 的约束不符。未采用。
- 调用方侧 BM25 或稀疏模型：服务不提供 sparse，无法满足 PRD-0002。未采用。
- 仅 dense：不满足 PRD-0002。未采用。

## 后果

- 额外计算只有稀疏头的一次投影，相对 24 层 encoder 可忽略；模型内存增加一个极小的头资产。
- sparse 是 XLM-R subword 级学习权重，不是 BM25；没有 IDF、长度归一化或语料统计，查询与文档对称。
- 8bit encoder 加官方 fp16 头不保证与官方 fp16 全模型逐位一致；本决策不承诺检索效果提升，验证按 [ADR-0004](0004-minimal-verification.md) 保持最小范围。
- 调用方需要支持稀疏向量的索引或存储；服务不负责融合与检索。
- ColBERT / multi-vector 不在本决策范围内，仍不纳入。

## 关联

- [PRD-0002](../prd/0002-dense-sparse-embeddings.md)
- [ADR-0002](0002-bge-m3-mlx.md)
- [SPEC-0002](../specs/0002-dense-sparse-output.md)
- [PLAN-0007](../plans/0007-dense-sparse-output.md)
