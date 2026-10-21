# 项目进度与交接

更新日期：2026-10-21。

## 当前状态

2026-10-21 按用户明确纠正，将开发理念统一为 SDD（规格驱动开发）：以已确认 Spec 驱动计划、实现与验收。依据见 [ADR-0001](docs/adr/0001-specification-driven-development.md)，流程见 [文档中心](docs/README.md)，文档调整与验证记录见 [PLAN-0001](docs/plans/0001-project-foundation.md)。本次只调整开发方法说明，不改变服务行为或既有验证结论。

首版已实现并部署到 Mac mini M4。[PLAN-0002](docs/plans/0002-minimal-service.md) 已完成；用户随后报告的长输入内存问题已修复并部署，定向证据见 [PLAN-0003](docs/plans/0003-fused-attention.md)。默认验收仍保持基本服务冒烟。

2026-10-21 按用户要求，16 项运行参数已集中到私有 TOML，并已同步到 M4、迁移配置和重启服务。线上现为 1 个执行位 + 19 个等待位，总计 20 个位置。两机各自项目环境的 65 项相关检查通过，M4 及本机经 Tailscale 的真实 HTTP 基本冒烟均通过，详见 [PLAN-0005](docs/plans/0005-file-configuration.md)；队列扩充的前序记录见 [PLAN-0004](docs/plans/0004-queue-capacity.md)。继续使用现有服务，当前无待完成部署步骤。

- 服务地址：`http://<TAILSCALE_IP>:8000`（Tailscale / 内网）。
- 接口：`POST /v1/embeddings`，共享 API Key；`GET /healthz` 无需 Key。
- 连接方式、请求参数与接口限制见 [推理服务连接与使用说明](docs/service-connection.md)。
- 使用项目原有 BGE-M3 MLX 8bit 权重，返回 1024 维 dense；调用方负责文件解析与切分。
- 原生 Python / FastAPI / Uvicorn 单 worker，MLX Apple GPU；单模型串行、有界等待、必要错误和轮转日志。注意力强制走融合内核并逐层求值，保留原权重和双向语义。
- M4 上由用户级 launchd 管理；需要相应用户保持登录，机器睡眠时不承诺可访问。未修改系统电源设置。

## 环境与运行位置

| 项目 | 已核实事实 |
| --- | --- |
| 本机 | M5、32GB、macOS 26.5.1；Miniconda 的 bge-embedding，Python 3.12.15 / arm64 |
| 目标机 | M4、16GB、macOS 26.5.1；Miniforge 的 bge-embedding，Python 3.12.15 / arm64 |
| 目标目录 | ${REMOTE_PROJECT_DIR} |
| 目标解释器 | ${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python |
| 常驻配置 | ${REMOTE_HOME}/Library/LaunchAgents/local.bge-embedding.plist，权限 600，通过 --config 引用私有 TOML |
| 运行配置 | ${REMOTE_PROJECT_DIR}/config.toml，权限 600，保存 Key 及其余 15 项运行参数；修改后重启生效 |
| 日志 | ${REMOTE_PROJECT_DIR}/logs/service.log，5 MiB / 2 备份；2026-10-21 从 ~/Library/Logs 迁入项目，旧文件留存原处未删除 |
| 依赖 | 两机使用同一带 wheel 哈希的 requirements.lock，pip check 均通过，无全局安装 |

启动、停止、获取私有配置及基本调用见 [部署说明](deploy/README.md)。Key 未打印、未写入仓库；用户提供的登录密码未使用或保存。

新版本由 `python -m bge_embedding --config <文件>` 启动。此次已在 M4 迁移旧 plist 的 Key、`0.0.0.0:8000` 和模型路径到 TOML，保留原访问凭据及地址；新 plist 只引用配置文件，不再保存旧环境变量。旧源码与私有 plist 已备份在目标项目的 `.cache/deploy-config-20261021-j_kuhy_5/`，目录权限 700，归档与 plist 权限 600。

2026-10-21 按用户要求把过程文件归口到项目工作路径：服务日志默认从 `~/Library/Logs/bge-embedding/service.log` 改为项目内 `logs/service.log`（相对配置文件解析），M4 已更新 `config.toml` 并重启，冒烟通过；约定常驻轮转日志归 `logs/`、一次性诊断测量与备份产物归 `.cache/`，均不入版本控制，见 [部署说明](deploy/README.md)。

## 当前验证范围

用户明确要求“一切从简”，见 [ADR-0004](docs/adr/0004-minimal-verification.md)。官方参考对照及复杂测试已退出首版必做范围；额外参考权重、专用验证脚本及 Torch 专用依赖已移除。

- 默认测试：2 项基本 smoke 通过。
- 已通过本机到 M4 的真实 HTTP 调用：健康状态、缺 Key 返回 401、正确 Key 的单条 / 两条批量、1024 维有限归一化向量。
- 针对实际内存问题新增 1 项定向回归：旧实现 2048-token Metal 活跃分配峰值 1674.8 MiB，修复后 677.3 MiB；本机回归通过，M4 独立测量一致。
- M4 修复后 8192-token 样本推理约 4.79 秒，Metal 活跃分配峰值 977.4 MiB；真实 HTTP 返回 200 / 8192 tokens / 1024 维，约 4.71 秒。4 个可安全复测的修复前后样本余弦相似度均高于 0.999999999。
- 内存测量期间无新增 swap 写出；8192 样本有 32 页系统级 swap 读入，原有 swap 仍在，不能称系统完全无 swap。2 GiB 工作指导值 / 256 MiB 缓存回收目标不是硬配额，见 Plan 的口径与限制。
- 已按 PLAN-0006 完成延迟基线、并发容量与资源峰值测试（2026-10-21）；仍未做故障注入、30 秒排队超时实测、soak、8192 全长、整机重启或重新登录测试；不承诺容量或吞吐。launchd 启动 / 重启选项已配置，手动卸载与加载已实际执行。
- 2026-10-21 按 [PLAN-0006](docs/plans/0006-performance-test.md) 完成 5 指标 × 3 场景性能测试并回填：5xx 与预期外 429 均为 0，无 swap 增长；RSS 峰值约 630 MiB、Metal 5341 峰值 838.2 MiB，三档延迟 P50 约 25.1 / 273.9 / 2616 ms。结果仅作观测，仍不构成容量、吞吐或 SLA 承诺；原始证据备份在本机 `.cache/perf/m4/`。

## 后续工作原则

先使用现有服务。只有实际问题或用户明确需求才增加实现、优化或对应测试；不要自动恢复参考评测、完整边界套件或复杂验收流程。

2026-10-21 按用户要求初始化项目 Git，分支为 `main`，`origin` 关联 [LMQH/bge-embedding-server](https://github.com/LMQH/bge-embedding-server)。模型权重、缓存、凭据和独立上游 MLX 克隆继续排除在版本控制之外；初始化检查见 [PLAN-0001](docs/plans/0001-project-foundation.md)。README 仅保留总览与导航，后续状态在本文件维护。
