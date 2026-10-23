# SPEC-0001：嵌入推理契约

- 状态：已确认，2026-10-15（实施基线；2026-10-15 按用户要求收缩验证范围；2026-10-21 用户明确将等待位扩充到 19，总计 20 个位置）。
- 确认依据：Q1～Q14 及最终原生环境确认；用户在 Q13 接受最小规则并授权落实字段默认值、错误码与基本容量限制。下列具体默认值和数值门槛由实施侧制定，不冒充用户逐项指定或实测结果。
- 需求：[PRD-0001](../prd/0001-embedding-service.md)，REQ-001～REQ-012。
- 决策：[ADR-0002](../adr/0002-bge-m3-mlx.md)、[ADR-0003](../adr/0003-native-python-runtime.md)、[ADR-0007](../adr/0007-batch-inference.md)。实施：[PLAN-0002](../plans/0002-minimal-service.md)。
- 2026-10-21 范围变更：dense + sparse 双路输出由 [PRD-0002](../prd/0002-dense-sparse-embeddings.md) 纳入范围，扩展契约见 [SPEC-0002](0002-dense-sparse-output.md)；本契约继续描述 dense 基础行为，双路字段与 sparse 语义以 SPEC-0002 为准。
- 2026-10-22 范围变更：嵌入结果缓存由 [PRD-0003](../prd/0003-result-cache.md) 纳入范围（已确认），附加行为契约见 [SPEC-0003](0003-result-cache.md)；配置项由 16 项增至 18 项。本契约继续有效；FIFO 与队列语义针对进入推理任务的请求，全命中请求绕过队列、`queue_full` / `queue_timeout` 仅适用于含未命中条目的请求，以 SPEC-0003 为准。
- 2026-10-23 范围变更：请求完成日志追加 `wait_ms` / `exec_ms` / `ahead` / `dedup`，429 增加 `Retry-After: 1`；详见 [SPEC-0004](0004-request-observability-and-dedup.md)。本契约的日志字段与过载响应头以 SPEC-0004 补充为准，其余行为不变。
- 2026-10-23 范围变更：按用户指定“单 worker + 真合批”，同一请求内的未命中条目由逐条前向改为按长度分桶的右 padding 合批；外部 API、输出顺序、`usage`、错误码、缓存与 FIFO 不变，执行位仍为 1，不做跨请求合批。实施见 [PLAN-0011](../plans/0011-batch-inference.md)。

## 目标与运行前提

在内网提供同步文本嵌入，支持中英文及混合文本。首版仅有一个 BGE-M3 模型实例，使用 MLX Apple GPU，返回 1024 维 dense 向量。文件解析、切分、向量存储和检索由调用方负责。

开发与部署使用原生 arm64 macOS 和 Python 3.12，各自在 bge-embedding conda 环境运行。本机保留 Miniconda，目标机保留 Miniforge；部署系统须符合实际锁定包的 macOS 要求，先核实再安装。启动命令、环境绝对路径和完整依赖锁由实施阶段按实际结果记录。

## 模型行为

- 初始使用 [模型来源](../../models/README.md) 中固定的 8bit 快照，仅从本地路径加载；请求期间不下载、不转换或切换模型。
- 模型与 tokenizer 使用同一快照。对有效输入保留原始字符串，不自动 trim、补 query instruction、切分或截断；必要的 tokenizer 标准处理照常执行。
- token 数按模型 tokenizer 加入特殊 token 后、padding 前计数。单条最多 8192 tokens，按实际编码检查；禁止 tokenizer 静默截断。
- 使用正确 attention mask；如使用 padding，固定为右 padding。取原始 last_hidden_state 的第 0 个 token（CLS），转换 float32 后 L2 归一化，不使用 mean pooling 或 pooler_output。
- 每条输出恰好 1024 个有限数值；归一化结果以 JSON 数字数组返回。非有限数值或异常输出视为推理故障。
- 同一执行任务内的未命中条目按长度接近程度分桶；桶内右 padding 后一次前向。每个合批组 padding 后的 token 总数不超过 8192，同组最长与最短长度不超过 1.25 倍；超出预算的条目单独执行。分组只影响执行方式，不改变输出顺序、`usage`、错误语义或缓存键。
- 长输入修复采用 MLX `scaled_dot_product_attention(force_fused=True)`，保持双向全局注意力和 additive mask；融合内核不可用时按推理失败处理，不退回完整注意力矩阵。每层注意力结果立即求值，控制跨层中间张量的存活。
- attention 的 Q/K/V 与 additive mask 使用 FP16，以利用 M4 GPU 的 FP16 吞吐；CLS、L2 归一化和 sparse 头仍在 FP32 计算或输出。FP16 引起的数值差异受合批容差约束。

