# Plan 执行留档索引

Plan 记录 AI 执行的依据、任务步骤、验收标准、执行记录与验证结论。执行前制定，执行后回填；完成或取消后保留文件和原编号，不以有无测试数据作为保留标准。新增计划使用历史最大编号加一，不重新编号或复用。

本目录仅保存计划文档、索引和模板。测试脚本与原始测试数据归 `tests/`，计划通过相对链接引用；当前项目进展统一见 [HANDOFF](../../HANDOFF.md)。

| 编号 | 计划 | 归档状态与说明 |
| --- | --- | --- |
| PLAN-0001 | [项目初始化与设计收敛](0001-project-foundation.md) | 已完成；从 Git 恢复历史记录 |
| PLAN-0002 | [实现轻量嵌入服务](0002-minimal-service.md) | 已完成；从 Git 恢复历史记录 |
| PLAN-0003 | [修复长输入注意力内存占用](0003-fused-attention.md) | 已完成 |
| PLAN-0004 | [扩充等待队列](0004-queue-capacity.md) | 已完成（本地实现与验证）；从 Git 恢复历史记录 |
| PLAN-0005 | [统一文件配置](0005-file-configuration.md) | 已完成；从 Git 恢复历史记录 |
| PLAN-0006 | [接口性能测试](0006-performance-test.md) | 已完成 |
| PLAN-0007 | [稠密与稀疏双路输出实施](0007-dense-sparse-output.md) | 已完成；部署依据以有日期的补记关联 |
| PLAN-0008 | [仓库连接信息脱敏与历史清理](0008-repository-privacy.md) | 已完成（本轮范围）；其他副本未处理，从 Git 恢复历史记录 |
| PLAN-0009 | [嵌入结果缓存实施](0009-result-cache.md) | 已完成 |
| PLAN-0010 | [请求观测、请求内去重与过载提示实施](0010-request-optimizations.md) | 已完成 |
| PLAN-0011 | [单 worker 批内真合批](0011-batch-inference.md) | 已完成 |
| PLAN-0012 | [推理服务算法与 Infra 优化](0012-inference-optimizations.md) | 已完成；[测试证据](../../tests/benchmarks/evidence/0012/README.md) |
| PLAN-0013 | [sparse 输出改为 Milvus 可直插形态](0013-milvus-sparse-format.md) | 已完成 |
| PLAN-0014 | [恢复执行留档与统一 Plan 归档规则](0014-plan-archive-governance.md) | 已完成 |

PLAN-0001 / 0002 / 0004 / 0005 / 0008 曾在 `e1ab99c` 中被删除，2026-10-26 从删除前版本恢复，保留历史内容与来源说明。各计划中的旧契约、环境和命令仅代表当时的执行上下文。

新计划从 [模板](_template.md) 开始，按 [文档中心](../README.md) 的 SDD 流程关联上游依据；历史计划不为套用新模板而重写。
