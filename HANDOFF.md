# 项目进度与交接

更新日期：2026-10-23。

## 当前状态

2026-10-23 按用户指示完成首批请求优化（O1/O2/O4）：请求日志追加 `wait_ms` / `exec_ms` / `ahead` / `dedup`；同一请求内重复文本只推理一次，响应顺序与 `usage` 不变；429 增加 `Retry-After: 1`。新增 [PRD-0004](docs/prd/0004-request-optimizations.md)、[SPEC-0004](docs/specs/0004-request-observability-and-dedup.md)、[PLAN-0010](docs/plans/0010-request-optimizations.md)，配置仍为 18 项。本机 99 项非 real、2 项 real 测试通过；本机服务已通过 launchd 重启加载新版本并完成真实 HTTP 与性能实测。M4 未部署，M4 线上行为仍以旧版本为准；部署需另行授权。

2026-10-23 按用户指定“单 worker + 真合批”完成批内合批：同一请求内的未命中条目按 token 长度分桶，右 padding 后一次前向；每组合批后的 padding token 不超过 8192，单条超预算时单独执行。外部 API、输出顺序、`usage`、错误码、缓存与 FIFO 不变；执行位仍为 1，不跨请求合批，未新增配置项。更新 [SPEC-0001](docs/specs/0001-embedding-inference.md)，新增 [ADR-0007](docs/adr/0007-batch-inference.md) 与 [PLAN-0011](docs/plans/0011-batch-inference.md)。当前 Mac mini M4 16GB 上 103 项非 real、3 项 real 测试通过；基准显示 16×25 约 3.3x、16×256 约 1.18x、16×512 约 1.05x，16×1024 / 16×2048 / 4×8192 约 1.0x，混合长度约 0.97x，峰值最高 977.4 MiB。结论：合批对短/中批有效，1M token 按 1k 块入库仍约 5 分钟，不会因合批出现数量级提升。当前常驻服务尚未重启加载该版本，新合批未生效。

2026-10-23 按用户要求完成 600 秒连续入库：`16×512`、dense-only、固定 512-token 合成输入、独立进程，不经过 HTTP/缓存/队列。260 批 / 2,129,920 tokens / 602.07 秒，平均 3,537.7 tok/s；首 30 秒 3,713.9，约 2 分钟后稳定在 3,512–3,532，稳定段斜率约 `-0.002 tok/s²`；峰值 977.4 MiB，RSS 峰值 1,292 MiB，swap 前后均为 41.5 MiB used，`pmset` 未记录热/性能警告。结论：未观察到明显持续热降频；该测试不代表 HTTP、队列、真实语料或容量承诺。

2026-10-22 新增 [REF-0003：当前服务的局限性](docs/references/0003-service-limitations.md)，把模型、接口、容量、运维与验证层面的边界按“设计取舍 / 能力缺口 / 未验证风险”三层固化为文档，覆盖 22 条局限并给出影响排序；同步更新[文档中心](docs/README.md)索引与 README 的边界说明。本文是评估依据与快照，不构成 SLA、容量或效果承诺；本次不改变服务行为。

2026-10-22 按用户要求将根目录 README 重写为技术产品介绍：以产品定位、核心能力、请求链路、快速开始、API 契约、M4 性能观测与适用边界组织内容，替代仅目录导航的旧版；性能数字引用 [PLAN-0006](docs/plans/0006-performance-test.md) / [PLAN-0009](docs/plans/0009-result-cache.md)，接口限制引用 [SPEC-0001](docs/specs/0001-embedding-inference.md) / [SPEC-0002](docs/specs/0002-dense-sparse-output.md)，版本基线取自 [requirements.lock](requirements.lock)。部署进度与验证证据继续在本文件及各 Plan 维护。文档检查记录见 [PLAN-0001](docs/plans/0001-project-foundation.md)，本次不改变服务行为。