## 批内合批（2026-10-23 增补）

- 仅在同一请求的未命中条目内合批；不跨请求、不改变单 worker / 单模型实例 / FIFO 队列。全命中请求、去重逻辑和缓存行为沿用 SPEC-0003、SPEC-0004。
- 分组按 token 长度排序后贪心装入，受 8192 padding 后 token 预算、16 条上限和 1.25 倍长度比约束；分组结果不对外暴露，也不保证稳定。
- padding 使用 tokenizer 的 pad token，固定右 padding；attention mask 必须屏蔽 padding。`usage` 只统计原始 token，不统计 padding。
- 合批结果必须满足既有 dense / sparse 契约。与逐条执行相比，dense 向量余弦相似度 ≥0.999999；sparse 的键集合一致，权重相对误差 ≤2e-3（绝对误差 ≤5e-4）。FP16 attention 的舍入会带来这一量级差异；dense-only 路径仍使用 FP16，sparse 路径不单独退回 FP32。
- 合批异常与单条异常一样使整个请求返回 500 `inference_failed`，不返回部分结果；不得因合批改变 400、401、413、429、503 的触发条件。

## API 与兼容子集

`POST /v1/embeddings`，首版使用内网 HTTP，请求与响应均为 JSON。鉴权头为 `Authorization: Bearer <共享 Key>`，Key 缺失、空值或不匹配返回 401。服务启动时 Key 必须已配置，不能以空 Key 运行。

| 请求字段 | 规则 |
| --- | --- |
| model | 必填字符串，首版只接受 bge-m3 |
| input | 必填，单个字符串或非空字符串数组；不接受 token-ID 数组、嵌套数组、null 或类型自动转换 |
| encoding_format | 可省略，默认 float；只接受字符串 float |

不接受其他字段，包括 dimensions、user；不支持 base64 输出。使用 OpenAI SDK 风格客户端时应显式设置 encoding_format="float"，不能宣称所有 SDK 默认参数和可选功能均兼容。首版不实现模型列表接口。

请求示例：

```json
{"model":"bge-m3","input":["知识库文档","An English query"],"encoding_format":"float"}
```

成功响应 HTTP 200，顶层包含 object="list"、model="bge-m3"、data 和 usage。data 按输入顺序排列，每项包含 object="embedding"、从 0 开始的 index 和 1024 项 embedding 数组。单条字符串同样返回含一项的 data。usage.prompt_tokens 为全部输入 token 数之和，usage.total_tokens 与之相等，均包含特殊 token，不包含 padding。

输入中空字符串、仅空白字符、空数组、非法类型或超长文本均拒绝；非空文本在空白检查后仍使用原文。先验证整个请求，任一输入无效时整批失败，不开始模型推理，不返回部分结果。批内推理故障时整批返回错误，已计算结果不作为部分成功交付。

## 基本容量与执行顺序

以下为首版有界保护值，非性能指标；当前不做容量规划或吞吐优化。

