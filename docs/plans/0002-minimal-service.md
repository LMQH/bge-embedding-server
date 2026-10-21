# PLAN-0002：实现轻量嵌入服务

- 状态：已完成（2026-10-15，按用户最终确认的基本冒烟范围交付）。
- 关联：[PRD](../prd/0001-embedding-service.md) · [Spec](../specs/0001-embedding-inference.md) · [原生运行决策](../adr/0003-native-python-runtime.md) · [简化验证决策](../adr/0004-minimal-verification.md)

## 当前范围与结果

使用项目已有的 BGE-M3 MLX 8bit 权重，交付原生 Python API 并部署到 M4。用户在实施期间明确要求一切从简，撤销实施侧加入的强制参考对照和复杂测试；仅按当前 Spec 做必要冒烟，历史结果不构成追加工作的理由。

| 状态 | 工作 | 结果 |
| --- | --- | --- |
| 完成 | 两机独立 conda 环境与依赖锁 | Python 3.12.15 / arm64；本机 Miniconda、目标 Miniforge，均为 bge-embedding；pip check 均通过 |
| 完成 | 真实 8bit 模型与最小 API | 本地加载、原始 CLS + float32 L2、1024 维、单条 / 批量、共享 Key、必要错误、健康检查 |
| 完成 | 串行执行与常驻配置 | 初版单 worker、1 个执行位 + 4 个等待位、30 秒排队超时；用户级 launchd 与轮转日志；后续等待位扩充见 [PLAN-0004](0004-queue-capacity.md) |
| 完成 | M4 部署与基本冒烟 | 由本机通过 Tailscale 调用目标服务，health / 401 / 单条 / 两条批量 / 1024 维有限归一化向量通过 |
| 完成 | 精简交付 | 默认 pytest 仅 2 项 smoke；删除官方参考验证脚本及额外参考权重，移除 Torch 及专用依赖；文档同步 |

## 实际环境与启动

- 本机：Apple M5、32GB、macOS 26.5.1；解释器 `${LOCAL_CONDA_ROOT}/envs/bge-embedding/bin/python`。
- 目标：Apple M4、16GB、macOS 26.5.1；解释器 `${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python`。
- 目标项目：`${REMOTE_PROJECT_DIR}`；用户名 `<REMOTE_USER>`，Tailscale `<TAILSCALE_IP>`，使用已有 SSH 认证，无需使用用户提供的密码。
- 依赖：[environment.yml](../../environment.yml)、[pyproject.toml](../../pyproject.toml)、[requirements.lock](../../requirements.lock)。75 个 pip 包固定版本和 wheel SHA-256；两机以相同 wheel 哈希安装，未复制环境。
- 核心版本：MLX 0.32.4、mlx-embeddings 0.1.0、mlx-vlm 0.4.0、Transformers 5.19.0、FastAPI 0.143.1、Uvicorn 0.54.0。MLX wheel 要求 macOS 26+ / arm64。
- 服务监听 `0.0.0.0:8000`，可用地址 `http://<TAILSCALE_IP>:8000`。`GET /healthz`，`POST /v1/embeddings`。
- launchd 配置 `${REMOTE_HOME}/Library/LaunchAgents/local.bge-embedding.plist`，权限 600；Key 随机生成并仅保存在目标机此私有文件，不打印、不写入仓库。
- 日志 `${REMOTE_HOME}/Library/Logs/bge-embedding/service.log`，5 MiB / 2 备份。启动方式见 [部署说明](../../deploy/README.md)。

## 当前验证证据

以下均使用对应项目环境：

| 命令 / 行为 | 实际结果 |
| --- | --- |
| 两机 `python -m pip install --no-index --find-links .cache/wheels --require-hashes -r requirements.lock`，再 `python -m pip install --no-deps --no-build-isolation -e .` | 成功；缓存 wheel 均核对官方 pip 解析结果哈希 |
| 两机 `python -m pip check` | No broken requirements found |
| 本机 `python -m pytest -q` | 2 passed，34 deselected；默认仅 smoke |
| 精简后环境加载现有 Embedder | 成功，无 Torch 依赖 |
| `launchctl bootstrap gui/501 .../local.bge-embedding.plist` | 成功；plist 语法检查通过，实际服务已就绪 |
| 本机 `python tests/verify_http.py --url http://<TAILSCALE_IP>:8000`，Key 经 SSH 读入内存 | PASS：health、鉴权、单条、小批量、1024 维有限归一化向量 |

