# 推理服务连接与使用说明

2026-10-21 已将配置化版本部署到 M4 并重启。双路输出已在本机实现并通过验证，但 M4 线上仍只返回 dense；当前不部署，以下限制与字段以线上为准，双路契约见 [SPEC-0002](specs/0002-dense-sparse-output.md)。配置和启动方式见 [部署说明](../deploy/README.md)。

| 项目 | 配置 |
|---|---|
| 访问地址 | `http://<TAILSCALE_IP>:8000` |
| API Base URL | `http://<TAILSCALE_IP>:8000/v1` |
| 嵌入接口 | `POST /v1/embeddings` |
| 健康检查 | `GET /healthz`，无需认证，正常返回 `{"status":"ready"}` |
| 请求类型 | `Content-Type: application/json` |
| 认证 | `Authorization: Bearer <共享 Key>` |
| API Key | 来自 M4 私有 `${REMOTE_PROJECT_DIR}/config.toml` 的 `auth.api_key`；此次迁移保留旧 Key，不在共享文档中填写 |
| 模型参数 | `model`：必填，固定为 `"bge-m3"` |
| 输入参数 | `input`：必填，单个字符串或字符串数组；不接受空字符串、纯空白或 token ID 数组 |
| 编码参数 | `encoding_format`：可选，默认 `"float"`，仅支持 `"float"` |
| 额外参数 | 不接受上述三个字段之外的参数 |
| 支持内容 | 纯文本，支持中文、英文等多语言；调用方负责文件解析和文本切分 |
| 单条长度上限 | **8192 tokens**，包含 tokenizer 添加的特殊 token；超限拒绝，不自动截断 |
| 批量条数上限 | **16 条／请求** |
| 批量总长度上限 | **32768 tokens／请求**，包含各条特殊 token |
| 请求体大小上限 | **1 MiB（1,048,576 字节）** |
| 输入校验 | 任一条输入无效或超限，整批失败 |
| 向量输出 | **1024 维 dense 浮点向量**，采用 CLS 池化与 L2 归一化 |
| 输出顺序 | 与输入顺序一致，通过 `data[i].index` 对应 |
| Token 用量 | `usage.prompt_tokens` 和 `usage.total_tokens`，均为整批输入 token 总数 |
| 推理并发 | 单 worker，最多 **1 个请求执行推理**；批内文本逐条处理 |
| 等待队列 | 最多 **19 个等待请求**，加上 1 个执行中请求，总计 **20 个位置**，FIFO |
| 排队超时 | **30 秒**，指等待时间，不是推理执行时限 |
| 过载响应 | 队列满或排队超时返回 **HTTP 429** |
| 常见错误 | **400** 输入无效或超限；**401** 认证失败；**413** 请求体过大；**429** 排队过载；**503** 模型未就绪；**500** 推理失败 |
| 数据与日志 | 不持久化输入正文和向量；日志不记录正文、向量或 API Key |