| 项目 | 配置示例基线与含义 |
| --- | --- |
| 请求体 | 最多 1 MiB 原始 JSON 字节，读取时限制，不能只信任 Content-Length |
| 批量条数 | 最多 16 条 |
| 单条长度 | 最多 8192 tokens，包含特殊 token |
| 单请求总长度 | 最多 32768 tokens，使用同一计数规则 |
| 执行中请求 | 最多 1 个，单 worker、单模型实例 |
| 等待队列 | 最多 19 个请求，另有 1 个可执行中的请求，总计 20 个位置 |
| 排队等待 | 最多 30 秒，仅从入队到开始执行；不限制已开始推理的执行时间 |

完成鉴权和校验的请求按成功入队顺序 FIFO 处理；整批完成再取下一个。队列满或排队超时返回 429；超时或客户端断开时移除 / 跳过尚未执行的任务，不能继续占用等待容量。已开始的 GPU 计算不强行中断，客户端断开后完成计算、丢弃响应，再释放执行位置；不能因此提前启动第二个推理任务。

推理期间健康检查仍可响应。停止服务时停止接收新任务，尚未执行的等待请求返回 503，当前计算完成后释放模型并退出；首版不设置可能截断长输入推理的硬执行超时。

依据 [PLAN-0003](../plans/0003-fused-attention.md) 的 M4 实测，MLX 工作内存指导值设为 2 GiB，缓存回收目标设为 256 MiB。这些是分配器策略，不是进程 RSS / 系统内存硬配额；释放回缓存后的瞬时值可能超过目标，后续分配时回收。资源保护依靠已验证的融合路径、逐层求值、长度上限和串行推理共同提供，不承诺任意系统负载下的硬隔离。

## 失败响应

嵌入接口的失败统一返回 error 对象，包含 message、type、param、code；message 为固定安全描述，不拼入用户文本、Key、模型本地路径或底层异常原文。param 对条目错误使用 input[0] 等下标，无法定位字段时为 null；healthz 使用下节定义的最小状态响应。

| HTTP | code | 场景 |
| --- | --- | --- |
| 400 | invalid_request | JSON / 字段 / 类型 / 空输入错误、未知字段、模型名或编码格式不支持 |
| 400 | input_too_long | 单条超过 8192 tokens，param 指向该条目 |
| 400 | batch_limit_exceeded | 条数或总 token 数超限 |
| 401 | invalid_api_key | Key 缺失、空值或错误 |
| 413 | request_too_large | 请求体超过 1 MiB |
| 429 | queue_full / queue_timeout | 等待队列已满或超过配置的等待超时（示例 30 秒） |
| 503 | model_unavailable | 服务尚未就绪或正在关闭 |
| 500 | inference_failed | 模型异常、资源不足或输出不符合数值契约 |

400 的 type 为 invalid_request_error，401 为 authentication_error，429 为 rate_limit_error，其余为 server_error（413 使用 invalid_request_error）。框架默认输入校验错误应映射为本契约的 400，不暴露默认的完整输入回显。只检查错误类别和安全描述，不把全部异常都吞成 400。

错误示例：

```json
{"error":{"message":"Input exceeds the token limit.","type":"invalid_request_error","param":"input[0]","code":"input_too_long"}}
```

## 启动、配置与日志

