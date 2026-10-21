# PLAN-0007：稠密与稀疏双路输出实施

- 状态：进行中，2026-10-21；本机实现与验证完成；M4 部署方案已落盘，当前不执行。
- 关联：[PRD-0002](../prd/0002-dense-sparse-embeddings.md)、[ADR-0005](../adr/0005-native-sparse-head.md)、[SPEC-0002](../specs/0002-dense-sparse-output.md)。

## 目标与前置条件

在现有 BGE-M3 8bit MLX 服务上增加可选 sparse 输出：补入官方稀疏头，完成推理、API、测试、文档与 M4 验证。前置条件：PRD-0002 与 SPEC-0002 已确认；本地 conda 环境为 `bge-embedding`；M4 项目目录与 launchd 配置可访问。M4 的最终验证依赖可用的部署通道。

## 实施步骤

| 状态 | 步骤与关联 Spec 场景 | 涉及目录或文件 | 验证标准 |
| --- | --- | --- | --- |
| 完成 | 建立 ADR-0005、SPEC-0002 与本 Plan，更新文档索引 | `docs/adr/0005-native-sparse-head.md`、`docs/specs/0002-dense-sparse-output.md`、`docs/plans/0007-dense-sparse-output.md`、`docs/README.md` | 链接有效，PRD-0002 引用可追溯 |
| 完成（本机） | 获取并转换官方稀疏头，固定 revision 与校验和 | `deploy/fetch_sparse_head.py`、`models/bge-m3-mlx-8bit/sparse_linear.safetensors`、`models/README.md` | 转换脚本成功；文件形状 1×1024 + 1；SHA-256 记录 |
| 完成（本机） | 推理双输出：加载稀疏头、计算 ReLU、按 token 取 max、排除特殊 token | `src/bge_embedding/inference.py` | 本地真实模型中文/英文 sparse 非空；dense 不变 |
| 完成 | API 与调度：`return_sparse` 校验、响应 sparse、scheduler 透传 | `src/bge_embedding/api.py`、`app.py`、`scheduler.py` | AC-201～AC-204 单元测试通过 |
| 完成 | HTTP smoke 扩展：`--sparse` 与 `--long` | `tests/verify_http.py` | 本地真实服务通过；旧 dense-only 路径仍通过 |
| 部分完成 | 文档与连接说明更新 | `docs/service-connection.md`、`docs/specs/0001-embedding-inference.md`、`deploy/README.md`、`HANDOFF.md` | 字段、限制、示例与实现一致；M4 线上说明待部署后确认 |
| 完成（本机） | 本地真实模型验证：中文/英文、批量、8192 tokens、dense 回归 | `src/`、`tests/` | 记录命令、耗时、峰值内存与结果 |
| 暂不执行 | M4 部署与真实 HTTP 验证 | M4 项目目录、launchd、模型目录 | AC-202、AC-203、AC-205、AC-207 通过；失败可回滚 |

## 验证记录（本机）

环境：M5、32GB、macOS 26.5.1，`bge-embedding` 环境 Python 3.12.15 / arm64；本地模型目录已生成稀疏头。以下均为本机结果，不是 M4 结果。

- `python -m pytest -q`：3 项默认 smoke 通过（新增稀疏 opt-in 测试）。
- `python -m pytest -q -m 'not real'`：72 passed，2 deselected。
- `BGE_REAL_TESTS=1 BGE_CONFIG="$PWD/config.toml" python -m pytest -q -m real`：2 passed；覆盖真实模型 dense/sparse、特殊 token 排除、dense 路径一致性和 8192 tokenization。
- 直接推理 8192 tokens（`"test " * 8190`）：
  - dense-only：5.133 s，峰值 977.4 MiB；
  - dense+sparse：4.777 s，峰值 977.4 MiB；
  - dense 最大绝对差 0.0；重复英文样本只有 1 个唯一正权重 token（`"3034"`）。
