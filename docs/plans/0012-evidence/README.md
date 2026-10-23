# PLAN-0012 测试数据

本目录保存 [PLAN-0012](../0012-inference-optimizations.md) 各项优化的可审查证据。数据在本机 Mac mini M4 16GB、项目 conda 环境 `bge-embedding` 中生成；不包含模型权重、请求文本、Key 或本机绝对路径。

## 文件

| 文件 | 内容 |
| --- | --- |
| `baseline_bench.json` | P0：FP32 attention、合批路径的 16×25/256/512/1024、4×8192、混合长度耗时与峰值 |
| `fp16_bench.json` | P1：FP16 attention 的同场景耗时与峰值 |
| `quality_summary.json` | P1：dense/sparse 对 FP32 基线及合批对单条的误差；最终测试计数 |
| `baseline_quality.npz`、`fp16_quality.npz`、`*_sparse.json` | P0/P1：7 个长度样本的原始 dense 向量与 sparse 权重；仅用于审计数值差异 |
| `eval2_bench.json`、`eval3_bench.json`、`eval4_bench.json` | P2：每 2/3/4 层 `mx.eval` 的耗时与峰值 |
| `p2_eval.json` | P2：关键数字汇总与否决结论 |
| `p3_compile.json` | P3：固定 shape `mx.compile` 的耗时/峰值与 `shapeless` 失败结论 |
| `p4_baseline.json` | P4：跨请求微合批前的并发基线，3 次运行 |
| `p4_final.json` | P4：实现后的进程内并发结果，10 次运行；记录提交 `2cfc94f` |
| `p4_live_http.json` | P4：重启后的真实 HTTP 并发冒烟，3 次运行；服务监听本机回环 |
| `p4_live_http.py` | P4：真实 HTTP 并发采集脚本（从私有 TOML 取 Key，不打印） |
| `harness.py` | P0–P3 的基准/质量采集脚本（需本地模型与 `config.toml`） |
| `compare_quality.py` | dense/sparse 误差比较 |
| `p4_bench.py` | 通过 ASGI 传输、真实模型加载的并发基准；不使用外部 HTTP 服务 |
| `summarize_p4.py` | 汇总 P4 的中位数与范围 |

## 方法与限制

- P0–P3 使用真实本地模型、固定合成文本 `test ` 重复到目标 token 长度；先 warmup，再取设定重复次数的中位数。P0/P1 的原始 dense/sparse 输出与质量汇总均已归档；P2/P3 的原始耗时样本在 JSON 中。
- P4 的 `p4_baseline.json` / `p4_final.json` 通过 `httpx.ASGITransport` 在进程内加载真实 `create_app`；`p4_live_http.json` 则在 launchd 重启后的真实回环 HTTP 服务上采集。缓存开启，文本唯一以避免命中；每个 case 的所有请求同时发出。`20x1x25` 是 20 个并发单条 25-token 请求；`16x4x25` 是 16 个并发、每条 4 个 25-token 文本的请求。
- P4 的基线采集于 `8cdaf66`（FP16、未含微合批）；最终数据采集于 `2cfc94f`（含微合批）。两者在同一台机器、同一 conda 环境、同一脚本下生成，但不在同一进程内连续 A/B，因此仍受系统噪声影响；`p4_final.json` 保留每次运行的原始样本。
- P4 不是 HTTP 线上服务、不是容量/SLA 承诺；没有并发时微合批不产生收益。P95 采用每次运行的样本 P95，汇总表取多次运行的中位数。
- 所有测量仅供工程审查；生产部署与重启仍需单独授权。