- 2026-10-21 用户确认将运行参数集中到 TOML，实施见 [PLAN-0005](../plans/0005-file-configuration.md)。服务通过 `python -m bge_embedding --config <文件>` 启动，不再读取 `BGE_MODEL_PATH` / `BGE_API_KEY` / `BGE_HOST` / `BGE_PORT` 作为服务配置。配置完整示例见 [config.example.toml](../../config.example.toml)，其中 Key 留空，实际文件不入库，权限设为 600。
- 配置包括监听地址与端口、Key、模型路径、等待位与等待超时、请求体 / 批量条数 / 单条及单请求总 token 上限、MLX 工作内存指导值与缓存回收目标、日志文件 / 轮转大小 / 备份数 / 级别，共 16 项。上文容量及内存数值为示例基线，实际采用配置值；执行位和 worker 固定为 1，总位置数为 `1 + queue.max_waiting`。
- 启动时一次性加载和校验；缺项、未知项、错误类型、非正数、非法端口、空 Key / 路径、非法日志级别或不可用模型文件均拒绝启动。单条 token 上限不得超过 BGE-M3 tokenizer 与 XLM-R 位置编码共同支持的长度。路径支持 `~`，相对路径以配置文件所在目录为基准。修改后重启生效，不提供热加载或环境变量覆盖，错误不回显配置值。
- 模型加载和必要配置校验完成后才提供就绪服务；缺 Key、文件缺失或加载失败应明确报错并退出，不在请求内反复重试下载。
- `GET /healthz` 无需 Key，只返回最小 status：模型已加载且服务未关闭时为 200 / ready，否则为 503 / not_ready。该规则适用于 HTTP 已监听期间；启动初始化未完成或已退出时可尚无监听。队列满不改变就绪状态，不暴露路径、Key 或模型文件元数据。
- 用户级 launchd 登录后启动、进程异常退出后恢复；plist 使用目标机项目环境 Python 的绝对路径，不依赖 shell 激活。正常手工停止按部署说明卸载任务，不能被误当崩溃循环重启。
- 服务不持久化用户文本和返回向量。日志仅保留启动 / 关闭状态、接口路径、状态码、耗时、批量大小 / token 数及安全错误类别；不记录请求体、向量、Authorization 或可能含输入的校验 / 异常原文。
- 部署日志使用 Python 日志轮转，默认单文件最多 5 MiB、保留 2 份备份；启动说明给出各机日志位置，不在代码中硬编码开发机路径。不引入独立监控系统或管理后台。

## 首版基本验证（2026-10-15 收缩）

用户在实施期间明确要求不扩大测试验收范围、一切从简。依据 [ADR-0004](../adr/0004-minimal-verification.md)，本轮只做必要的真实服务冒烟：

| 场景 ID | 验证内容 |
| --- | --- |
| AC-001 | 现有 8bit 模型能够加载，真实文本返回 1024 维有限向量 |
| AC-002 | 健康检查就绪；正确 Key 的单条和小批量返回成功，顺序与 usage 合理；无 Key 被拒绝 |
| AC-003 | 在目标 M4 的独立 conda 环境启动服务；提供用户级 launchd 启停方式 |
| AC-006 | 确认两机项目解释器与依赖，启动命令不依赖 base 或开发机路径 |
| AC-007 | 同一请求含 16 条 25–2048 tokens 的混合输入；合批与逐条结果对照；顺序、index、`usage` 与 sparse 契约不变 | dense 余弦 ≥0.999999；sparse 键集合一致；无部分结果 |
| AC-008 | 合批分组受 8192 padding token 预算、16 条上限和 1.25 倍长度比约束；4×8192 与 16×1024 均按预算拆组 | 分组不超预算；单条路径保留；Metal 峰值不超过 1.0 GiB（本机） |
| AC-009 | 16×25、16×256、16×512、16×1024、16×2048 与 4×8192 基准；1k/2k 与逐条对照 | 1k/2k 墙钟不劣化超过 5%；短/中批有可测收益；无 5xx |

此前由实施侧加入的官方参考模型对照、余弦阈值、完整边界套件、复杂队列 / 取消测试、故障注入和日志哨兵验收不再是首版必做项；AC-004、AC-005 原复杂验收场景撤销。已执行结果可留在 Plan 作为历史事实，不据此追加工作。后续只有实际问题或用户明确需求才增加对应测试。

上文接口和运行行为仍是实现契约；取消复杂验收不表示已证明所有边界场景。8192-token 上限保留，本轮不要求极限长度实测；未实际完成的检查须明确说明。参考模型和专用测试依赖不作为默认开发 / 部署前置条件。

2026-10-15 后续：针对用户实际报告的长输入内存问题，已按 PLAN-0003 完成定向 8192-token 推理及 HTTP 检查。该结果不扩大默认验收范围，也不等同于压力或容量测试。
