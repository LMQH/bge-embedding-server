# 项目进度与交接

更新日期：2026-10-26。当前仓库版本：**v1.1.1**；已部署服务版本：**v1.1.0**。

设备口径（2026-10-26 用户澄清）：性能记录中的“本机 Mac mini M4”与“M4 目标机”是同一台 Mac mini M4 16GB，不是两台 M4。不同测试须按代码版本、模型级 / 进程内 ASGI / 真实 HTTP 区分。早期 M5 开发机及其同步、环境和验证记录保留历史含义，不归入 M4 性能数据。

## 当前状态

v1.1.1 为文档与测试资产整理补丁，不改变服务行为，本次未部署或重启。v1.1.0 服务已在 Mac mini M4 16GB 上线（用户级 launchd 常驻，`http://<TAILSCALE_IP>:8000`）。

核心能力与依据：

- 嵌入推理契约：[SPEC-0001](docs/specs/0001-embedding-inference.md)。BGE-M3 MLX 8bit，1024 维 dense，单条 8192 tokens / 16 条 / 32768 tokens / 1 MiB 上限，FP16 attention，批内按长度分桶合批，15ms 窗口跨请求微合批。
- 双路输出：[SPEC-0002](docs/specs/0002-dense-sparse-output.md)，`return_sparse` 返回 token 级稀疏权重 `[[token_id, weight], ...]`，可直接作为 Milvus `SPARSE_FLOAT_VECTOR` 字段值；M4 线上已切换。
- 结果缓存：[SPEC-0003](docs/specs/0003-result-cache.md)，进程内、按字节上限、无 TTL。
- 请求观测：[SPEC-0004](docs/specs/0004-request-observability-and-dedup.md)，请求日志 `wait_ms` / `exec_ms` / `ahead` / `dedup`，请求内去重，429 附 `Retry-After: 1`。
- 能力边界与局限清单：[REF-0003](docs/references/0003-service-limitations.md)。

2026-10-26 已恢复 v1.0.0 整理时误删的 5 份过程性 Plan，完整执行历史见 [Plan 索引](docs/plans/README.md)。Plan 保留执行依据、步骤与结果，本文仅维护当前结论和交接摘要。

## 版本记录

| 版本 | 日期 | 内容 |
| --- | --- | --- |
| v1.1.1 | 2026-10-26 | 恢复 5 份历史 Plan，统一执行留档、编号与索引；基准脚本和原始结果归入 `tests/`；修正设备与验证口径说明。无服务行为变更，未部署。依据见 [PLAN-0014](docs/plans/0014-plan-archive-governance.md) |
| v1.1.0 | 2026-10-26 | `return_sparse` 输出由字符串键对象改为 `[[token_id, weight], ...]`，可直接作为 Milvus `SPARSE_FLOAT_VECTOR` 字段值；代码同步、M4 部署并复验。破坏性：读取 `sparse` 的旧客户端需按 [SPEC-0002](docs/specs/0002-dense-sparse-output.md) 更新。证据见 [PLAN-0013](docs/plans/0013-milvus-sparse-format.md) |
| v1.0.0 | 2026-10-23 | 首版定版：dense 契约、双路输出、结果缓存、请求观测与去重、批内与跨请求微合批 |

## 执行记录与验证入口

全部计划（含初始化、配置迁移与仓库治理）见 [Plan 索引](docs/plans/README.md)；以下为服务验证的常用入口。

| 记录 | 内容 |
| --- | --- |
| [PLAN-0003](docs/plans/0003-fused-attention.md) | 长输入内存修复：2048-token Metal 峰值 1674.8 → 677.3 MiB |
| [PLAN-0006](docs/plans/0006-performance-test.md) | 性能基线：25 / 945 / 5341 tokens P50 约 25.1 / 273.9 / 2616 ms；并发与资源峰值 |
| [PLAN-0007](docs/plans/0007-dense-sparse-output.md) | 双路输出验收：8192 tokens dense+sparse 实测与 M4 部署记录 |
| [PLAN-0009](docs/plans/0009-result-cache.md) | 缓存实施与部署验证：命中 P50 4.6 / 7.1 / 6.8 ms |
| [PLAN-0010](docs/plans/0010-request-optimizations.md) | 请求优化验证：去重、日志字段、Retry-After 实测 |
| [PLAN-0011](docs/plans/0011-batch-inference.md) | 批内合批：16×25 约 3.3x、16×256 约 1.18x，1k 以上约 1.0x；600 秒连续入库 3537.7 tok/s |
| [PLAN-0012](docs/plans/0012-inference-optimizations.md)（含 [PLAN-0012 测试证据](tests/benchmarks/evidence/0012/README.md)） | FP16 采纳（快 18–21%，峰值 977→784 MiB）、P2/P3 否决证据、跨请求微合批（20 并发单条 P95 380→146ms） |
| [PLAN-0013](docs/plans/0013-milvus-sparse-format.md) | sparse 改为 `[token_id, weight]` 二元数组：代码同步、真实推理、M4 部署重启、HTTP smoke 与 pymilvus 校验证据 |