- 中文短句 `人工智能正在改变知识库检索`：8 个 sparse 项，最高为 `81492=0.3436`、`24471=0.2400`、`30094=0.2389`；与改造前原型一致。
- 本机 HTTP：`tests/verify_http.py --url http://127.0.0.1:8011 --config /tmp/bge-test-config.toml --sparse --long` 通过，8192 tokens 返回 200，耗时 4.88 s；默认 dense-only smoke 也通过。
- 日志只记录状态、耗时、批大小和 token 数，无正文、权重或 Key。

## M4 部署方案（暂不执行）

本节只定义方案。用户已明确当前不执行、无需审批；以下内容用于后续评审和需要时执行。当前尝试连接返回 `Permission denied (publickey,password,keyboard-interactive)`，线上仍只返回 dense。

### 1. 范围与成功标准

- 只部署已在本机验证的双路输出改动；不升级依赖、不改 `config.toml`、不改队列与限额、不做检索质量评测。
- 成功标准：
  - M4 服务健康；不传 `return_sparse` 的响应与现状一致，且没有 `sparse` 字段。
  - 传 `return_sparse=true` 时返回 dense + sparse；key 为 token id 字符串，value 为有限正数。
  - 8192 tokens 请求返回 200；记录耗时与峰值内存；无 OOM、无 500。
  - 失败时能在约 5 分钟内恢复现有 dense-only 服务。
- 非目标：ColBERT、BM25/SPLADE、服务端融合、官方 fp16 全模型数值对照、soak、压力测试或故障注入。

### 2. 前置条件与授权

| 项目 | 要求 |
| --- | --- |
| SSH / 执行通道 | M4 可用 SSH（把本机公钥加入 M4 的 `~/.ssh/authorized_keys`）或用户明确选择自行执行；当前无可用凭据 |
| 维护窗口 | 用户确认可短暂中断服务；`launchctl bootout/bootstrap` 期间请求会失败，模型重新加载需要数秒 |
| 备份目录 | M4 项目下 `.cache/dual-output-<timestamp>/`，权限 700；备份源码、测试、部署文件、文档、plist；`config.toml` 只备份不打印 |
| 稀疏头 | 优先从本机 `scp` 已验证文件，不在 M4 重新下载；本机文件 4,251 bytes，SHA-256 `e4c8a5ad647917de2a26c40dfa3a3e00564e7040a351e117eeb672a7cd5a7a2b` |
| 依赖 | 不新增运行时依赖；使用 M4 现有 `bge-embedding` 环境与 `requirements.lock` |
| 回滚能力 | 旧代码会忽略 `sparse_linear.safetensors`（文件名不匹配 `model*.safetensors`）；恢复旧 `src/` 后重启即可 |

### 3. 变更集

只同步本次改动，避免覆盖 M4 私有配置、模型主体权重和缓存：

- 推理与 API：`src/bge_embedding/inference.py`、`api.py`、`app.py`、`scheduler.py`。
- 测试与冒烟：`tests/conftest.py`、`test_api.py`、`test_config.py`、`test_inference.py`、`measure_attention.py`、`verify_http.py`。
- 部署与模型说明：`deploy/fetch_sparse_head.py`、`deploy/README.md`、`models/README.md`。
- 文档：`docs/adr/0005-native-sparse-head.md`、`docs/specs/0002-dense-sparse-output.md`、`docs/plans/0007-dense-sparse-output.md`、`docs/specs/0001-embedding-inference.md`、`docs/prd/0002-dense-sparse-embeddings.md`、`docs/README.md`、`docs/service-connection.md`、`HANDOFF.md`。
- 模型资产：`models/bge-m3-mlx-8bit/sparse_linear.safetensors`（单独复制并校验，不通过批量同步覆盖其他权重）。
- 不改：`config.toml`、`pyproject.toml`、`requirements.lock`、模型主体权重、launchd plist（除非用户要求）。

### 4. 执行步骤（用户明确要求执行后）

