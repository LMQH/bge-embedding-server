# 文档中心

SDD（Specification-Driven Development）：Spec 是可验证的行为契约，PRD 提供需求来源，ADR 记录决策，Plan 记录执行与验证。流程规则见 [AGENTS.md](../AGENTS.md) 与 [ADR-0001](adr/0001-specification-driven-development.md)。

## 阅读入口

- 调用服务 → [连接与使用说明](service-connection.md)
- 部署自建 → [README 快速开始](../README.md)、[部署说明](../deploy/README.md)
- 修改代码 → [SPEC-0001](specs/0001-embedding-inference.md)、[源码结构](references/0002-source-layout.md)
- 设计理由 → 下表 ADR
- 术语 → [术语表](references/0004-glossary.md)

## 索引

| 类型 | 文档 |
| --- | --- |
| PRD | [0001 嵌入推理服务](prd/0001-embedding-service.md) · [0002 双路输出](prd/0002-dense-sparse-embeddings.md) · [0003 结果缓存](prd/0003-result-cache.md) · [0004 请求观测与去重](prd/0004-request-optimizations.md) |
| ADR | [0001 SDD](adr/0001-specification-driven-development.md) · [0002 BGE-M3 与 MLX](adr/0002-bge-m3-mlx.md) · [0003 原生 Python](adr/0003-native-python-runtime.md) · [0004 最小验证](adr/0004-minimal-verification.md) · [0005 原生稀疏头](adr/0005-native-sparse-head.md) · [0006 进程内缓存](adr/0006-in-memory-result-cache.md) · [0007 批内合批](adr/0007-batch-inference.md) · [0008 跨请求微合批](adr/0008-cross-request-micro-batching.md) |
| Spec | [0001 嵌入推理](specs/0001-embedding-inference.md) · [0002 双路输出](specs/0002-dense-sparse-output.md) · [0003 结果缓存](specs/0003-result-cache.md) · [0004 观测与去重](specs/0004-request-observability-and-dedup.md) |
| Plan | [完整索引](plans/README.md) |
| 其他 | [进度与交接](../HANDOFF.md) · [连接与使用](service-connection.md) · [MLX 与模型格式](references/0001-mlx-framework-and-model-formats.md) · [源码结构](references/0002-source-layout.md) · [局限性](references/0003-service-limitations.md) · [术语表](references/0004-glossary.md) |

## 约定

- 文件名 `NNNN-short-title.md`，按类型各自递增；编号永久保留。`_template.md` 不是正式文档。
- 状态：PRD / Spec 用“草案 / 已确认 / 已废弃”，Plan 用“草案 / 进行中 / 已完成 / 已取消”，ADR 用“提议 / 已接受 / 已废弃 / 已替代”。
- 需求用 `REQ-NNN`，Spec 场景引用需求 ID，Plan 引用 Spec 场景；Plan 保留执行依据与验证结论，不因完成或取消删除。
- 原始测试数据与脚本归 `tests/`，Plan 链接引用；模型权重、缓存、凭据不入库。
- 改文档后检查相对链接，含删除文件后的引用清理。
