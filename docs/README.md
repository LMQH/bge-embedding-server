# 文档中心

本项目采用 SDD（Specification-Driven Development，规格驱动开发）。Spec 将需求转化为可验证的行为契约，是实现、测试与验收的直接依据；PRD、ADR 和 Plan 为规格提供需求来源、决策约束与执行记录。项目进度与交接见 [HANDOFF.md](../HANDOFF.md)，文档中的“待确定”不代表默认选择。

**按需阅读路径**

- 只想调用服务 → [连接与使用说明](service-connection.md)
- 要部署或自建 → 根目录 [README 快速开始](../README.md) 与 [部署说明](../deploy/README.md)
- 要修改代码 → [SPEC-0001](specs/0001-embedding-inference.md) 与 [源码说明](references/0002-source-layout.md)
- 想了解“为什么这样设计” → 下表 ADR 一列
- 术语（执行位、合批、sparse 键等）→ [术语表](references/0004-glossary.md)

## SDD 开发理念

开发围绕“确认规格 → 制定计划 → 实现 → 按规格验证”迭代。关键是用明确的输入、输出、边界、失败行为与验收场景指导代码，而非以文档数量或代码完成作为需求满足的证明。方法依据见 [ADR-0001](adr/0001-specification-driven-development.md)。

规格只覆盖当前确认的范围，无需预先穷尽未来设计。需求变化时先调整 PRD 和受影响的 Spec，必要时补充 ADR，确认后再更新 Plan 与实现；发现代码与规格冲突时先澄清预期行为。验证结果逐项回到 Spec 的场景或章节，未验证项保持明确标注。纯文档、Git 等不改变服务行为的工作按任务目标检查即可，无需为流程补写行为规格。

## 文档职责与索引

| 类型 | 回答的问题 | 当前文档 | 模板 |
| --- | --- | --- | --- |
| PRD | 为什么做、为谁做、范围与成功标准是什么 | [PRD-0001：嵌入推理服务](prd/0001-embedding-service.md)、[PRD-0002：稠密与稀疏双路嵌入输出](prd/0002-dense-sparse-embeddings.md)、[PRD-0003：嵌入结果缓存](prd/0003-result-cache.md)、[PRD-0004：请求观测、请求内去重与过载提示](prd/0004-request-optimizations.md) | [PRD 模板](prd/_template.md) |
| ADR | 为什么选择某种方案，考虑过哪些替代方案 | [ADR-0001：SDD 开发理念](adr/0001-specification-driven-development.md)、[ADR-0002：BGE-M3 与 MLX](adr/0002-bge-m3-mlx.md)、[ADR-0003：原生 Python 与 conda](adr/0003-native-python-runtime.md)、[ADR-0004：首版基本冒烟](adr/0004-minimal-verification.md)、[ADR-0005：稀疏输出采用 BGE-M3 原生稀疏头](adr/0005-native-sparse-head.md)、[ADR-0006：进程内结果缓存](adr/0006-in-memory-result-cache.md)、[ADR-0007：单 worker 批内合批](adr/0007-batch-inference.md)、[ADR-0008：跨请求微合批](adr/0008-cross-request-micro-batching.md) | [ADR 模板](adr/_template.md) |
| Spec | 系统必须表现出什么可验证行为 | [SPEC-0001：嵌入推理契约](specs/0001-embedding-inference.md)、[SPEC-0002：稠密与稀疏双路输出契约](specs/0002-dense-sparse-output.md)、[SPEC-0003：嵌入结果缓存契约](specs/0003-result-cache.md)、[SPEC-0004：请求观测、请求内去重与过载提示契约](specs/0004-request-observability-and-dedup.md) | [Spec 模板](specs/_template.md) |
| Plan | AI 按什么依据与步骤执行，如何验收，实际结果是什么 | [完整 Plan 索引（PLAN-0001～PLAN-0014）](plans/README.md) | [Plan 模板](plans/_template.md) |
| Handoff | 当前进展、待定事项、阻塞与下一步是什么 | [项目进度与交接](../HANDOFF.md) | — |
| 使用说明 | 如何连接和调用服务 | [推理服务连接与使用说明](service-connection.md) | — |
| 参考资料 | 外部资料、技术事实与待验证事项是什么 | [MLX 框架、模型格式与官方资料](references/0001-mlx-framework-and-model-formats.md)、[源码接入与代码结构](references/0002-source-layout.md)、[当前服务的局限性](references/0003-service-limitations.md)、[术语表](references/0004-glossary.md) | — |

