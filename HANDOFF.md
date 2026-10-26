# 项目进度与交接

更新日期：2026-10-26。仓库版本 **v1.1.1**；部署版本 **v1.1.0**。

## 当前状态

v1.1.0 在 Mac mini M4 16GB 上线（用户级 launchd，`http://<TAILSCALE_IP>:8000`）；v1.1.1 只整理文档与测试资产，未部署。M4 与历史记录中的“M4 目标机”是同一台设备；M5 早期记录不归入 M4 数据。

契约：嵌入与队列 [SPEC-0001](docs/specs/0001-embedding-inference.md)，双路输出 [SPEC-0002](docs/specs/0002-dense-sparse-output.md)，缓存 [SPEC-0003](docs/specs/0003-result-cache.md)，请求观测与去重 [SPEC-0004](docs/specs/0004-request-observability-and-dedup.md)。能力边界见 [REF-0003](docs/references/0003-service-limitations.md)。

| 版本 | 日期 | 内容 |
| --- | --- | --- |
| v1.1.1 | 2026-10-26 | 恢复 5 份历史 Plan，统一留档与索引；基准脚本归入 `tests/`。无行为变更 |
| v1.1.0 | 2026-10-26 | `sparse` 改为 `[[token_id, weight], ...]`，可直接写入 Milvus；已部署。旧客户端需按 [SPEC-0002](docs/specs/0002-dense-sparse-output.md) 更新 |
| v1.0.0 | 2026-10-23 | 首版：dense、双路输出、缓存、观测去重、批内与跨请求微合批 |

## 环境

| 项目 | 值 |
| --- | --- |
| 设备 | Mac mini M4 16GB，macOS 26.5.1，arm64 |
| 项目目录 / 解释器 | `${REMOTE_PROJECT_DIR}` / `${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python` |
| 常驻配置 | `${REMOTE_HOME}/Library/LaunchAgents/local.bge-embedding.plist`（600，`--config` 引用私有 TOML） |
| 运行配置 / 日志 | `${REMOTE_PROJECT_DIR}/config.toml`（600）/ `logs/service.log`（5 MiB × 2） |
| 依赖 | 开发与部署共用 [requirements.lock](requirements.lock)，`pip check` 通过 |
| 远程访问 | Tailscale 内已有 SSH 密钥免密登录，未保存密码 |

运行参数、连接方式见[连接与使用](docs/service-connection.md)，启动见[部署说明](deploy/README.md)。可访问性依赖登录状态与网络唤醒。

## 验证口径

- 测试分 `smoke`（默认）与 `real`（需真实模型与 Metal）；Plan 记录各次验证。
- v1.1.0 已在 M4 完成真实 HTTP 补测（[PLAN-0015](docs/plans/0015-production-service-validation.md)，[证据](tests/benchmarks/evidence/0015/README.md)）：基线、阶梯、30 分钟持续、过载与 30 秒排队超时、取消、SIGTERM 503、SIGKILL 拉起。
- 未验证：能耗、Metal 峰值、整机重启 / 登录、跨主机客户端；P95 目标与 RTO 未定义，因此不承诺容量、吞吐或 SLA。
- 结果按代码版本与测量方式区分，原始证据在对应 Plan 的 `tests/benchmarks/evidence/`。

## 后续事项

- 需要新指标时复用 `tests/benchmarks/service_load.py`；先按阶梯选率，再测持续负载。
- 调优先看日志 `wait_ms` / `exec_ms` / 429 分布与缓存命中率，再决定准入控制或 padding 预算。
- 对 M4 的部署、配置与运维变更需单独授权。

## 仓库治理

- SDD 流程见[文档中心](docs/README.md)：PRD 定需求、ADR 记决策、Spec 定契约、Plan 留执行与验证。
- Plan 编号递增不复用，历史记录不删除；原始测试资产归 `tests/`，通过链接关联。
- 仓库不含模型权重、缓存、凭据与日志；私有连接信息只在被忽略的 `config.toml` 与 `docs/service-connection.local.md`。
- `main` 关联 GitHub；仓库补丁版本 `v1.1.1`，服务部署以 `v1.1.0` 为准。