| 阶段 | 操作 | 验证 | 失败处理 |
| --- | --- | --- | --- |
| 0 预检 | 记录 M4 当前 `/healthz` 与关键文件哈希；创建备份目录；用 `rsync -av --dry-run` 预演变更集 | 备份存在且权限 700；dry-run 只列出预期文件；服务仍健康 | 停止，不部署 |
| 1 同步 | `rsync` 同步第 3 节文件；`scp` 稀疏头；在 M4 校验头文件的 SHA-256 和大小 | 文件内容/哈希一致；`sparse_linear.safetensors` 为 4,251 bytes | 从备份恢复，不重启 |
| 2 启动前检查 | 在 M4 项目环境执行 `python -m pytest -q`；用 `mx.load` 检查头形状 | 3 项 smoke 通过；weight `(1,1024)`、bias `(1,)` | 恢复备份，不重启 |
| 3 重启 | `launchctl bootout gui/$(id -u)/local.bge-embedding`；`launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.bge-embedding.plist"`；轮询 health | `/healthz` 返回 ready；日志无启动异常 | 立即回滚并重启旧版 |
| 4 dense-only 冒烟 | 运行 `python tests/verify_http.py --launchd` | 健康、缺 Key 401、单条/批量、1024 维归一化；响应无 `sparse` | 回滚 |
| 5 双路与 8192 | 运行 `python tests/verify_http.py --launchd --sparse --long` | 200；8192 tokens；sparse 非空且键/值合法；记录耗时 | 回滚 |
| 6 资源记录 | 在 M4 直接推理 8192 tokens，分别测 dense-only 与 dense+sparse；记录 `mx.get_peak_memory()` 与耗时 | 与本机 977.4 MiB 基线对照；无 OOM、无明显回退 | 回滚 |
| 7 观察 | 观察 health 与日志 5～10 分钟；可做少量并发/批请求 | 无 5xx、无异常日志、服务稳定 | 回滚 |
| 8 收尾 | 更新 `docs/service-connection.md`、`HANDOFF.md`、本 Plan 的 M4 结果；必要时再次同步文档 | 文档与线上一致；证据含命令、耗时、峰值内存与未验证项 | 记录偏差，不掩盖失败 |

M4 上的关键命令：

```sh
# 0. 预检与备份（示例，用户要求执行后按实际时间戳执行）
launchctl print gui/$(id -u)/local.bge-embedding >/tmp/bge-before.txt
mkdir -p .cache/dual-output-YYYYMMDD-HHMMSS
cp -a src tests deploy docs HANDOFF.md config.toml \
  "$HOME/Library/LaunchAgents/local.bge-embedding.plist" \
  .cache/dual-output-YYYYMMDD-HHMMSS/
chmod 700 .cache/dual-output-YYYYMMDD-HHMMSS

# 1. 同步与校验（在本机执行，目标为 M4；具体主机名按可用访问方式）
# 先 dry-run；确认输出只包含预期文件后，去掉 --dry-run 执行。
rsync -avR --dry-run --exclude __pycache__ --exclude .pytest_cache --exclude .DS_Store \
  src/bge_embedding tests deploy docs models/README.md HANDOFF.md \
  ${REMOTE_USER}@<M4>:${REMOTE_PROJECT_DIR}/
rsync -avR --exclude __pycache__ --exclude .pytest_cache --exclude .DS_Store \
  src/bge_embedding tests deploy docs models/README.md HANDOFF.md \
  ${REMOTE_USER}@<M4>:${REMOTE_PROJECT_DIR}/
scp models/bge-m3-mlx-8bit/sparse_linear.safetensors \
  ${REMOTE_USER}@<M4>:${REMOTE_PROJECT_DIR}/models/bge-m3-mlx-8bit/

# 2. 启动前检查
python -m pytest -q
python - <<'PY'
import mlx.core as mx
head = mx.load("models/bge-m3-mlx-8bit/sparse_linear.safetensors")
print({key: value.shape for key, value in head.items()})
PY

# 3. 重启
launchctl bootout gui/$(id -u)/local.bge-embedding
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.bge-embedding.plist"
until curl -fsS http://127.0.0.1:8000/healthz; do sleep 1; done

# 4-5. 验证
python tests/verify_http.py --launchd
python tests/verify_http.py --launchd --sparse --long
```

