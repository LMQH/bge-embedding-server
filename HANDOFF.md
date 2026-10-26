# 项目进度与交接

更新日期：2026-10-26。当前版本：**v1.0.0（定版）**；工作区包含 sparse 输出格式变更（未部署，见下）。

## 当前状态

v1.0.0 定版。服务已在两机上线同一版本：本机与 Mac mini M4 16GB 目标机（用户级 launchd 常驻，`http://<TAILSCALE_IP>:8000`）。

核心能力与依据：

- 嵌入推理契约：[SPEC-0001](docs/specs/0001-embedding-inference.md)。BGE-M3 MLX 8bit，1024 维 dense，单条 8192 tokens / 16 条 / 32768 tokens / 1 MiB 上限，FP16 attention，批内按长度分桶合批，15ms 窗口跨请求微合批。
- 双路输出：[SPEC-0002](docs/specs/0002-dense-sparse-output.md)，`return_sparse` 返回 token 级稀疏权重 `[[token_id, weight], ...]`，可直接作为 Milvus `SPARSE_FLOAT_VECTOR` 字段值；两机线上仍是旧的字符串键形态，待部署升级。
- 结果缓存：[SPEC-0003](docs/specs/0003-result-cache.md)，进程内、按字节上限、无 TTL。
- 请求观测：[SPEC-0004](docs/specs/0004-request-observability-and-dedup.md)，请求日志 `wait_ms` / `exec_ms` / `ahead` / `dedup`，请求内去重，429 附 `Retry-After: 1`。
- 能力边界与局限清单：[REF-0003](docs/references/0003-service-limitations.md)。

开发过程记录已按 v1.0.0 定版整理：纯过程性 Plan（项目初始化、首版搭建、队列扩容、配置迁移、历史清理）已删除；保留承载验证数据的 Plan（见下）。本文即过程结论的简洁汇总。

## 保留的验证记录

| 记录 | 内容 |
| --- | --- |
| [PLAN-0003](docs/plans/0003-fused-attention.md) | 长输入内存修复：2048-token Metal 峰值 1674.8 → 677.3 MiB |
| [PLAN-0006](docs/plans/0006-performance-test.md) | 性能基线：25 / 945 / 5341 tokens P50 约 25.1 / 273.9 / 2616 ms；并发与资源峰值 |
| [PLAN-0007](docs/plans/0007-dense-sparse-output.md) | 双路输出验收：8192 tokens dense+sparse 实测与 M4 部署记录 |
| [PLAN-0009](docs/plans/0009-result-cache.md) | 缓存实施与部署验证：命中 P50 4.6 / 7.1 / 6.8 ms |
| [PLAN-0010](docs/plans/0010-request-optimizations.md) | 请求优化验证：去重、日志字段、Retry-After 实测 |
| [PLAN-0011](docs/plans/0011-batch-inference.md) | 批内合批：16×25 约 3.3x、16×256 约 1.18x，1k 以上约 1.0x；600 秒连续入库 3537.7 tok/s |
| [PLAN-0012](docs/plans/0012-inference-optimizations.md)（含 [0012-evidence](docs/plans/0012-evidence/README.md)） | FP16 采纳（快 18–21%，峰值 977→784 MiB）、P2/P3 否决证据、跨请求微合批（20 并发单条 P95 380→146ms） |
| [PLAN-0013](docs/plans/0013-milvus-sparse-format.md) | sparse 改为 `[token_id, weight]` 二元数组：两机同步、真实推理、HTTP smoke 与 pymilvus 校验证据；重启待授权 |

## 环境与运行位置

| 项目 | 已核实事实 |
| --- | --- |
| 两机 | Mac mini、Apple M4、16GB、macOS 26.5.1；各自原生 arm64 的 `bge-embedding` 环境（本机 Miniconda / 目标机 Miniforge），Python 3.12 |
| 目标目录 | ${REMOTE_PROJECT_DIR} |
| 目标解释器 | ${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python |
| 常驻配置 | ${REMOTE_HOME}/Library/LaunchAgents/local.bge-embedding.plist，权限 600，通过 `--config` 引用私有 TOML |
| 运行配置 | ${REMOTE_PROJECT_DIR}/config.toml，权限 600，保存 Key 及运行参数；修改后重启生效 |
| 日志 | ${REMOTE_PROJECT_DIR}/logs/service.log，5 MiB / 2 备份 |
| 依赖 | 两机使用同一带 wheel 哈希的 [requirements.lock](requirements.lock)，`pip check` 通过 |

- 连接方式、请求参数与接口限制见 [推理服务连接与使用说明](docs/service-connection.md)；启动与部署见 [部署说明](deploy/README.md)。
- 调用方负责文件解析与切分。单 worker、1 执行位 + 19 等待位 FIFO；机器睡眠或未登录时不承诺可访问。
- M4 公钥授权：旧开发机公钥已装入 M4 `authorized_keys`；当前执行环境 SSH 未授权，M4 远程操作需先行处理密钥。

## 当前验证口径

- 测试分 `smoke`（默认，4 项起）与 `real`（需本机模型权重与 Metal）两组；定版时两机相关检查通过，详见各保留 Plan。
- 未做：故障注入、30 秒排队超时实测、soak、整机重启 / 重新登录演练；M4 线上最新版本的冒烟记录未单独归档（部署事实经用户确认）。不承诺容量、吞吐或 SLA。
- 所有性能数字为同机观测值，不是承诺；原始证据在对应 Plan 与 [0012-evidence](docs/plans/0012-evidence/README.md)。
- 2026-10-26 sparse 形态变更：两机已同步同一提交与同一稀疏头（SHA-256 一致），均通过非 real 测试与真实推理测试；本机另有 HTTP smoke（含 8192 tokens）与 pymilvus 形状校验证据。线上进程未重启，响应契约仍为旧形态，部署与重启待单独授权。

## 后续工作原则

先使用现有服务；只有实际问题或用户明确需求才增加实现、优化或测试。对 M4 的部署、配置与运维变更需另行授权。运行调优先观察日志中 `wait_ms` / `exec_ms` / 429 分布与缓存命中率，再决定准入控制或 padding 预算调整。

## 仓库治理（v1.0.0）

- 文档遵循 [SDD 流程](docs/README.md)：PRD 定需求、ADR 记决策、Spec 定契约、Plan 留验证证据；行为变更先改 Spec。
- 定版时已删除纯过程性 Plan（初始化、首版搭建、队列扩容、配置迁移、历史清理），结论已并入本文；`docs/service-connection.md` 只保留当前线上契约，历史部署补记由本文承载。
- 仓库不含模型权重、缓存、凭据与日志；私有连接信息只存在于被忽略的 `config.toml` 与 `docs/service-connection.local.md`。
- Git 仓库：`main` 分支，`origin` 关联 GitHub（见 `git remote -v`）；定版以 `v1.0.0` tag 为准。