2026-10-22 已对当前文档中的真实内网地址、设备名、登录用户名及本机 / 目标机绝对路径脱敏，变量均为占位符，不再作为实际连接信息。已按用户授权重写并推送远端 `main`，重新克隆后的 Git 对象扫描通过；本地已同步新历史，移除 5 个旧 Codex 引用并清理 reflog / 不可达对象，扫描通过。详细范围与证据见 [PLAN-0008](docs/plans/0008-repository-privacy.md)。其他机器的旧克隆及 GitHub 缓存 / fork / PR 引用仍需分别处理，不能承诺外部副本已删除。

2026-10-21 按用户明确纠正，将开发理念统一为 SDD（规格驱动开发）：以已确认 Spec 驱动计划、实现与验收。依据见 [ADR-0001](docs/adr/0001-specification-driven-development.md)，流程见 [文档中心](docs/README.md)，文档调整与验证记录见 [PLAN-0001](docs/plans/0001-project-foundation.md)。本次只调整开发方法说明，不改变服务行为或既有验证结论。

首版已实现并部署到 Mac mini M4。[PLAN-0002](docs/plans/0002-minimal-service.md) 已完成；用户随后报告的长输入内存问题已修复并部署，定向证据见 [PLAN-0003](docs/plans/0003-fused-attention.md)。默认验收仍保持基本服务冒烟。

2026-10-21 按用户要求，16 项运行参数已集中到私有 TOML，并已同步到 M4、迁移配置和重启服务。线上现为 1 个执行位 + 19 个等待位，总计 20 个位置。两机各自项目环境的 65 项相关检查通过，M4 及本机经 Tailscale 的真实 HTTP 基本冒烟均通过，详见 [PLAN-0005](docs/plans/0005-file-configuration.md)；队列扩充的前序记录见 [PLAN-0004](docs/plans/0004-queue-capacity.md)。继续使用现有服务；双路输出的 M4 部署方案已落盘，当前明确不执行、无需审批。

2026-10-21 新增 [PRD-0002](docs/prd/0002-dense-sparse-embeddings.md)，将 dense + sparse 双路输出纳入范围，采用 BGE-M3 原生稀疏头。本机实现、测试与文档已完成，[PLAN-0007](docs/plans/0007-dense-sparse-output.md) 记录了 8192 tokens 的本地证据；M4 未部署，线上仍只返回 dense。按用户要求，Plan、实现与测试已推送到 GitHub `main`，当前不执行 M4 部署。

2026-10-22 新增 [PRD-0003](docs/prd/0003-result-cache.md)：进程内嵌入结果缓存（[ADR-0006](docs/adr/0006-in-memory-result-cache.md)，契约 [SPEC-0003](docs/specs/0003-result-cache.md)）。实现与 23 项新增测试全部通过，并按用户授权部署至 M4 线上验证通过；独立 code-review 审查通过并完成修复复验。按 PLAN-0006 同一标准复测延迟（缓存启用 / 禁用两轮）：三档 P50 25.1 / 273.9 / 2616 ms（基线）→ 4.6 / 7.1 / 6.8 ms（缓存启用），未命中路径无回退（945t 冷 273 ms ≈ 基线）；并发 20 由 662 请求 / 3.68 QPS 升至 135,047 请求 / 750 QPS（命中主导口径）；5xx 与预期外 429 均为 0，swap 无增长。配置增至 18 项（`[cache]` 开关与字节上限），本机与 M4 的私有配置均已更新。详细证据见 [PLAN-0009](docs/plans/0009-result-cache.md)。M4 线上现为缓存版本；本机公钥已装入 M4 `authorized_keys`，后续部署免密。

- 服务地址：`http://<TAILSCALE_IP>:8000`（Tailscale / 内网）。
- 接口：`POST /v1/embeddings`，共享 API Key；`GET /healthz` 无需 Key。
- 连接方式、请求参数与接口限制见 [推理服务连接与使用说明](docs/service-connection.md)。
- 使用项目原有 BGE-M3 MLX 8bit 权重，返回 1024 维 dense；本机版本可选 sparse，M4 线上未部署。调用方负责文件解析与切分。
- 原生 Python / FastAPI / Uvicorn 单 worker，MLX Apple GPU；单模型串行、有界等待、必要错误和轮转日志。注意力强制走融合内核并逐层求值，保留原权重和双向语义。
- M4 上由用户级 launchd 管理；需要相应用户保持登录，机器睡眠时不承诺可访问。未修改系统电源设置。

