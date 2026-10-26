# 推理基准工具

按需手动运行，不由 pytest 收集。从仓库根目录使用 `bge-embedding` 环境；历史结果见 [PLAN-0012 证据](evidence/0012/README.md)。

| 脚本 | 用途 |
| --- | --- |
| [harness.py](harness.py) | 模型级基准与 dense/sparse 质量采集 |
| [compare_quality.py](compare_quality.py) | FP32 与 FP16 的 dense/sparse 误差比较 |
| [p4_bench.py](p4_bench.py) | 加载真实模型，进程内 ASGI 并发基准 |
| [p4_live_http.py](p4_live_http.py) | 读取私有 TOML，采集已运行服务的 HTTP 并发 |
| [summarize_p4.py](summarize_p4.py) | 汇总微合批前后中位数与范围 |
| [service_load.py](service_load.py) | 真实 HTTP 基线、有界到达率、持续、过载与资源 / 日志采样 |
| [service_recovery.py](service_recovery.py) | 取消、SIGTERM、SIGKILL 与 launchd 恢复；会中断服务 |
| [summarize_service_load.py](summarize_service_load.py) | 生成成功吞吐、错误、分钟窗口与资源趋势报告 |

模型级采集需要本地权重与 Metal，并先 `mkdir -p .cache/opt`；HTTP 采集需要服务已启动，连接与 Key 只从私有 TOML / plist 读取：

```sh
mkdir -p .cache/opt
conda run -n bge-embedding python tests/benchmarks/p4_bench.py --tag final --repeats 3
```

生产补测（[PLAN-0015](../../docs/plans/0015-production-service-validation.md)）不加载第二份模型，仅用 tokenizer 构造精确长度的唯一输入：

```sh
python tests/benchmarks/service_load.py --launchd --profile baseline --output .cache/production-validation/baseline
python tests/benchmarks/service_load.py --launchd --profile mixed --rate 2.25 --duration 1800 --output .cache/production-validation/soak
python tests/benchmarks/summarize_service_load.py .cache/production-validation --output .cache/production-validation/report.json
```

`--profile overload` 制造过载；`service_recovery.py` 会停止或终止当前服务，仅在已授权窗口运行。唯一输入避免缓存误计；报告不含地址、Key、文本或向量。RSS 与系统 swap 不等于 Metal 峰值。2026-10-26 M4 结果见[证据](evidence/0015/README.md)。