## 明确保留的限制

- 精确 8192-token 请求已启动但未得到完成结果；用户要求精简测试后已通过卸载服务取消，并重新启动服务。该项**未通过验收、未完成验证**，不能因配置允许 8192 就宣称已实测可用。
- 不再进行并发压力、完整边界套件、复杂取消 / 超时测试或故障注入。已实现相关保护，后续实际问题再针对性处理。
- launchd 的登录启动与异常重启选项已配置；未做整机重启 / 注销登录或 SIGKILL 恢复测试。手工 bootout / bootstrap 已实际执行。
- 未做性能调优或容量承诺。根目录尚无 Git 元数据，未创建 commit / PR；未修改独立的上游 MLX 克隆。

## 早期扩展验证历史（已退出当前交付范围）

下列记录保留实施事实，不是当前执行清单。官方参考权重与专用验证脚本已删除，固定结果摘要保留；后续不要自动恢复这些测试。

## 执行记录（2026-10-15）

- 用户明确确认 Specs 已定并授权实施，计划转为进行中。已创建环境声明、包声明、模型适配、API / 有限队列、固定语料与验收脚本、launchd 安装脚本；此条为实施记录，验证结果另列。
- 本机环境创建成功：Miniconda `${LOCAL_CONDA_ROOT}/envs/bge-embedding/bin/python`，Python 3.12.15、arm64，使用 conda-forge 独立创建。
- 用户提供目标登录用户名并授权从 Tailscale 查询；发现 `<REMOTE_HOSTNAME>` / `<TAILSCALE_IP>`，通过已有 SSH 认证成功连接，无需使用用户密码。核实 M4、16 GiB、arm64、macOS 26.5.1、Miniforge `${REMOTE_CONDA_ROOT}`，创建独立同名 Python 3.12 环境成功。
- 目标工作目录 `${REMOTE_PROJECT_DIR}`，首次同步仅项目代码、文档与既有 8bit 模型，不复制环境、vendor 或凭据。
- 依赖解析首次发现未约束的 mlx-vlm 会引入新增音频依赖，安装前中止并将其固定到满足 mlx-embeddings 要求的 0.4.0；仍使用完整发行包，不修改第三方源码。参考官方 requirements：<https://github.com/Blaizzy/mlx-vlm/blob/v0.4.0/requirements.txt>。最终兼容性须以导入与模型实测确认。

- 原始 tokenizer JSON 直接编码的预检查发现末尾空白差异；实际 Transformers 5.19.0 的 XLMRobertaTokenizer 会重新配置预分词器。用真实 AutoTokenizer 加载后，全部 18 条样本的 IDs / mask / 特殊 token 一致，不修改快照。
- 长度样本初次生成把 `hello ` 误当成单 token，断言及时失败（实为两个 token）；修正为实测单 token 的 `test `，保留 128 / 512 / 2048 及 8192 / 8193 的实际编码断言，没有改变任何质量阈值。
- 本机 `python tests/verify_model.py reference`：18 条 CPU FP32 参考通过维度 / 有限性 / L2 与 6/6 检索，约 7.48 秒。`python tests/verify_model.py mlx`：18 条 8bit 全通过，最低 cosine=0.9992245337，6/6 检索，Metal 峰值约 1.76 GB；保持现有 8bit，无 FP16 转换。
- 本机项目环境 `python -m pytest -m 'not real' -q`：35 passed、1 deselected；`BGE_REAL_TESTS=1 BGE_MODEL_PATH=... python -m pytest -m real -q`：1 passed、35 deselected。第一次分阶段安装时完整收集因尚未安装 numpy 失败，依赖就绪后已重跑通过。
- 本机真实 Uvicorn socket 冒烟：单条 / 批量 / 并发 / 顺序 / usage / 归一化通过，单条与批量 cosine >=0.9999；测试进程正常停止，不留本机常驻实例。固定样本 usage=23。
