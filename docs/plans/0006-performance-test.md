# PLAN-0006：接口性能测试

- 状态：已完成（2026-10-21 执行并回填；结果仅作观测，不构成 SLA、容量或吞吐承诺）
- 关联：[PRD-0001](../prd/0001-embedding-service.md) · [SPEC-0001](../specs/0001-embedding-inference.md) · [ADR-0004](../adr/0004-minimal-verification.md)
- 目的：用 5 个通用指标和 3 组场景评价当前 M4 接口性能；结果只作观测和能力边界，不写成 SLA、容量或吞吐承诺。

## 目标与前置条件

- 目标机：Mac mini M4 16GB，macOS 26.5.1；项目环境 `bge-embedding`；当前运行配置为 1 个执行位 + 19 个等待位（总计 20 个位置），30 秒排队超时，单条 8192 tokens、批量 16、单请求 32768 tokens。见 [SPEC-0001](../specs/0001-embedding-inference.md) 与 [服务连接说明](../service-connection.md)。
- 测试窗口：当前服务在用，需先约定窗口；停止 launchd，用同一私有 `config.toml` 在本机手动启动，测试后恢复 launchd。Key 只从私有配置读取，不打印、不写入报告。
- 客户端与服务端同机，走 localhost，排除 Tailscale 网络延迟；不做跨机器对比。
- 长度档位取当前日志的实际值：25 / 945 / 5341 tokens；场景 2 的 mix 假设为 90% 25-token + 10% 5341-token。实际调用分布不同时替换档位和比例，并重算时长。
- 只测 batch=1。8192 全扫描、batch 16、20 以上的并发负载、30 秒超时实测、soak 不在本轮；仅保留一次 21 并发的 429 边界检查。

## 测试指标

| 指标 | 口径 |
| --- | --- |
| P50 / P95 / P99 E2E | 客户端发送到完整响应；按场景和长度分桶；P99 标注样本量，仅作参考 |
| QPS | 2xx 请求数 / 墙钟时间 |
| tokens/s | `usage.prompt_tokens` 总和 / 墙钟时间 |
| 错误率 | 5xx 比例；429 比例，区分预期与非预期 |
| 峰值内存 | 进程 RSS 高水位 + Metal 峰值 |
| 正确性门槛 | 1024 维、有限值、L2≈1、usage 正确；不计入性能指标 |

## 实施步骤

| 状态 | 场景 | 负载 | 输出 |
| --- | --- | --- | --- |
| 已完成 | 1. 延迟基线 | 25 / 945 / 5341 tokens，batch=1，并发 1；每档预热 5 次 + 测 100 次 | P50/P95/P99、QPS、tokens/s、错误率、峰值内存 |
| 已完成 | 2. 并发容量 | 90% 25-token + 10% 5341-token；并发 1 和 20，各 3 分钟；另做一次 21 并发检查，确认第 21 个 429 | 同上；记录 429 类型和队列超时 |
| 已完成 | 3. 资源峰值 | 在第 1、2 组期间采样 RSS 和 swap；用现有 `measure_attention.py` 对 5341 tokens 做 3 次 Metal 峰值测量 | RSS 高水位、Metal 峰值、swap 增量 |

## 执行方式

- 实际使用自研 `bench.py`（原始文件仅存于目标机与本机 `.cache/perf/`，不入库）：httpx 异步客户端，固定并发，逐请求记录 E2E、状态码、`usage.prompt_tokens`，并内置逐请求正确性校验；未用 k6/wrk2，也未用 curl 循环。
- 客户端记录每个请求的 E2E 时间、状态码和 `usage.prompt_tokens`；每组开始前预热 5 次。
- RSS 用 `ps -o rss= -p <pid>` 约 0.5 秒采样；swap 用 `vm_stat` 前后对比；Metal 峰值用现有 [`measure_attention.py`](../../tests/measure_attention.py)（模型级测量，不是 HTTP 级）。
- 每组前后各执行一次 [`verify_http.py`](../../tests/verify_http.py) 正确性冒烟。

## 测试时长分析

按当前观测中位数估算（25 tokens≈0.054s，945≈0.361s，5341≈2.540s；实际会有波动）：

| 阶段 | 计算 | 估算 |
| --- | --- | --- |
| 组 1：延迟基线 | 105 × (0.054 + 0.361 + 2.540) ≈ 310s；加 10% 开销 | 5.7 min |
| 组 2：并发容量 | 2 × 3 min + 预热 0.5 min + 21 并发检查 0.2 min + 排空 1 min | 7.7 min |
| 组 3：资源峰值 | 3 × 2.54s + 模型加载/开销 | ≈1 min |
| 纯执行 | 5.7 + 7.7 + 1 | 14.4 min |
| 准备/收尾 | 停/起服务、语料、健康与正确性冒烟 | 5 min（首次另加 10 min 语料准备） |
| 分析/报告 | 分位数、表格、内存与结论 | 15 min |
| 合计 | | ≈34 min；首次约 44 min |
| 含 20% 缓冲 | | ≈41 min；首次约 53 min |
| 可选 soak | 70–80% 负载 30 min | +30 min |

