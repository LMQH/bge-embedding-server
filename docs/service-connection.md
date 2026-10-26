# 连接与使用

v1.1.0 线上契约。`<TAILSCALE_IP>`、`${REMOTE_PROJECT_DIR}` 为占位符；实际地址与 Key 由部署方私下提供，需要本地记录时写入被忽略的 `docs/service-connection.local.md`。

| 项目 | 值 |
| --- | --- |
| 地址 / Base URL | `http://<TAILSCALE_IP>:8000` / `.../v1` |
| 接口 | `POST /v1/embeddings`；`GET /healthz` 免鉴权 |
| 认证 | `Authorization: Bearer <共享 Key>`，Key 在 `${REMOTE_PROJECT_DIR}/config.toml` 的 `auth.api_key` |
| 请求字段 | `model="bge-m3"`（必填）、`input`（必填）、`encoding_format="float"`、`return_sparse`（可选）；不接受其他字段 |
| 输入 | 纯文本，多语言；调用方负责解析与切分 |
| 上限 | 单条 8192 tokens，16 条 / 32768 tokens / 1 MiB 每请求，含特殊 token；超限整批拒绝 |
| 输出 | 1024 维 L2 归一 dense；`return_sparse=true` 时附 `[[token_id, weight], ...]`，可直接写入 Milvus `SPARSE_FLOAT_VECTOR` |
| 并发 | 单 worker，1 执行位 + 19 等待位，FIFO；批内合批 + 15 ms 窗口跨请求微合批 |
| 过载 | 队列满或等待超 30 s 返回 429（仅约束等待时间） |
| 错误 | 400 输入无效、401 鉴权失败、413 请求体过大、429 过载、503 未就绪、500 推理失败 |
| 数据 | 不持久化输入与向量；日志只含安全元数据 |

字段语义与失败行为见 [SPEC-0001](specs/0001-embedding-inference.md)、[SPEC-0002](specs/0002-dense-sparse-output.md)；配置与启动见[部署说明](../deploy/README.md)。
