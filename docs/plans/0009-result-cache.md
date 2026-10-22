# PLAN-0009：嵌入结果缓存实施

- 状态：已完成，2026-10-22；本机实现与单元验证完成，M4 部署与真实验证完成（用户明确授权"推到 Mac mini 上去测试"）。
- 关联：[PRD-0003](../prd/0003-result-cache.md)（已确认）、[ADR-0006](../adr/0006-in-memory-result-cache.md)（已接受）、[SPEC-0003](../specs/0003-result-cache.md)（已确认）。

## 目标与前置条件

为 `/v1/embeddings` 增加进程内 LRU 结果缓存：配置、缓存模块、API 接线、测试、文档与本机真实服务验证。行为实现以已确认的 SPEC-0003 为前提——步骤 0 完成前不写代码。M4 部署不在本计划自动执行，需用户单独授权。依赖：本地 conda 环境为 `bge-embedding`（命令沿用 PLAN-0007 验证记录中实际执行的命令，不猜测环境名）。

## 实施步骤

| 状态 | 步骤与关联 Spec 场景 | 涉及目录或文件 | 验证标准 |
| --- | --- | --- | --- |
| 完成 | 0. 用户确认 PRD-0003、ADR-0006、SPEC-0003（2026-10-22 指示"执行修改，推到 Mac mini 上去测试"） | `docs/prd/0003-result-cache.md`、`docs/adr/0006-in-memory-result-cache.md`、`docs/specs/0003-result-cache.md` | 状态改为已确认 / 已接受，记录确认来源 |
| 完成 | 1. 配置扩展：新增 `[cache]` 段（AC-306、AC-307） | `src/bge_embedding/config.py`、`config.example.toml`、`tests/test_config.py` | 缺段 / 未知项 / 非法值拒绝启动；enabled=false 合法；现有配置测试回归通过 |
| 完成 | 2. 缓存模块：键计算、LRU 字节预算、命中转换（AC-301、AC-304、AC-305） | `src/bge_embedding/cache.py`（新）、`tests/test_cache.py`（新） | 命中逐位一致；淘汰不超预算；超大条目不缓存；flag 键隔离；仅标准库 |
| 完成 | 3. API 接线：校验后查缓、miss 子批调度、结果回填、顺序合并、日志命中数（AC-302、AC-303） | `src/bge_embedding/app.py`、`tests/test_api.py` | 部分命中顺序与 usage 正确；全命中不经调度器；推理失败不回填；现有 API 测试回归通过 |
| 完成 | 4. 冒烟扩展：`--warm` 连续两次同一请求并输出两次耗时（AC-301、AC-303、AC-308） | `tests/verify_http.py` | 真实服务通过；dense-only 与 `--sparse` 路径回归通过 |
| 完成（按用户指示调整） | 5. 真实模型验证：用户指示不跑本机真实验证，真实验证全部移至 M4 执行 | — | 本机仅非 real 单元回归；M4 部署后补齐真实场景 |
| 完成 | 6. 文档同步：SPEC-0001 范围变更注记、源码与部署 README、HANDOFF 摘要、本 Plan 回填 | `docs/specs/0001-embedding-inference.md`、`docs/README.md`、`src/bge_embedding/README.md`、`deploy/README.md`、`HANDOFF.md` | 索引与实现一致；HANDOFF 更新日期与摘要 |
| 完成 | 7. M4 部署与线上验证（用户 2026-10-22 明确授权） | M4 项目目录、私有 `config.toml`、launchd | 部署成功，真实验证全项通过，详见验证记录 |

## 验证记录

环境：本机 Miniconda `bge-embedding`（Python 3.12.15 / arm64，M5 32GB）；目标机 Miniforge `bge-embedding`（macOS 26.5.1，M4 16GB）。按用户指示，本机不跑真实模型验证；真实场景全部在 M4 线上服务执行。

### 本机单元验证

- `python -m pytest -q -m 'not real'`：**92 passed, 2 deselected**（改动前基线 72 passed；新增 20 项 = test_cache 9 项 + test_api 5 项 + test_config 参数化 5 项 + 配置加载 1 项）。
- `python -m pytest -q`（默认 `-m smoke`）：**4 passed**。
- 覆盖场景：AC-301（单元部分）、AC-302、AC-304、AC-305（单元部分）、AC-306、AC-307；既有队列 / FIFO / 超时 / 断开 / 鉴权测试全部回归通过。

### M4 部署

