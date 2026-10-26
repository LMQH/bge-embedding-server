# 推理优化基准工具

本目录保存 PLAN-0012 的基准采集与分析脚本；历史结果及测量方法见 [验证附件](evidence/0012/README.md)。这些脚本按需手动运行，不由 pytest 自动收集。

| 脚本 | 用途 |
| --- | --- |
| [harness.py](harness.py) | 模型级基准与 dense/sparse 质量采集 |
| [compare_quality.py](compare_quality.py) | 比较 FP32 基线与 FP16 的 dense/sparse 误差 |
| [p4_bench.py](p4_bench.py) | 加载真实模型，通过进程内 ASGI 采集并发基准 |
| [p4_live_http.py](p4_live_http.py) | 从私有 TOML 读取 Key，采集已运行服务的 HTTP 并发结果 |
| [summarize_p4.py](summarize_p4.py) | 汇总微合批前后基准的中位数与范围 |

从仓库根目录运行，使用已核实的 `bge-embedding` conda 环境。脚本仍从根目录读取 `config.toml` 和 `.cache/opt/`，运行前须创建 `.cache/opt/`；模型采集需要本地权重与 Metal，HTTP 采集需要服务已启动。例如：

```sh
mkdir -p .cache/opt
conda run -n bge-embedding python tests/benchmarks/p4_bench.py --tag final --repeats 3
```

本目录保留历史实验工具，不能仅靠切换标签重建旧版本基线；复现须使用验证附件中记录的代码版本。原始质量数据保留采集时的 sparse 形态。
