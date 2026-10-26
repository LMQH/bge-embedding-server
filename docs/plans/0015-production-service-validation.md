# PLAN-0015：M4 服务生产补测

- 状态：已完成（2026-10-26）
- 环境：Mac mini M4 16GB，macOS 26.5.1，项目 miniforge 环境 Python 3.12.15；服务 `90b3f4e`（v1.1.0），同机回环 HTTP 客户端
- 关联：[SPEC-0001](../specs/0001-embedding-inference.md) AC-001～003、007～010；[SPEC-0002](../specs/0002-dense-sparse-output.md) AC-201～205；[SPEC-0003](../specs/0003-result-cache.md) AC-301～305、308；[SPEC-0004](../specs/0004-request-observability-and-dedup.md) AC-401、402、404、406
- 范围：当前部署版本的 HTTP 吞吐、延迟、资源趋势、过载与进程恢复。不改服务行为，不新增 SLA

## 场景与预算

| 阶段 | 方法 | 预算 |
| --- | --- | ---: |
| A 预检与冒烟 | 核对版本 / 解释器 / 配置；`verify_http.py --launchd --sparse --long` | 10 min |
| B 基线 | 单条 32 / 512 / 2048 × dense / dual 各 100 次；16×512 各 20 批；8192 少量调用；缓存命中独立测 | 15 min |
| C 阶梯 | 短查询 20 / 40 / 80 rps；混合 1 / 2 / 3 rps，各 5 min | 30 min |
| D 持续 | 最高干净档的 75%，固定混合负载 30 min | 30 min |
| E 过载 | 超出总位置数的长批突发、等待中 / 执行中取消、随后正常负载 | 10 min |
| F 恢复 | SIGTERM 下等待 503 / 执行完成；SIGKILL 后 launchd 拉起 | 10 min |

负载用 tokenizer 预生成精确长度、互不重复的 token 序列，到达率由单调时钟调度，不等待上一响应；记录发出、丢发、调度迟延与全部结果分母。测量窗口不含生成与分词。

## 判定

- 契约：输出条数、`index`、`usage`、1024 维有限值与归一、sparse 键合法性全部校验；正常负载无 5xx / 429 / 客户端超时；过载按 code 与 `Retry-After` 分类；取消与拒绝后可恢复；优雅停止与异常拉起分别核验。
- 容量：满足延迟与错误要求的最高实测到达率。短查询 / 批量 P95 目标未定义，只交付曲线与首次拒绝点，不宣布 SLO 容量。
- 稳定性：同负载首尾 10 分钟吞吐下降 ≤10%、各类 P95 上升 ≤20%；RSS / swap 不持续增长。
- 未覆盖：能耗、Metal 峰值（RSS 不等于 Metal 峰值）、整机重启 / 登录、跨主机客户端。

## 执行入口

```sh
python tests/verify_http.py --launchd --sparse --long
python tests/benchmarks/service_load.py --launchd --profile baseline --output .cache/production-validation/baseline
python tests/benchmarks/summarize_service_load.py .cache/production-validation --output .cache/production-validation/report.json
```

`service_recovery.py` 会中断服务，仅在已授权窗口运行。原始数据留在忽略目录 `.cache/production-validation/`；脱敏汇总与逐阶段数字见[证据](../../tests/benchmarks/evidence/0015/README.md)。