| 项 | 结果 |
| --- | --- |
| 通道 | SSH 公钥认证（用户授权后一次性安装本机公钥至 M4 `authorized_keys`，密码用后即弃、未落盘） |
| 预检备份 | `.cache/deploy-cache-20261022-115940/`（权限 700；含 src / tests / docs / deploy / config.example.toml / config.toml / plist；config.toml 权限 600，SHA-256 前 16 位 `12a67f1f231ac0f4`） |
| 同步 | `rsync -avR`（src / tests / docs / deploy / config.example.toml，不带 `--delete`，不触碰模型权重） |
| 配置变更 | 私有 `config.toml` 由远端脚本插入 `[cache]` 段（enabled=true, max_bytes=268435456）；`load_config` 校验通过；文件保持 600 |
| 部署前测试 | M4 `pytest -q -m 'not real'`：**92 passed, 2 deselected**（与本机一致） |
| 重启 | `launchctl bootout` + `bootstrap`，**3 秒后 healthz 200 / ready** |

### M4 真实验证（AC 对照）

| 场景 | 命令 / 方式 | 结果 |
| --- | --- | --- |
| AC-301、AC-305、AC-308 | `verify_http.py --launchd --sparse --long --warm` | warm cache：cold **0.047s** → warm **0.002s**，两次响应 `data` JSON 全等（逐位一致）；sparse 键值路径命中一致 |
| 基线回归 | 同上 | 8192 tokens **4.75s**（基线 4.79s，无回退）；健康、鉴权、单条、两条批量、1024 维归一化、sparse 全项 PASS |
| AC-303 | 一次性并发脚本（`.cache/ac303_test.py`，验证后已删除） | 8192-token 长请求推理中（4.81s），并发已缓存短请求 **0.0037s 返回 200**，未排队、未 429 |
| AC-308 日志 | `logs/service.log` 检查 | `hits=1` / `hits=0` 正常记录；无 Bearer / Key / 原文 / 向量（grep 复核 0 命中） |
| RSS 观测 | 部署后全量验证负载完成时 | **1295 MiB**（含 8192 长请求峰值残留与缓存占用的观测口径，非稳态空闲值；16GB 机器安全余量充足） |

记录一次失败重测：AC-303 首次用中文样本「测试 」×8190，token 数超 8192 被拒（400），导致长请求未进入推理、结果假阳性；改用 PLAN-0007 同款英文样本 `\"test \" * 8190` 重测通过。该教训已体现：并发验证必须先断言长请求 200。

### 独立代码审查与修复（2026-10-22，第二轮）

实现完成后按 Standard 通道追加独立 `code-review` 审查（审查对象为工作区未提交变更，非实现方自审）。结论：四个重点方向（cache.py 正确性、app.py 接线、契约一致性、生命周期）均「未发现缺陷」；提出 2 个低级发现与数条建议，处置如下：

| 发现 | 处置 |
| --- | --- |
| cache.py 使用 numpy，与 SPEC-0003「仅用标准库」字面不符 | 已修复：改用 `array.array("f")`（与 float32 往返逐位等价），实现达到纯标准库，契约无需修订 |
| 「推理失败 / 客户端断开不回填」缺直接单元断言 | 已修复：补 `test_inference_failure_does_not_backfill`、`test_client_disconnect_does_not_backfill` |
| 键拼接字节序与契约文本相反（flag‖tokens vs tokens‖flag） | 已修复：实现调换为契约顺序；定宽字段本无碰撞，行为不变 |
| store 内 cache_key 重复计算 | 已修复：循环内一次计算复用 |
| sparse dict 只读未强制 | 部分采纳：审查建议的 `MappingProxyType` 不可用（json 不识别），改为 docstring 固化只读不变量 |
| partial hit 测试断言弱（常量向量无法区分槽位） | 已修复：测试改用 token 区分向量，断言命中槽取自缓存、推理槽来自新推理 |
| [cache] 段未知键无专属校验样本 | 已修复：补 `enbled = true` 参数化样本 |
| 重复键测试窥探私有 `_entries` | 容忍现状（审查者标注低优先级） |

修复后复验：

- 本机 `pytest -q -m 'not real'`：**95 passed, 2 deselected**（+3 项）；默认 smoke **4 passed**。
- M4 同步修复版后 `pytest -q -m 'not real'`：**95 passed**；重启 3 秒 ready。
- M4 `verify_http.py --launchd --sparse --long --warm`：warm cache cold **0.061s** → warm **0.003s**；8192 tokens **5.00s**；全项 PASS。

### 延迟复测（2026-10-22，同 PLAN-0006 标准，缓存版本）

按用户要求沿用 [PLAN-0006](0006-performance-test.md) 的同一套标准复测，重点为延迟：同 `bench.py`、同语料（seed 20261021，25/945/5341 tokens 各 20 条）、同参数（三档各预热 5 + 测 100；21 并发边界检查；并发 1 与 20 各 180 秒；RSS/swap 采样），客户端与服务端同机 localhost。为公平归因，跑两轮：**A 缓存禁用**（复现无缓存口径）、**B 缓存启用**（线上现状）。

场景 1（并发 1，每档 100 次）：