敏感性：

- 5341 档从 100 次加到 200 次：组 1 约 10.3 min，总时长约 39 min（首次约 49 min）。
- 若 P99 要作为结论，5341 需至少约 1000 次：该档约 42 min（比 100 次多约 38 min），不建议纳入首轮。
- 若实际最长是 8192 tokens：组 1 约 9.8 min，总时长约 38 min（首次约 48 min）。
- 首次语料准备约 10 min；后续复用为 0。

## 判定

- 5xx = 0；并发 1 时非预期 429 = 0；无 OOM、无持续 swap 增长。
- 正确性：每组前后执行冒烟，并抽检响应向量；抽检样本 100% 满足 1024 维、有限值、L2≈1、usage 正确。
- 并发 20 是配置上限，不是目标负载；该组的 429 / queue_timeout 如实记录，不作为失败。第 21 个并发返回 429 是预期行为。
- P95、QPS、tokens/s 只报实测值和基线对比；当前没有 SLA，不设绝对通过线。若后续需要，先补 PRD/Spec 目标。
- 峰值内存只做安全判断，不把 2 GiB 的 MLX 指导值当作硬配额。

## 验证记录

### 执行记录（2026-10-21）

- 环境：Mac mini M4（<REMOTE_HOSTNAME>，macOS 26.5.1 arm64，Python 3.12.15，httpx 0.28.1，numpy 2.5.4）；服务与客户端同机 `127.0.0.1:8000`；运行配置 1 执行位 + 19 等待位、30 秒排队超时。测量窗口 11:30:37–11:42:01（`results.json` environment 记录）。
- 流程偏差（如实记录）：
  - 编排脚本 `run_plan.sh` 首轮（11:06）手动服务启动失败退出（见 `run.log`，"startup failed"，原因未查明，列为遗留）；成功轮次按脚本同组命令手动执行，dry 输出命名为 `dry-live.json`（计划为 `dry.json`）。
  - 负载工具为自研 `bench.py`（httpx），非计划的 k6/wrk2；正确性校验内置于 bench，每个 200 响应校验 1024 维、有限值、L2≈1（±1e-5）与 usage，即全量校验而非抽检，三组异常计数均为 0。
- 真实命令（M4 项目环境，项目根）：
  - `python .cache/perf/bench.py --config config.toml --data .cache/perf/data/texts.json --output .cache/perf/results.json --pid <手动服务PID> --samples 100 --duration 180 --warmup 5`
  - `python tests/measure_attention.py --config config.toml --output .cache/perf/metal-5341 --lengths 5341 5341 5341`（先停止手动服务）
  - 服务启动后、压测前执行 `python tests/verify_http.py --config config.toml`
  - 语料由 `generate_data.py` 生成：固定 seed 20261021，25/945/5341 tokens 各 20 条，哈希记录在 `data/manifest.json`，纯合成文本
- 样本量：场景 1 三档各 100/100 成功；21 并发边界 21 次成功 20（1 次预期 429）；并发 1 共 767/767、并发 20 共 662/662（各 180 秒自然请求数）；RSS 采样 1345 次（约 0.5 秒间隔）。
- 主要结果：P50 25t = 25.1 ms / 945t = 273.9 ms / 5341t = 2616 ms；并发 20 P50 5565 ms；RSS 峰值 645440 KB ≈ 630.3 MiB；Metal 5341 三次峰值一致 838.2 MiB（active 575.7 MiB）；swap used 前后持平（793.38 MB），Swapouts 无新增，Swapins +20（vm_stat 页，系统级读入，非本测试写出）。
- 判定结果：5xx = 0；非预期 429 = 0（仅边界检查出现 1 次预期 429）；无 OOM、无持续 swap 增长；正确性异常 0 —— 满足本计划全部判定标准。P95/QPS/tokens/s 仅报实测值，不设通过线、不构成承诺。
- 原始证据：目标机 `.cache/perf/`；本机备份 `.cache/perf/m4/`（8 个关键文件两端 MD5 一致）。测试后服务已恢复 launchd 管理（当日 12:10 的 bootout/bootstrap 成功即证任务已在位运行）。
- 遗留：`run_plan.sh` 首轮失败原因未查明；30 秒排队超时路径未实测（并发未超过 20 + 19 等待位容量）；未做 soak、8192 全长、故障注入。

## 交付与遗留事项

- 原始结果写入 `.cache/perf/`，汇总表回填本 Plan；不提交模型、向量、Key 或用户文本。
- 完成后同步 [HANDOFF](../../HANDOFF.md)；若指标目标成为验收承诺，再更新 PRD/Spec。
- 本轮不改变服务实现、不新增接口、不做容量承诺。
