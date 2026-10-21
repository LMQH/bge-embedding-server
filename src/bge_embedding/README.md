# 本项目推理服务代码

- `__main__.py`：单 worker 启动、关闭信号与安全轮转日志。
- `config.py`：启动时加载并校验完整 TOML；相对路径基于配置文件目录，私有文件不入库。
- `app.py`：模型生命周期、读取请求、鉴权、健康检查和调度调用。
- `api.py`：严格输入规则、token 限制、响应与安全错误。
- `scheduler.py`：单任务执行、有限 FIFO、排队超时和取消。
- `inference.py`：本地 8bit 加载、分词、强制融合双向注意力、逐层求值、原始 CLS + float32 L2。MLX 工作内存与缓存策略从配置加载，示例为 2 GiB / 256 MiB，均不是进程硬配额。

只使用各机 `bge-embedding` conda 环境。完整包版本见根目录 `requirements.lock`，实际运行与启停见 [部署说明](../../deploy/README.md)。`src/vendor/mlx/` 仅供阅读，不从此目录安装依赖。

验证按 [ADR-0004](../../docs/adr/0004-minimal-verification.md) 保持基本冒烟。进度及限制见 [HANDOFF](../../HANDOFF.md)。

长输入内存问题的定向回归和测量命令见 [PLAN-0003](../../docs/plans/0003-fused-attention.md)，不加入默认 smoke。适配层针对锁定的 mlx-embeddings 0.1.0 / MLX 0.32.4；升级这些依赖时需重新核对 attention 接口。
