# PLAN-0010：请求观测、请求内去重与过载提示实施

- 状态：已完成
- 关联 PRD / ADR / Spec：[PRD-0004](../prd/0004-request-optimizations.md)、[SPEC-0004](../specs/0004-request-observability-and-dedup.md)；ADR 不适用，验证范围沿用 [ADR-0004](../adr/0004-minimal-verification.md)。

## 目标与前置条件

交付 SPEC-0004 定义的三个请求级优化：日志追加 `wait_ms` / `exec_ms` / `ahead` / `dedup`，请求内重复文本只推理一次，429 返回 `Retry-After: 1`。不新增配置、依赖或端点，不改变 API 字段、错误码、上限、队列与缓存语义。

前置条件：

- SPEC-0004 已按用户 2026-10-23 指示确认。
- 本机 `bge-embedding` 环境可用；基线非 real 测试 95 项通过。
- M4 部署不在本计划授权范围，验证在仓库与本机完成。

## 实施步骤

| 状态 | 步骤与关联 Spec 场景 | 涉及目录或文件 | 验证标准 |
| --- | --- | --- | --- |
| 已完成 | 记录任务入队、开始与结束时间，供 AC-401 / AC-402 使用 | `src/bge_embedding/scheduler.py` | 任务时间戳单调，不改变调度顺序与取消语义 |
| 已完成 | 日志追加四个字段；请求内按 token 序列去重并映射回原顺序 | `src/bge_embedding/app.py` | AC-401、AC-402、AC-403 |
| 已完成 | 429 增加 `Retry-After: 1`，其他错误不加 | `src/bge_embedding/api.py` | AC-404 |
| 已完成 | 新增 / 调整单元测试覆盖去重、日志与响应头 | `tests/test_api.py` | AC-401～AC-405 |
| 已完成 | 同步文档索引、连接说明、局限清单与 HANDOFF | `docs/README.md`、`docs/service-connection.md`、`README.md`、`docs/references/0003-service-limitations.md`、`HANDOFF.md` | 链接可达，描述与实现一致 |
| 已完成 | 运行非 real 全量测试与真实模型冒烟 | — | AC-405、AC-406 |
| 已完成 | 本机部署：通过 launchd 重启加载新代码，沿用既有私有配置 | 用户级 launchd 任务 | `/healthz` ready；真实 HTTP 冒烟通过 |

## 验证记录

环境：本机 Apple Silicon、`bge-embedding` conda 环境（Python 3.12），2026-10-23。命令均在仓库根目录执行。

| 场景 | 命令或方法 | 预期 | 实际 |
| --- | --- | --- | --- |
| 基线 | `python -m pytest -q -m 'not real'` | 既有测试通过 | `95 passed, 2 deselected` |
| AC-401 / AC-402 | 同上，新增日志与排队测试 | 四个字段存在、非负；排队请求 `ahead>=1`；超时 `exec_ms=0` | `99 passed, 2 deselected`；排队日志 `ahead` 1→19、`wait_ms` 4.6–5.1 s、`exec_ms` 25–30 ms；超时用例 `exec_ms=0` |
| AC-403 | 同上，`["a","b","a"]` 参数化缓存开 / 关 | 推理 2 次、响应 3 条、`usage` 9 | 通过；日志 `batch=3 dedup=1` |
| AC-404 | 同上；真实 HTTP 另测 | 两个 429 带 `Retry-After: 1`，400/401 不带 | 单元测试通过；真实 HTTP 20 并发触发 1 个 `queue_full`，响应头 `Retry-After: 1` |
| 默认 smoke | `python -m pytest -q` | 基本 smoke 通过 | `4 passed, 97 deselected` |
| 真实模型 | `BGE_REAL_TESTS=1 BGE_CONFIG=$PWD/config.toml python -m pytest -q -m real` | 模型与长输入回归通过 | `2 passed, 99 deselected` |
| AC-406 | 临时配置在 `127.0.0.1:8001` 启动真实服务，运行 `tests/verify_http.py --sparse`；另发 3 条含重复文本的请求与 20 并发排队请求 | 冒烟通过；日志含新字段；去重生效；429 带头 | `PASS`；重复请求 3 条、`usage=39`、日志 `dedup=1`；并发 19×200 + 1×429，日志 `ahead` 0→19、`wait_ms` 4.6–5.1 s；`shutdown complete` |