说明：`rsync` 不带 `--delete`；不覆盖 `config.toml`。实际主机名、端口和路径以用户提供的访问方式为准；health 轮询地址按 `config.toml` 的 host/port 调整（示例假设 `0.0.0.0:8000`）。资源记录可复用本机同款一次性脚本：加载 `Embedder`，tokenize `"test " * 8190`，分别执行 `embed(..., return_sparse=False/True)`，记录耗时和 `mx.get_peak_memory()`；脚本不输出正文或权重。若服务仍在运行，独立测量进程会额外占用约 1GB，建议在维护窗口内执行。

### 5. 验证矩阵

| 场景 | 验证方式 | 通过条件 |
| --- | --- | --- |
| AC-201 dense-only 兼容 | `verify_http.py --launchd` | 200；无 `sparse`；dense 1024 有限归一化 |
| AC-202 单条 sparse | `verify_http.py --launchd --sparse` | 200；sparse 非空；key 为数字字符串；value > 0 |
| AC-203 批量 sparse | 同上，两条中英混合 | 每项独立 sparse；index 顺序正确 |
| AC-204 非法 `return_sparse` | 本机已测；M4 可选复测 | 400 `invalid_request`，不推理 |
| AC-205 8192 tokens | `verify_http.py --launchd --sparse --long` | 200；usage 8192；dense/sparse 有效；记录耗时 |
| AC-207 dense 回归 | 本机已完成（dense 最大绝对差 0.0）；M4 可选做部署前后余弦 | 本机通过；M4 如测则 ≥ 0.9999 |
| 资源 | 直接推理记录峰值内存 | 无 OOM；与本机 977.4 MiB 基线对照 |

### 6. 回滚方案

触发条件：health 超过 5 分钟未 ready、启动异常、sparse 缺失/非法、8192 返回 500 或 OOM、dense 明显回归。

```sh
launchctl bootout gui/$(id -u)/local.bge-embedding
# 从 .cache/dual-output-<timestamp>/ 恢复 src/、tests/、deploy/、docs/、HANDOFF.md 和 plist
# 不覆盖 config.toml；稀疏头可保留，旧代码不会加载它
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.bge-embedding.plist"
until curl -fsS http://127.0.0.1:8000/healthz; do sleep 1; done
python tests/verify_http.py --launchd
```

回滚后更新 HANDOFF 和 PLAN-0007，记录失败现象、日志类别与恢复结果，不删除备份。

### 7. 风险与待确认项

- 访问风险：当前 SSH 被拒绝；没有可用访问方式就不能执行，也不会把本机结果当作 M4 结果。
- 中断风险：单 worker 重启会中断在途请求；需在低使用时段执行。
- 离线风险：M4 服务运行时设置 HF 离线；稀疏头必须提前放到模型目录，优先 `scp` 而不是依赖下载。
- 内存风险：M4 16GB，8192 tokens 本机峰值为 977.4 MiB；稀疏头很小，但 M4 仍需实测确认。
- 质量风险：8bit encoder + 官方 fp16 头不保证与官方 fp16 全模型逐位一致；本轮不做参考质量对照。
- 消费端风险：sparse key 是 token id 字符串，调用方需支持稀疏索引；服务不提供融合或检索。
- 未确认项：维护窗口、SSH 访问方式、是否需要在部署前保存 M4 dense 基线。后续执行时一并确认。

### 8. 执行条件与当前状态

本方案当前不执行，用户已明确无需审批。只有用户后续明确要求执行时，才确认可用访问方式、维护窗口和回滚备份位置，并按本方案操作；在此之前，M4 保持现状。预计总耗时 15～25 分钟，其中服务实际中断约数秒到 1 分钟（模型重载），验证另计。

## 交付与遗留事项

本机代码、测试、文档和稀疏头转换脚本已完成；M4 部署与验证是唯一未完成步骤，当前明确不执行。残余风险：8bit encoder + 官方 fp16 头不保证与官方 fp16 全模型逐位一致，本轮不做参考质量对照；M4 8192 的稀疏路径资源表现待实测。
