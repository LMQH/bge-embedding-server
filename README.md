# BGE-Embedding

**在 Apple Silicon 上自托管 BGE-M3 的嵌入推理服务。**

面向知识库与 RAG 的内网 Embedding API：一台 Mac mini、一个模型进程，提供 1024 维稠密向量与可选的稀疏词权重；接口沿用 OpenAI Embeddings 的基础请求形状。部署后，模型、文本和向量都留在内网，不依赖外部推理 API。

> **BGE-M3 8bit** · **1024 维 dense** · **可选 sparse** · **8192 tokens** · **单机部署**
>
> **Python 3.12** · **FastAPI / Uvicorn** · **MLX / Metal**

## 核心能力

- **私有部署**：模型从本地加载，主权重与稀疏头固定 revision / 校验值；请求文本与向量不落盘；服务运行时不下载模型，也不调用外部 API。
- **Apple GPU 原生推理**：8bit BGE-M3 直接运行在 M 系列芯片的 Metal 上，一台 Mac mini 即可对外服务。
- **一次前向，两路信号**：开启 `return_sparse` 时，dense 与 sparse 共享同一次模型前向，便于做语义 + 词面混合检索。
- **为单机设计的有界性**：单 worker、单模型串行执行；1 个执行位 + 19 个等待位；请求体、批量与 token 均有上限，过载明确返回 429。
- **重复请求走缓存**：进程内 LRU 按 token 哈希复用结果，全命中请求不占用执行位或等待位。
- **可运维**：18 项参数集中在一个私有 TOML（[示例](config.example.toml)），启动时严格校验；`GET /healthz` 探活；launchd 常驻；轮转日志只记录安全元数据。

## 工作方式

```text
客户端
  │  POST /v1/embeddings   Authorization: Bearer <Key>
  ▼
FastAPI
  │  鉴权 · 严格校验 · 1 MiB 请求体上限
  ▼
tokenize ──► 缓存查询 ──命中──► 直接返回（不进入推理队列）
  │ 未命中
  ▼
有界 FIFO（1 个执行位 + 19 个等待位，30 秒排队超时）
  ▼
MLX / Metal
  │  BGE-M3 8bit · 融合双向注意力 · 逐层求值
  │  CLS 池化 + float32 L2 归一化
  │  可选：原生稀疏头 → token 级正权重
  ▼
JSON 响应（dense / dense + sparse）
```

单 worker、单模型实例；批内逐条推理，不承诺 GPU 合批——优先保证单机资源可预测，而不是通用高并发。缓存只驻留进程内存，重启即清空。

选择 BGE-M3 + MLX 的原因很直接：BGE-M3 原生同时提供 dense 与 sparse 信号，MLX 则直接利用 Apple Silicon 的 Metal 与统一内存；不引入第二个稀疏模型，也不依赖外部向量服务，延迟、内存和隐私边界都留在同一个进程里。依据见 [ADR-0002](docs/adr/0002-bge-m3-mlx.md) 和 [ADR-0005](docs/adr/0005-native-sparse-head.md)。

## 快速开始