## 环境与运行位置

| 项目 | 已核实事实 |
| --- | --- |
| 服务与性能测试设备 | 同一台 Mac mini M4、16GB、macOS 26.5.1；原生 arm64 的 `bge-embedding` 环境（Miniforge），Python 3.12 |
| 目标目录 | ${REMOTE_PROJECT_DIR} |
| 目标解释器 | ${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python |
| 常驻配置 | ${REMOTE_HOME}/Library/LaunchAgents/local.bge-embedding.plist，权限 600，通过 `--config` 引用私有 TOML |
| 运行配置 | ${REMOTE_PROJECT_DIR}/config.toml，权限 600，保存 Key 及运行参数；修改后重启生效 |
| 日志 | ${REMOTE_PROJECT_DIR}/logs/service.log，5 MiB / 2 备份 |
| 依赖 | 开发与部署沿用同一带 wheel 哈希的 [requirements.lock](requirements.lock)，`pip check` 通过 |

- 连接方式、请求参数与接口限制见 [推理服务连接与使用说明](docs/service-connection.md)；启动与部署见 [部署说明](deploy/README.md)。
- 调用方负责文件解析与切分。单 worker、1 执行位 + 19 等待位 FIFO；机器睡眠或未登录时不承诺可访问。
- M4 公钥授权：旧开发机公钥已装入 M4 `authorized_keys`；当前执行环境 SSH 未授权，M4 远程操作需先行处理密钥。

## 当前验证口径

- 测试分 `smoke`（默认，4 项起）与 `real`（需本机模型权重与 Metal）两组；定版时相关检查通过，详见各保留 Plan。
- 未做：故障注入、30 秒排队超时实测、soak、整机重启 / 重新登录演练；v1.1.0 未完整重跑性能基线（线上冒烟见 PLAN-0013）。不承诺容量、吞吐或 SLA。
- M4 的单请求、并发、批量、长输入、内存及持续推理已有观测；数据跨不同版本与测量方式，并非 v1.1.0 的统一性能复测。仅了解 M4 性能可沿用现有记录；需要当前版本统一指标时再补轻量 HTTP 复测，无需检索标注数据集或 Ragas。
- 所有性能数字为对应测试场景的观测值，不是承诺；原始证据在对应 Plan 与 [PLAN-0012 测试证据](tests/benchmarks/evidence/0012/README.md)。
- 2026-10-26 sparse 形态变更：代码与稀疏头已同步并校验 SHA-256，通过非 real 测试与真实推理测试；另有临时服务 HTTP smoke（含 8192 tokens）与 pymilvus 形状校验证据；M4 已于同日授权重启，`verify_http.py --launchd --sparse --long` 全 PASS，线上响应与本地真实推理逐位一致。

## 后续工作原则

先使用现有服务；只有实际问题或用户明确需求才增加实现、优化或测试。对 M4 的部署、配置与运维变更需另行授权。运行调优先观察日志中 `wait_ms` / `exec_ms` / 429 分布与缓存命中率，再决定准入控制或 padding 预算调整。

## 仓库治理（v1.1.1）

- 2026-10-26：恢复 PLAN-0001 / 0002 / 0004 / 0005 / 0008，保留原编号；PLAN-0012 的脚本与原始数据统一移至 [tests/benchmarks](tests/benchmarks/README.md)。归档规则、索引与核验记录见 [PLAN-0014](docs/plans/0014-plan-archive-governance.md)。

- 文档遵循 [SDD 流程](docs/README.md)：PRD 定需求、ADR 记决策、Spec 定契约、Plan 留执行依据、步骤与验证结论；行为变更先改 Spec。
- Plan 不因完成、取消或没有测试数据而删除，编号递增且不复用；历史记录保留在 Plan，原始测试资产归 `tests/`，通过链接关联。`docs/service-connection.md` 只保留当前线上契约。
- 仓库不含模型权重、缓存、凭据与日志；私有连接信息只存在于被忽略的 `config.toml` 与 `docs/service-connection.local.md`。
- Git 仓库：`main` 分支，`origin` 关联 GitHub（见 `git remote -v`）；仓库补丁版本标记为 `v1.1.1`，服务部署仍以 `v1.1.0` 为准。
