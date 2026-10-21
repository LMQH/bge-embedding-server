# 文档中心

本项目采用 SDD（Specification-Driven Development，规格驱动开发）。Spec 将需求转化为可验证的行为契约，是实现、测试与验收的直接依据；PRD、ADR 和 Plan 为规格提供需求来源、决策约束与执行记录。项目进度与交接见 [HANDOFF.md](../HANDOFF.md)，文档中的“待确定”不代表默认选择。

## SDD 开发理念

开发围绕“确认规格 → 制定计划 → 实现 → 按规格验证”迭代。关键是用明确的输入、输出、边界、失败行为与验收场景指导代码，而非以文档数量或代码完成作为需求满足的证明。方法依据见 [ADR-0001](adr/0001-specification-driven-development.md)。

规格只覆盖当前确认的范围，无需预先穷尽未来设计。需求变化时先调整 PRD 和受影响的 Spec，必要时补充 ADR，确认后再更新 Plan 与实现；发现代码与规格冲突时先澄清预期行为。验证结果逐项回到 Spec 的场景或章节，未验证项保持明确标注。纯文档、Git 等不改变服务行为的工作按任务目标检查即可，无需为流程补写行为规格。

## 文档职责与索引

| 类型 | 回答的问题 | 当前文档 | 模板 |
| --- | --- | --- | --- |
| PRD | 为什么做、为谁做、范围与成功标准是什么 | [PRD-0001：嵌入推理服务](prd/0001-embedding-service.md) | [PRD 模板](prd/_template.md) |
| ADR | 为什么选择某种方案，考虑过哪些替代方案 | [ADR-0001：SDD 开发理念](adr/0001-specification-driven-development.md)、[ADR-0002：BGE-M3 与 MLX](adr/0002-bge-m3-mlx.md)、[ADR-0003：原生 Python 与 conda](adr/0003-native-python-runtime.md)、[ADR-0004：首版基本冒烟](adr/0004-minimal-verification.md) | [ADR 模板](adr/_template.md) |
| Spec | 系统必须表现出什么可验证行为 | [SPEC-0001：嵌入推理契约](specs/0001-embedding-inference.md) | [Spec 模板](specs/_template.md) |
| Plan | 按什么顺序实施，如何验证与交付 | [PLAN-0001：项目初始化与设计收敛](plans/0001-project-foundation.md)、[PLAN-0002：实现轻量嵌入服务](plans/0002-minimal-service.md)、[PLAN-0003：长输入注意力修复](plans/0003-fused-attention.md)、[PLAN-0004：扩充等待队列](plans/0004-queue-capacity.md)、[PLAN-0005：统一文件配置](plans/0005-file-configuration.md)、[PLAN-0006：接口性能测试](plans/0006-performance-test.md) | [Plan 模板](plans/_template.md) |
| Handoff | 当前进展、待定事项、阻塞与下一步是什么 | [项目进度与交接](../HANDOFF.md) | — |
| 使用说明 | 如何连接和调用服务 | [推理服务连接与使用说明](service-connection.md) | — |
| 参考资料 | 外部资料、技术事实与待验证事项是什么 | [MLX 框架、模型格式与官方资料](references/0001-mlx-framework-and-model-formats.md)、[源码接入与代码结构](references/0002-source-layout.md) | — |

## 工作流程

1. 在 PRD 中澄清目标、范围、需求编号与验收标准。
2. 涉及重要架构选择时创建 ADR，记录上下文、备选项、理由与后果；没有架构决策的改动无需强行创建 ADR。
3. 在 Spec 中将需求转换为接口、边界行为和验收场景，引用相关 PRD 与 ADR，记录确认依据；受影响的行为规格确认后再进入实现。
4. 在 Plan 中将已确认的 Spec 拆成实施步骤、依赖和验证方式，每项关联对应场景或章节；受未决事项影响的步骤保持待定。
5. 按 Spec 与 Plan 做最小实现，使用对应验收场景验证，将实际命令、结果和未验证项记录到 Plan。修复 Bug 先复现，并依据已有规格判断缺陷；预期行为改变时先修订规格。
6. 核对规格、代码和验证证据一致后交付，同步 HANDOFF 的日期、进度与下一步摘要。SDD 不扩大 [ADR-0004](adr/0004-minimal-verification.md) 约定的验证范围，不将原已后置的复杂评测恢复为必做项。

文档可以迭代推进，不要求所有设计一次性完成。若上游存在影响当前工作的未决问题，先澄清该问题，再推进依赖它的实现。

## 命名、状态与维护

- 各类文档分别从 `0001` 连续编号，文件名采用 `NNNN-short-title.md`，文档 ID 分别使用 `PRD-`、`ADR-`、`SPEC-`、`PLAN-` 前缀；不同类型不要求编号一一对应。
- `_template.md` 仅作复制起点，不属于正式编号文档。新增文档时补充本页索引，用相对链接关联上下游。
- PRD 与 Spec 使用“草案 / 已确认 / 已废弃”；Plan 使用“草案 / 进行中 / 已完成 / 已取消”；ADR 使用“提议 / 已接受 / 已废弃 / 已替代”。
- “已确认”与“已接受”必须有明确依据，记录确认来源；不能因为文件已创建就自动确认。待确定项不得作为实现承诺。
- PRD 中使用稳定的需求 ID（例如 `REQ-001`），Spec 中的验收场景引用需求 ID，Plan 的工作项引用 Spec 场景或章节。
- 已接受 ADR 保留原始决策内容。决策改变时新增 ADR，并在旧记录中标注替代状态与链接，不覆写历史理由。
- PRD 维护需求事实，ADR 维护决策理由，Spec 维护行为契约，Plan 维护执行状态；通过引用关联，避免重复维护同一事实。
- 根目录 [README](../README.md) 仅保留简洁总览与导航，[AGENTS.md](../AGENTS.md) 是协作约定，[HANDOFF.md](../HANDOFF.md) 维护项目级进度与交接摘要，并链接 Plan 中的详细任务与验证证据；交接时覆盖过时摘要，历史记录留在 Plan。本目录不记录虚构的测试、部署或运行结果。