### 本机部署实测（2026-10-23）

服务由用户级 launchd 管理，使用既有私有 `config.toml`；`launchctl kickstart -k` 重启后加载新代码，未修改配置。客户端与服务端同机，`batch=1`，固定合成语料，结果仅作观测。

| 场景 | 方法 | 实际 |
| --- | --- | --- |
| 部署与冒烟 | 重启 launchd 任务；`tests/verify_http.py --sparse` | `startup ready`；`PASS`；日志已含 `wait_ms` / `exec_ms` / `ahead` / `dedup` |
| 冷 / 热延迟 | 每档 5 次未命中 + 10 次同文本命中 | 25 / 945 / 5341 tokens：冷 P50 **48.9 / 270.0 / 2458.7 ms**，命中 P50 **1.7 / 2.2 / 5.9 ms**；实际 token 32 / 952 / 5349 |
| 请求内去重 | 3 条相同 5349-token 输入 vs 3 条不同输入 | 相同：墙钟 2480 ms、服务端 `exec_ms=2460`、`dedup=2`；不同：墙钟 7396 ms、`exec_ms=7379`、`dedup=0` |
| 429 / 排队 | 4×约 4089-token 长请求执行中，并发 20 个短请求 | 19×200 + 1×429 `queue_full`（`Retry-After: 1`）；`ahead` 0→19、`wait_ms` 5150–5540 ms、`exec_ms` 20–25 ms；长请求 `exec_ms=6604` |
| 内存 | 测试后 `vmmap -summary` | Physical footprint 1.2 GiB，峰值 1.4 GiB |

说明：

- 本机为 M5 / 32GB，数字与 README 中 M4 的观测不可直接比较；两者都是同机客户端、`batch=1` 的观测值，不是 SLA 或容量承诺。
- 本批不改变冷路径推理；冷延迟用于确认没有明显回退，不能据此宣称吞吐提升。命中路径的收益来自既有缓存，不是本批新增。
- 去重收益取决于请求内重复度：相同输入从 3 次推理降为 1 次，墙钟约 2.5 s vs 7.4 s。

补充说明：

- 真实服务验证使用临时配置（端口 8001、模型与日志指向本机路径），未改动私有 `config.toml`，未触碰 8000 端口上的既有进程；验证后已停止临时进程并删除含 Key 的临时配置，仅在被忽略的 `.cache/verify-0010/` 保留脱敏日志。随后本机正式部署已按上表通过 launchd 重启完成。
- 临时验证中的长请求为 4 条约 4084-token 文本，`exec_ms=6629`；19 个排队短请求全部 200，`ahead` 与 `wait_ms` 随位置递增，符合预期。
- 未执行：M4 部署、真实 30 秒排队超时（只触发 `queue_full`）、长时间 soak、生产观察；不据此承诺容量或 SLA。
- 未做性能前后对比：本批不改变冷路径推理，新增开销为每个请求的整数计数与一次字典分组；不宣称吞吐提升。

## 交付与遗留事项

已交付：

- 本机部署：用户级 launchd 任务已重启并加载新代码，沿用私有 `config.toml`；真实 HTTP 冒烟与实测通过。
- `scheduler.py`：任务记录 `enqueued_at` / `started_at` / `finished_at` / `ahead`。
- `app.py`：请求内按 token 序列去重、结果按原顺序映射；日志追加四个字段。
- `api.py`：`queue_full` / `queue_timeout` 返回 `Retry-After: 1`。
- `tests/test_api.py`：新增去重（缓存开 / 关）、日志指标、Retry-After 测试，并补充既有队列用例断言。
- 文档：PRD-0004、SPEC-0004、本 Plan、PRD/Spec/Plan 索引、连接说明、README、局限清单与 HANDOFF。

回滚：回退以上源码与测试后重启本机 launchd 任务即可；没有配置项或数据格式变更，不需要同步回退私有 TOML。

遗留：M4 部署与生产观察需另行授权；观察 1–2 周后再决定跨请求合并或准入控制。GPU 合批已由 [PLAN-0011](0011-batch-inference.md) 单独实施。