已有部署时，向部署方获取地址与 API Key，直接看 [API](#api)；以下是从零自建。所有命令均在项目根目录执行。

### 前置条件

- Apple Silicon（arm64）Mac，macOS 26 或以上（当前锁定 MLX wheel 的要求）
- 建议 16GB 统一内存
- Miniconda 或 Miniforge，项目环境名 `bge-embedding`
- 约 604 MB 模型权重；首次获取需要网络

| 组件 | 锁定版本 |
| --- | --- |
| Python | 3.12.15，arm64 |
| MLX / mlx-metal | 0.32.4 |
| mlx-embeddings / mlx-vlm | 0.1.0 / 0.4.0 |
| FastAPI / Uvicorn | 0.143.1 / 0.54.0 |
| 模型 | `mlx-community/bge-m3-mlx-8bit`，revision 见[模型说明](models/README.md) |

完整版本与 wheel 哈希见 [requirements.lock](requirements.lock)，环境声明见 [environment.yml](environment.yml)。

### 1. 安装环境

```sh
conda env create -f environment.yml
conda activate bge-embedding
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
```

### 2. 获取模型与稀疏头

```sh
hf download mlx-community/bge-m3-mlx-8bit \
  --revision 7eca4a1c6ea1a0c5efc37598b369012f3985910f \
  --local-dir models/bge-m3-mlx-8bit

python deploy/fetch_sparse_head.py
```

模型权重与稀疏头都不入库。来源、校验值和离线方式见 [模型说明](models/README.md)。稀疏头是启动前置条件：即使只调用 dense，缺失时服务也会拒绝启动，不会静默降级。

### 3. 生成私有配置并启动

```sh
python deploy/install.py --config "$PWD/config.toml"
python -m bge_embedding --config "$PWD/config.toml"
```

`install.py` 会生成权限 600 的 `config.toml`（含随机 Key）和 launchd plist，但不会启动服务。常驻、登录自启与停止方式见 [部署说明](deploy/README.md)。

### 4. 冒烟

另开一个终端：

```sh
python tests/verify_http.py --config "$PWD/config.toml" --sparse
```

该脚本从同一份 TOML 读取地址与 Key，检查健康状态、鉴权、单条 / 批量、向量形状与稀疏输出；加 `--long` 会追加 8192-token 输入。

## API

`POST /v1/embeddings`，JSON 请求，共享 Key 鉴权。`GET /healthz` 无需鉴权：就绪返回 `200 {"status":"ready"}`，否则返回 `503 {"status":"not_ready"}`。

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `model` | 是 | 固定为 `bge-m3` |
| `input` | 是 | 单个字符串或非空字符串数组；不接受空串、纯空白、token ID 数组 |
| `encoding_format` | 否 | 默认 `float`，仅接受 `float` |
| `return_sparse` | 否 | JSON 布尔值，默认 `false`；为 `true` 时每项额外返回 `sparse` |

未知字段、错误类型或空输入会整单拒绝，不会返回部分结果。

```sh
curl -s http://127.0.0.1:8000/v1/embeddings \
  -H "Authorization: Bearer $BGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bge-m3",
    "input": ["知识库文档", "An English query"],
    "encoding_format": "float"
  }'
```

响应结构（`embedding` 实际为 1024 项，此处仅示意前三项）：

```json
{
  "object": "list",
  "model": "bge-m3",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.0123, -0.0456, 0.0789]
    }
  ],
  "usage": {"prompt_tokens": 10, "total_tokens": 10}
}
```

每条 dense 恰好 1024 个有限数值，已完成 L2 归一化；`data` 按输入顺序排列，`index` 从 0 开始；`usage` 为整批输入 token 总数。

需要稀疏输出时传 `"return_sparse": true`，每项会多一个以十进制 token id 字符串为键、正权重为值的对象：

```json
{
  "object": "embedding",
  "index": 0,
  "embedding": [0.0123, -0.0456, 0.0789],
  "sparse": {"81492": 0.3436, "24471": 0.24}
}
```

同一 token 多次出现取最大权重，特殊 token 不出现；不做额外的归一化或截断。`BGE_API_KEY` 从私有 `config.toml` 的 `auth.api_key` 读取，不要写进仓库或共享文档。

这是 OpenAI Embeddings 风格的**兼容子集**，不是完整兼容：不支持 `dimensions`、`user`、模型列表、base64 输出等；使用 OpenAI SDK 时请显式传 `encoding_format="float"`。

### 容量与错误

| 项目 | 默认值 |
| --- | --- |
| 单条输入 | 8192 tokens（含特殊 token） |
| 单请求 | 16 条 / 32768 tokens / 1 MiB |
| 执行与等待 | 1 个执行位 + 19 个等待位 |
| 排队超时 | 30 秒（仅等待时间，不含已开始的推理） |

| HTTP | code | 场景 |
| --- | --- | --- |
| 400 | `invalid_request` / `input_too_long` / `batch_limit_exceeded` | 字段、类型、空输入、长度或批量超限 |
| 401 | `invalid_api_key` | Key 缺失、为空或不匹配 |
| 413 | `request_too_large` | 请求体超过 1 MiB |
| 429 | `queue_full` / `queue_timeout` | 队列已满或等待超时 |
| 503 | `model_unavailable` | 服务未就绪或正在关闭 |
| 500 | `inference_failed` | 推理异常或输出不符合数值契约 |

错误响应使用固定安全描述，不回显用户文本、Key 或本地路径；日志同样只记录安全元数据。

以上为示例基线，可在私有 TOML 中调整；执行位与 worker 固定为 1。完整字段规则、失败语义与验收场景见 [SPEC-0001](docs/specs/0001-embedding-inference.md) 和 [SPEC-0002](docs/specs/0002-dense-sparse-output.md)。双路输出需要目标机部署对应版本并准备稀疏头；当前线上启用范围以 [项目进度与交接](HANDOFF.md) 为准。

## 性能观测

在 Mac mini M4 16GB（macOS 26.5.1）上测得，客户端与服务端同机、`batch=1`、固定合成语料：

| 输入长度 | 无缓存 P50（10-21 基线） | 缓存命中 P50（10-22） |
| --- | --- | --- |
| 25 tokens | 25.1 ms | 4.6 ms |
| 945 tokens | 273.9 ms | 7.1 ms |
| 5341 tokens | 2616 ms | 6.8 ms |

- 8192 tokens 冷推理约 4.8 秒；无缓存时进程 RSS 峰值约 630 MiB，缓存版本在长时间负载后约 1.3 GiB（含模型、MLX 分配器缓存与结果缓存），16GB 机器仍有充足余量。
- 命中主导的 20 并发混合负载观测到 750 QPS；冷推理路径约 4 QPS 量级，两者不可直接比较。
- 以上均为 2026-10-21 / 10-22 的观测值，不是 SLA、容量或吞吐承诺；缓存收益取决于实际重复率。方法与原始数据见 [PLAN-0006](docs/plans/0006-performance-test.md)、[PLAN-0009](docs/plans/0009-result-cache.md)。

## 适用场景与边界

**适合**

- 内网知识库 / RAG 的文档入库与在线查询
- 语义搜索、文本去重、聚类与分类特征
- 希望数据不出内网、又不想自建 GPU 集群的团队
- 需要 dense + sparse 混合检索信号，但不想维护第二套模型

**不负责**

- 文件解析、文档切分、向量库、检索与 rerank
- 多租户、生产级账号体系、计费与配额
- 多模型、多机调度、水平扩展或高可用
- 冷推理的高并发 SLA（单机单模型串行，不承诺）
- 与 OpenAI Embeddings 全量 API 的完全兼容
- Docker / 容器化部署（依赖 macOS Metal，采用原生运行）

服务面向内网与共享 Key 的非生产场景；用户级 launchd 需要保持登录，机器睡眠或未登录时不承诺可访问。8bit 量化模型与官方 fp16 全模型不保证逐位一致；本项目未做检索效果评测，不承诺召回提升。逐条的分层清单（设计取舍 / 能力缺口 / 未验证风险）见[当前服务的局限性](docs/references/0003-service-limitations.md)。

## 项目结构

```text
src/bge_embedding/   服务实现：API、配置、调度、缓存、MLX 推理
src/vendor/mlx/      MLX 源码参考（不入库、不参与安装）
models/              模型来源与获取说明（权重不入库）
deploy/              安装、稀疏头获取、launchd 部署
tests/               单元测试、smoke、真实 HTTP 验证
docs/                PRD / ADR / Spec / Plan 与参考资料
```

```sh
python -m pytest -q                 # 默认 smoke
python -m pytest -q -m 'not real'   # 不依赖真实模型的单元回归
```

## 文档

项目采用 SDD（Specification-Driven Development）：需求、决策、行为契约与实施记录分别落在 PRD、ADR、Spec 和 Plan 中，入口见[文档中心](docs/README.md)。

- [文档中心](docs/README.md)：SDD 流程与全部 PRD / ADR / Spec / Plan 索引
- [连接与使用说明](docs/service-connection.md)：地址、参数与限制
- [部署说明](deploy/README.md)：环境、配置、launchd、冒烟
- [模型说明](models/README.md)：权重来源、revision、校验值
- [源码说明](src/README.md)：模块职责与 MLX 源码记录
- [项目进度与交接](HANDOFF.md)：当前部署状态、验证范围与后续事项
- [协作约定](AGENTS.md)：SDD 流程与工程约束

关键决策：[BGE-M3 + MLX](docs/adr/0002-bge-m3-mlx.md) · [原生 Python](docs/adr/0003-native-python-runtime.md) · [原生稀疏头](docs/adr/0005-native-sparse-head.md) · [进程内缓存](docs/adr/0006-in-memory-result-cache.md)
