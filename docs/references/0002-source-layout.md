# MLX 源码接入与服务代码结构

更新日期：2026-10-21。首版部署与后续本地改动的状态见 [HANDOFF](../../HANDOFF.md)。

## 实际布局

```text
BGE-Embedding/
├── environment.yml            # 两机独立创建 conda 环境
├── pyproject.toml             # 仅安装自有源码包
├── requirements.lock          # 固定版本与 wheel 哈希
├── config.example.toml        # 16 项运行配置示例，私有 config.toml 不入库
├── src/
│   ├── vendor/mlx/            # 独立上游克隆，仅供阅读
│   └── bge_embedding/
│       ├── __main__.py        # 原生启动与日志
│       ├── config.py          # TOML 加载、校验与路径解析
│       ├── app.py             # 生命周期、请求、健康状态
│       ├── api.py             # 输入与响应契约
│       ├── scheduler.py       # 有限串行队列
│       └── inference.py       # 本地模型、分词、CLS + L2
├── models/                    # 原有 8bit 快照与来源说明
├── deploy/                    # 私有 launchd 配置生成及运行说明
├── tests/                     # 默认基本 smoke 与真实 HTTP 冒烟
└── docs/                      # PRD、ADR、Spec、Plan
```

`app` 初始化模型并交由 `scheduler` 在唯一推理线程执行；`api` 处理契约，`inference` 不依赖 Web 框架。没有通用后端、插件、多模型或向量存储层。

## 上游与运行依赖

根目录已初始化 Git，`origin` 为 `https://github.com/LMQH/bge-embedding-server.git`，分支为 `main`。上游 MLX 是被忽略的独立克隆而非 submodule，来源见 [src/README](../../src/README.md)。不修改上游，也不从该目录编译或安装；运行环境使用锁定的 MLX 官方 wheel 与 mlx-embeddings 包。

源码包限定为 `src/bge_embedding`，不包含 vendor。权重、下载缓存、凭据和本地环境不纳入版本控制。两机分别使用 Miniconda / Miniforge 的 `bge-embedding`，不复制环境或开发机 prefix。

## 运行与验证

[部署说明](../../deploy/README.md) 给出安装、启停和基本调用命令。依照用户要求及 [ADR-0004](../adr/0004-minimal-verification.md)，默认仅做基本服务冒烟，不扩大参考比较、边界、压力或故障注入测试。未验证项在 Handoff / Plan 中明确记录。