## 工作流程

1. 在 PRD 中澄清目标、范围、需求编号与验收标准。
2. 涉及重要架构选择时创建 ADR，记录上下文、备选项、理由与后果；没有架构决策的改动无需强行创建 ADR。
3. 在 Spec 中将需求转换为接口、边界行为和验收场景，引用相关 PRD 与 ADR，记录确认依据；受影响的行为规格确认后再进入实现。
4. 在 Plan 中将已确认的 Spec 拆成实施步骤、依赖和验证方式，每项关联对应场景或章节；受未决事项影响的步骤保持待定。
5. 按 Spec 与 Plan 做最小实现，使用对应验收场景验证，将实际命令、结果和未验证项记录到 Plan。修复 Bug 先复现，并依据已有规格判断缺陷；预期行为改变时先修订规格。
6. 核对规格、代码和验证证据一致后交付，同步 HANDOFF 的日期、进度与下一步摘要。SDD 不扩大 [ADR-0004](adr/0004-minimal-verification.md) 约定的验证范围，不将原已后置的复杂评测恢复为必做项。

文档可以迭代推进，不要求所有设计一次性完成。若上游存在影响当前工作的未决问题，先澄清该问题，再推进依赖它的实现。

## 命名、状态与维护

- 各类文档分别从 `0001` 按创建顺序递增编号，文件名采用 `NNNN-short-title.md`，文档 ID 分别使用 `PRD-`、`ADR-`、`SPEC-`、`PLAN-` 前缀；不同类型不要求编号一一对应。已有编号永久保留，不重新编号或复用。
- `_template.md` 仅作复制起点，不属于正式编号文档。新增文档时补充本页索引，用相对链接关联上下游。
- PRD 与 Spec 使用“草案 / 已确认 / 已废弃”；Plan 使用“草案 / 进行中 / 已完成 / 已取消”；ADR 使用“提议 / 已接受 / 已废弃 / 已替代”。
- “已确认”与“已接受”必须有明确依据，记录确认来源；不能因为文件已创建就自动确认。待确定项不得作为实现承诺。
- PRD 中使用稳定的需求 ID（例如 `REQ-001`），Spec 中的验收场景引用需求 ID，Plan 的工作项引用 Spec 场景或章节。
- 已接受 ADR 保留原始决策内容。决策改变时新增 ADR，并在旧记录中标注替代状态与链接，不覆写历史理由。
- PRD 维护需求事实，ADR 维护决策理由，Spec 维护行为契约，Plan 保留 AI 执行的依据、任务步骤、验收标准、执行记录与验证结论；通过引用关联，避免重复维护同一事实。
- Plan 是执行留档，不因已完成、已取消、属于过程性工作或没有测试数据而删除。状态变更补记时间与依据，保留原有执行记录；历史命令与旧契约不作为当前操作指令。
- `docs/plans/` 仅存计划文档与模板。测试脚本与需入库的原始测试数据归 `tests/`，例如基准工具在 `tests/benchmarks/`、PLAN-0012 历史结果在 `tests/benchmarks/evidence/0012/`；Plan 保留验证摘要并链接原始证据。模型权重、缓存、凭据和私有运行文件仍不入库。
- 文档变更时检查本文档内相对链接全部可解析（含新增与删除文件后的引用清理）；定版或批量删改后应全库复查一遍。
- 根目录 [README](../README.md) 仅保留简洁总览与导航，[AGENTS.md](../AGENTS.md) 是协作约定，[HANDOFF.md](../HANDOFF.md) 维护项目级进度与交接摘要，并链接 Plan 中的详细任务与验证证据；交接时覆盖过时摘要，历史记录留在 Plan。本目录不记录虚构的测试、部署或运行结果。