## 环境与运行位置

| 项目 | 已核实事实 |
| --- | --- |
| 本机（当前执行环境） | Mac mini、Apple M4、16GB、macOS 26.5.1；Miniconda 的 bge-embedding，Python 3.12.15 / arm64 |
| 目标机 | Mac mini、M4、16GB、macOS 26.5.1；Miniforge 的 bge-embedding，Python 3.12.15 / arm64 |
| 目标目录 | ${REMOTE_PROJECT_DIR} |
| 目标解释器 | ${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python |
| 常驻配置 | ${REMOTE_HOME}/Library/LaunchAgents/local.bge-embedding.plist，权限 600，通过 --config 引用私有 TOML |
| 运行配置 | ${REMOTE_PROJECT_DIR}/config.toml，权限 600，保存 Key 及其余 15 项运行参数；修改后重启生效 |
| 日志 | ${REMOTE_PROJECT_DIR}/logs/service.log，5 MiB / 2 备份；2026-10-21 从 ~/Library/Logs 迁入项目，旧文件留存原处未删除 |
| 依赖 | 当前执行环境与目标机使用同一带 wheel 哈希的 requirements.lock，pip check 均通过，无全局安装 |

2026-10-23 复核：当前 agent 执行环境是 Mac mini、Apple M4、16GB（`sysctl` 核实），不是 M5 / 32GB。仓库中 2026-10-21 / 22 的部分 Plan 仍保留当时开发机 M5 的历史记录；本轮合批测试与数据均在上述 Mac mini M4 16GB 上取得，且使用独立进程，未重启常驻服务。

启动、停止、获取私有配置及基本调用见 [部署说明](deploy/README.md)。Key 未打印、未写入仓库；用户提供的登录密码未使用或保存。

新版本由 `python -m bge_embedding --config <文件>` 启动。此次已在 M4 迁移旧 plist 的 Key、`0.0.0.0:8000` 和模型路径到 TOML，保留原访问凭据及地址；新 plist 只引用配置文件，不再保存旧环境变量。旧源码与私有 plist 已备份在目标项目的 `.cache/deploy-config-20261021-j_kuhy_5/`，目录权限 700，归档与 plist 权限 600。

2026-10-21 按用户要求把过程文件归口到项目工作路径：服务日志默认从 `~/Library/Logs/bge-embedding/service.log` 改为项目内 `logs/service.log`（相对配置文件解析），M4 已更新 `config.toml` 并重启，冒烟通过；约定常驻轮转日志归 `logs/`、一次性诊断测量与备份产物归 `.cache/`，均不入版本控制，见 [部署说明](deploy/README.md)。

## 当前验证范围

用户明确要求“一切从简”，见 [ADR-0004](docs/adr/0004-minimal-verification.md)。官方参考对照及复杂测试已退出首版必做范围；额外参考权重、专用验证脚本及 Torch 专用依赖已移除。

- 默认测试：4 项基本 smoke 通过。
- 双路输出本机验证：72 项非 real 通过；2 项 real 通过；8192 tokens dense-only 5.133 秒 / 977.4 MiB，dense+sparse 4.777 秒 / 977.4 MiB，dense 最大绝对差 0.0；本机真实 HTTP 含 sparse 与 8192 tokens 冒烟通过（4.88 秒）。详见 [PLAN-0007](docs/plans/0007-dense-sparse-output.md)。M4 双路输出未部署、未实测。
- 已通过本机到 M4 的真实 HTTP 调用：健康状态、缺 Key 返回 401、正确 Key 的单条 / 两条批量、1024 维有限归一化向量。
- 针对实际内存问题新增 1 项定向回归：旧实现 2048-token Metal 活跃分配峰值 1674.8 MiB，修复后 677.3 MiB；本机回归通过，M4 独立测量一致。
- M4 修复后 8192-token 样本推理约 4.79 秒，Metal 活跃分配峰值 977.4 MiB；真实 HTTP 返回 200 / 8192 tokens / 1024 维，约 4.71 秒。4 个可安全复测的修复前后样本余弦相似度均高于 0.999999999。
- 内存测量期间无新增 swap 写出；8192 样本有 32 页系统级 swap 读入，原有 swap 仍在，不能称系统完全无 swap。2 GiB 工作指导值 / 256 MiB 缓存回收目标不是硬配额，见 Plan 的口径与限制。
- 已按 PLAN-0006 完成延迟基线、并发容量与资源峰值测试（2026-10-21）；仍未做故障注入、30 秒排队超时实测、soak、8192 全长、整机重启或重新登录测试；不承诺容量或吞吐。launchd 启动 / 重启选项已配置，手动卸载与加载已实际执行。
- 2026-10-21 按 [PLAN-0006](docs/plans/0006-performance-test.md) 完成 5 指标 × 3 场景性能测试并回填：5xx 与预期外 429 均为 0，无 swap 增长；RSS 峰值约 630 MiB、Metal 5341 峰值 838.2 MiB，三档延迟 P50 约 25.1 / 273.9 / 2616 ms。结果仅作观测，仍不构成容量、吞吐或 SLA 承诺；原始证据备份在本机 `.cache/perf/m4/`。
- 2026-10-23 请求优化验证与部署：99 项非 real、2 项 real 通过；本机服务经 launchd 重启部署，真实 HTTP 冒烟通过；25 / 945 / 5341 tokens 冷 P50 48.9 / 270.0 / 2458.7 ms，命中 P50 1.7 / 2.2 / 5.9 ms；3 条相同 5349-token 输入墙钟 2.48 s（`exec_ms=2460`、`dedup=2`），3 条不同 7.40 s；20 并发排队为 19×200 + 1×429 `queue_full`（`Retry-After: 1`），`ahead` 0–19；测试后 footprint 1.2 GiB、峰值 1.4 GiB。详见 [PLAN-0010](docs/plans/0010-request-optimizations.md)。M4 未部署。
- 2026-10-23 批内真合批验证：当前 Mac mini M4 16GB 上 103 项非 real、3 项 real 通过；16×25 / 256 / 512 / 1024 / 2048 与 4×8192 的逐条 vs 合批对照，加速约 3.32x / 1.18x / 1.05x / 1.01x / 1.00x / 1.00x，混合长度约 0.97x；Metal 峰值最高 977.4 MiB，dense 余弦均 ≥0.999999。未做当前常驻服务的 HTTP 合批验证；详见 [PLAN-0011](docs/plans/0011-batch-inference.md)。

## 后续工作原则

先使用现有服务。只有实际问题或用户明确需求才增加实现、优化或对应测试；不要自动恢复参考评测、完整边界套件或复杂验收流程。

2026-10-23 首批优化后，先观察日志中的 `wait_ms` / `exec_ms` / 429 分布与缓存命中，再决定是否推进跨请求合并或准入控制；M4 部署需另行授权。

2026-10-23 批内真合批已按 [PLAN-0011](docs/plans/0011-batch-inference.md) 完成，单 worker、不跨请求、不新增配置。后续按实际批量请求的长度分布观察 `exec_ms`，再决定是否调整 8192 padding 预算或“小组合批”启发式；多 worker、跨请求合批与 M4 部署仍需另行授权。

2026-10-21 按用户要求初始化项目 Git，分支为 `main`，`origin` 关联 [LMQH/bge-embedding-server](https://github.com/LMQH/bge-embedding-server)。模型权重、缓存、凭据和独立上游 MLX 克隆继续排除在版本控制之外；初始化检查见 [PLAN-0001](docs/plans/0001-project-foundation.md)。本次双路输出的 Plan、实现与测试已推送到 `origin/main`，提交历史见 GitHub；M4 未执行。README 仅保留总览与导航，后续状态在本文件维护。
