# 原生 macOS 运行与部署

执行依据：[SPEC-0001](../docs/specs/0001-embedding-inference.md)、[PLAN-0002](../docs/plans/0002-minimal-service.md)。仅支持原生 arm64 macOS；当前锁定 MLX wheel 要求 macOS 26 或以上。使用本机 Miniconda / 目标机 Miniforge 各自的 `bge-embedding` 环境，不复制环境目录。

## 建立环境

在项目根目录执行；`conda` 必须先核实属于本机已有安装。依赖锁生成后按下面方式安装，环境声明不包含开发机 prefix。

```sh
conda env create -f environment.yml
conda activate bge-embedding
python -c 'import platform,sys; print(sys.executable, platform.machine())'
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -m pytest -q
```

完整锁包含运行与基本冒烟依赖，默认测试只有 2 项 smoke；不需要官方参考权重或 Torch。模型获取与固定 revision 见 [models/README](../models/README.md)。不安装 `src/vendor/mlx`。

## 私有配置与本机启动

运行参数统一来自 [config.example.toml](../config.example.toml)，服务不再读取原来的四个 `BGE_*` 环境变量。首次在项目根目录执行：

```sh
python deploy/install.py --config "$PWD/config.toml"
```

配置不存在时，脚本基于示例生成随机 Key，将模型路径设为本机项目的 `models/bge-m3-mlx-8bit`；配置与 launchd plist 均为权限 600。此命令只生成文件，不启动服务。配置已存在时直接校验并保留其内容与 Key。若旧 plist 保存了 Key、监听地址、端口或模型路径，首次生成 TOML 时一并迁移，保留原服务参数。

编辑私有 `config.toml` 后启动：

```sh
python -m bge_embedding --config "$PWD/config.toml"
```

也可自行复制示例、设置权限 600，填写非空 `auth.api_key` 和正确的 `model.path`。根目录 `config.toml` 已被 Git 忽略；其他位置的私有配置也不得提交。Key 只在私有文件中查看，不粘贴到共享文档或命令行。

配置共 16 项：监听地址 / 端口、Key、模型路径、等待位 / 等待超时、四项请求上限、两项 MLX 内存策略、四项日志参数。示例保留既有基线：1 个执行位 + 19 个等待位、30 秒等待、1 MiB 请求体、16 条 / 批、8192 tokens / 条及 32768 tokens / 请求。执行位与 worker 固定为 1。

所有项必须填写；缺项、未知项、错误类型或范围、无效模型路径、单条上限超过模型支持长度时拒绝启动。相对路径以配置文件所在目录为基准，支持 `~`。启动读取一次，修改后须重启；无热加载或环境变量覆盖。MLX 工作内存与缓存参数仍是分配器策略，不是进程硬配额。

`server.host` 示例为 `127.0.0.1`、`server.port` 为 8000。目标机将 `server.host` 改为内网 / Tailscale 地址，例如 `<TAILSCALE_IP>`。`GET /healthz` 无需认证。`POST /v1/embeddings` 需要 `Authorization: Bearer <Key>`，请求示例：

```json
{"model":"bge-m3","input":["知识库文档","English query"],"encoding_format":"float"}
```

接口只接受上述三个字段，SDK 客户端显式传 `encoding_format="float"`。原始输入不落盘，超长拒绝。启动失败退出并记录安全类别；运行期间不下载模型。

## 用户级 launchd

登录目标机，使用该机项目环境的 Python，在项目根目录执行上述安装命令。编辑 `config.toml` 中的目标监听地址及其他参数，重新执行安装命令校验配置，再加载：

```sh
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.bge-embedding.plist"
curl --fail http://<TAILSCALE_IP>:8000/healthz
```

plist 只保存该机解释器和 `--config` 绝对路径等启动信息，Key 与运行参数统一来自 TOML。迁移旧服务时，先按下文 `bootout` 停止旧任务，再生成新 plist、编辑并校验配置，然后 bootstrap；保留原 `server.host`、端口及模型路径，以免意外改变服务地址。

正常停止及重新启动：

```sh
launchctl bootout gui/$(id -u)/local.bge-embedding
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.bge-embedding.plist"
```

`RunAtLoad` 在用户登录时启动；`KeepAlive.SuccessfulExit=false` 在异常退出后恢复。重启后必须登录该用户。手动停止用 `bootout`，不要用 kill 模拟正常停机。本轮不安排故障注入测试。

日志文件、大小、备份数和级别从 `[logging]` 加载；示例为项目内 `logs/service.log`、5 MiB、2 份备份、INFO。相对路径以配置文件所在目录为基准，两机 `config.toml` 均在项目根，日志即落在项目工作路径下。过程文件归口：`logs/` 只放常驻轮转日志；一次性诊断、测量与备份产物放 `.cache/`，两者均不入版本控制。launchd 的 stdout/stderr 指向 `/dev/null`；应用文件日志保留安全错误类别，无请求正文、Key、向量或底层异常文本。收到正常退出信号先拒绝新请求、释放等待任务，再等待当前 GPU 计算完成。

## 基本冒烟

服务启动后，在项目环境执行：

```sh
python tests/verify_http.py --config "$PWD/config.toml"
```

脚本读取同一 TOML 中的 Key、地址和端口；目标机可用 `--launchd` 替代 `--config`，从 plist 找到配置文件。可另加 `--url` 覆盖探测地址，适用于从另一台机器连接。只检查健康状态、缺 Key 被拒绝、单条 / 两条批量成功及向量基本形状与数值。

按照用户要求，不默认执行参考模型比较、完整测试套件、极限长度、压力测试或故障注入。已有扩展测试退出默认执行范围；仅在出现相关问题并明确需要时使用。实际结果与未验证项见 [Plan](../docs/plans/0002-minimal-service.md)。