| 档位 | 基线 10-21（无缓存） | A 缓存禁用 | B 缓存启用（P50） |
| --- | --- | --- | --- |
| 25 tokens | P50 25.1 ms | P50 21.7 / P95 23.4 / P99 25.7 ms | **P50 4.6 / P95 32.6 / P99 43.8 ms** |
| 945 tokens | P50 273.9 ms | P50 270.8 / P95 276.3 / P99 278.0 ms | **P50 7.1 / P95 273.2 / P99 274.3 ms** |
| 5341 tokens | P50 2616 ms | P50 2589.4 / P95 2632.9 / P99 2650.8 ms | **P50 6.8 / P95 2441.3 / P99 2455.7 ms** |

口径说明：B 轮每档 100 次中 15 次为冷（20 条语料仅预热了前 5 条），85 次为命中；P95/P99 落在冷样本上，等于冷推理延迟。945t 冷延迟 273.2 ms ≈ A 轮 270.8 ms ≈ 基线 273.9 ms，**未命中路径无回退**；5341t 冷 2441 ms 略优于基线（冷样本仅 15 次，热/节流压力更小）。

场景 2（180 秒，90% 25-token + 10% 5341-token）：

| 并发 | 基线 10-21 | A 缓存禁用 | B 缓存启用 |
| --- | --- | --- | --- |
| 1 | 767 请求 / QPS 4.26 | 829 请求 / QPS 4.55 / P50 21.9 ms | **32,636 请求 / QPS 181.3 / P50 3.2 ms** |
| 20 | 662 请求 / QPS 3.68 / P50 5565 ms | 720 请求 / QPS 3.78 / P50 5326 ms | **135,047 请求 / QPS 750.2 / P50 13.1 ms / P95 86.3 ms** |

注意：B 轮并发吞吐由缓存命中主导（每档仅 20 条语料，预热后全部命中），750 QPS 是缓存路径吞吐，不代表冷推理吞吐；冷推理吞吐以 A 轮为准。

21 并发边界检查：

- A 轮（禁用）：20×200 + 1×429 `queue_full`，与基线一致（预期行为）。
- B 轮（启用）：21×200，`expected_429_observed=false`。符合 SPEC-0003：全命中请求不进入调度器、不占队列位置，因此不触发 `queue_full`。这是已确认的语义变化，不是缺陷。

资源与正确性：

- 两轮 5xx = 0、非预期 429 = 0；每轮前后 `verify_http.py` 冒烟通过。
- 正确性校验：A 轮 vector 校验 242 项、B 轮 3,574 项，全部 1024 维/有限/L2≈1；`token_mismatch` 均为 0。
- swap：两轮前后 Swapouts / Swapins 完全持平，无新增写出。
- Metal 5341×3（禁用轮，独立进程）：峰值 878.97 MB ≈ 838.4 MiB，与基线 838.2 MiB 一致；耗时 2.438 / 2.447 / 2.447 s。
- RSS：A 轮（手动服务，PID 正确）峰值 740,336 KB ≈ 723 MiB；B 轮 bench 采样 PID 异常（数值 100–176 MiB 与直接观测不符，判为无效证据，不予采用），改为直接观测：部署后长时间负载的常驻 RSS ≈ 1,290 MiB（含模型、MLX 分配器缓存与分配器碎片），低于 2 GiB 指导值，16GB 机器余量充足。

证据：M4 `.cache/perf/results-cache-on.json`、`results-cache-off.json`、`metal-5341-recache.json`；临时禁用配置（含 Key 副本）用后已删除。测试期间 launchd 服务曾 bootout 以便手动起禁用配置，测后已恢复并冒烟通过。

## 回滚方案（如需）

```sh
launchctl bootout gui/$(id -u)/local.bge-embedding
# 从 .cache/deploy-cache-20261022-115940/ 恢复 src/、config.toml（关键：旧代码遇未知 [cache] 段会拒启，必须连配置一起回滚）
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.bge-embedding.plist"
```

## 交付与遗留事项

- 交付：`cache.py` 缓存模块、`app.py` 接线、`config.py` / `config.example.toml` 配置扩展、测试 23 项新增、`verify_http.py --warm`、文档五处同步；M4 线上已运行缓存版本（含独立审查修复）并全项验证通过。
- 遗留：命中率与生产收益取决于实际负载重复度，通过 `hits=` 日志字段持续观察；256 MiB 字节预算为示例基线，RSS 1295 MiB 为负载后观测值，长期运行水位待观察；微批优化与本缓存正交，按 HANDOFF 原则等实际问题再立项。
- SSH 通道变更：本机公钥已装入 M4 `<REMOTE_USER>` 的 `authorized_keys`（经 Tailscale），后续部署免密；该事实仅记录存在，不在文档保存地址与凭据。
