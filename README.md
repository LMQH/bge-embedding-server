# BGE-Embedding

面向 macOS 的文本嵌入 API，为知识库 / RAG 提供文档与查询向量。采用 BGE-M3 8bit 模型，通过 MLX 使用 Apple Silicon GPU 推理。

## 能力概览

- **文本向量化**：支持中英文等多语言纯文本，返回 1024 维、L2 归一化的稠密向量。
- **单条与批量调用**：提供 OpenAI Embeddings 风格的 `POST /v1/embeddings` 接口，使用共享 API Key 认证。
- **可选稀疏输出**：通过 `return_sparse` 请求 BGE-M3 原生稀疏权重，契约见 [SPEC-0002](docs/specs/0002-dense-sparse-output.md)。具体部署版本的支持情况见 [HANDOFF](HANDOFF.md)。
- **重复输入缓存**：在进程内复用嵌入结果，支持容量限制与 LRU 淘汰，重启后清空。
- **原生 macOS 运行**：使用独立 conda 环境、TOML 配置和用户级 launchd；单模型串行推理，有界排队。

调用方负责文件解析与文本切分。默认单条上限为 8192 tokens，超长输入拒绝处理；完整限制见[接口使用说明](docs/service-connection.md)。

## 运行环境与版本

当前运行基线为 **Apple Silicon（arm64）与 macOS 26 或以上**，系统版本下限来自锁定的 MLX wheel。主要版本如下：

| 组件 | 版本 / 约定 |
| --- | --- |
| 服务包 `bge-embedding` | `0.1.0` |
| Python | `3.12.15`，原生 arm64 |
| conda 环境 | `bge-embedding`，使用 `conda-forge`；开发机为 Miniconda，生产实测机为 Miniforge |
| MLX / mlx-metal | `0.32.4` / `0.32.4` |
| mlx-embeddings / mlx-vlm | `0.1.0` / `0.4.0` |
| Transformers / Tokenizers | `5.19.0` / `0.23.3` |
| FastAPI / Uvicorn | `0.143.1` / `0.54.0` |
| 模型 | `mlx-community/bge-m3-mlx-8bit`；固定 revision 与稀疏头版本见[模型说明](models/README.md) |

Python 与环境声明以 [environment.yml](environment.yml) 为准，Python 包的完整精确版本与 wheel 哈希以 [requirements.lock](requirements.lock) 为准，包元数据与依赖约束见 [pyproject.toml](pyproject.toml)。conda 用于管理独立环境，其自身版本不在项目依赖锁中；两机分别创建环境，不复制环境目录。

**真实生产部署与实测示例**：Mac mini M4、16GB 统一内存、macOS `26.5.1`，使用 Miniforge 管理的 Python `3.12.15` 环境。该配置是已有部署实例；项目面向上述 macOS / arm64 运行基线，其他硬件配置仍需各自验证。部署与基本验证见 [PLAN-0002](docs/plans/0002-minimal-service.md)，性能基线与缓存复测分别见 [PLAN-0006](docs/plans/0006-performance-test.md) 和 [PLAN-0009](docs/plans/0009-result-cache.md)。

## 开始使用

**连接已有服务**：向部署方获取地址与 API Key，按[连接与使用说明](docs/service-connection.md)调用。设置 `BGE_BASE_URL`（服务根地址，不含 `/v1`）与 `BGE_API_KEY` 后：

```sh
curl --fail "${BGE_BASE_URL}/v1/embeddings" \
  -H "Authorization: Bearer ${BGE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"bge-m3","input":["用于知识库检索的文本"],"encoding_format":"float"}'
```

向量位于响应的 `data[0].embedding`。`GET /healthz` 可用于检查服务是否就绪，无需 API Key。

**自行部署**：从[运行与部署](deploy/README.md)开始，按上述版本基线建立 `bge-embedding` 环境，再按[模型说明](models/README.md)获取权重、生成私有配置并启动。权重、凭据与本地配置不纳入版本控制。

## 文档与代码

| 你想了解 | 入口 |
| --- | --- |
| 当前部署版本、验证结果与后续工作 | [项目进度与交接](HANDOFF.md) |
| 接口参数、认证与错误响应 | [连接与使用说明](docs/service-connection.md) |
| 环境安装、配置、启动与常驻运行 | [运行与部署](deploy/README.md) · [配置示例](config.example.toml) |
| 模型来源、固定版本与下载方式 | [模型说明](models/README.md) |
| 需求、架构决策、行为规格与实施记录 | [文档中心](docs/README.md) |
| 服务代码与上游源码布局 | [源码说明](src/README.md) · [测试目录](tests/) |
| 参与开发时的协作约定 | [AGENTS.md](AGENTS.md) |

本项目采用 SDD（规格驱动开发）：先确认 Spec，再制定计划、实现并按规格验收。具体流程见[文档中心](docs/README.md)。
