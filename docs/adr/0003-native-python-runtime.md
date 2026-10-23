# ADR-0003：原生 Python 服务与独立 conda 环境

## 状态

已接受，2026-10-15。依据：需求问询 Q12 经 Docker 支持情况说明后，用户明确回复“可”，并要求使用虚拟环境；Q13 接受最小接口边界及由实施侧落实工程默认值，Q14 选择用户级 launchd。本文补充 [ADR-0002](0002-bge-m3-mlx.md)，不替代其硬件、模型、维度及长度决策。

其中“正确性与回退”的强制参考验证要求已由 [ADR-0004](0004-minimal-verification.md) 替代；其余运行与环境决策继续有效。

## 上下文

首版是在内网供知识库 / RAG 使用的轻量常驻嵌入 API。用户要求先实现正确可用的服务，性能优化后置。本机开发，Mac mini M4 16GB 验证与部署，开发与目标机应使用各自的项目虚拟环境。

## 决策

| 项目 | 已接受方案 |
| --- | --- |
| 运行方式 | 开发与部署均原生运行于 macOS / Apple Silicon，首版不使用 Docker |
| 语言与 API | Python 3.12、FastAPI、Uvicorn 单 worker；一个模型实例串行处理请求 |
| 项目环境 | 两机分别创建 `bge-embedding` conda 环境，原生 `osx-arm64`；禁止使用 base、系统 Python 或其他项目环境安装和测试 |
| conda 发行器 | 本机沿用 Miniconda，Mac mini 沿用 Miniforge，无需更换发行器 |
| 依赖来源 | conda 仅提供 Python / pip 等环境基础，项目环境显式使用 conda-forge；Python 包在该环境内通过 `python -m pip` 安装并锁定 |
| MLX 运行时 | 使用官方发行包，不编译 `src/vendor/mlx/`；该目录保留作源码参考 |
| 模型实现 | 采用 `mlx-embeddings==0.1.0`；从 `last_hidden_state[:, 0, :]` 获取 CLS，转换为 float32 后做 L2 归一化 |
| 初始权重 | `mlx-community/bge-m3-mlx-8bit`，固定 revision `7eca4a1c6ea1a0c5efc37598b369012f3985910f`，从本地目录加载；来源见 [models/README](../../models/README.md) |
| 正确性与回退 | 先验证分词、模型加载及参考输出。失败先定位原因；确因量化误差不达标时，使用同一 BGE-M3 的 FP16 MLX 权重验证，不静默放宽标准 |
| 常驻管理 | 用户级 launchd，用户登录后启动，进程异常退出后自动重启；机器重启后须先登录该用户 |

本机已核实 conda 为 `${LOCAL_CONDA_ROOT}/bin/conda`、版本 `26.1.1`、平台 `osx-arm64`，当前未创建 `bge-embedding`。Mac mini 使用 Miniforge 来自用户说明，实际安装路径、平台、版本和 macOS 需连接后核实，不能套用本机路径。

两机使用同一环境声明及经验证的依赖锁，各自重建环境，不复制环境目录，不在共享声明中写入本机绝对 `prefix`。conda-forge 仅针对本项目环境显式选择，不修改用户全局 channel。服务、安装和测试均绑定该环境的解释器；launchd 使用目标机核实后的绝对解释器路径，不依赖交互 shell 的自动激活。

`mlx-embeddings` 对应正式 tag 提交为 `32981fa4e8064ed664b52071789dd18271fe4206`。MLX `0.32.4` 是首轮兼容性验证候选；FastAPI、Uvicorn、Transformers 及间接依赖的完整精确版本在项目环境解析并验证后锁定，不把未执行的依赖安装描述为成功。兼容性修复可在既定技术栈内调整依赖版本并记录证据，无需重新询问业务决策。

## 替代方案

- **Docker 开发和部署**：Docker Desktop 普通 Linux 容器没有本项目所需的 macOS Metal 透传支持；Docker Model Runner 的 Mac 推理引擎运行在容器外，不等于本服务可直接容器化。拆分容器 API 与宿主机推理增加当前不需要的进程和通信，故首版采用原生方式。依据见 [Docker 核查](../references/0001-mlx-framework-and-model-formats.md#6-docker-开发与部署核查)。
- **统一安装 Miniconda 或 Miniforge**：两者都能管理 conda 环境，无需为统一发行器更换已有安装。复现依靠项目环境声明、包版本、平台和模型 revision，而不是复制某一台机器的环境路径。
- **源码编译 MLX 或直接依赖模型库 main**：首版无需修改 MLX 底层。使用发行包和已发布的模型库，加少量明确的 CLS 处理，可降低构建与版本漂移成本。
- **多 worker、动态合批、优先级调度**：当前没有对应的负载需求，先采用单实例、有界 FIFO 请求队列和批内逐条推理；API 批量输入不要求一次 GPU 批推理。

## 后果

- `mlx-embeddings==0.1.0` 默认 `text_embeds` 使用 mean pooling，`pooler_output` 还经过额外变换，均不直接作为 BGE-M3 dense 返回值；实现只采用上述显式 CLS 路径。
- 该模型库会引入 `mlx-vlm` 等依赖，且声明 GPLv3；包许可与上游说明应保留，不能套用 MLX 本体的 MIT 标记。首版不为裁剪依赖另建 fork。
- 8bit 是首个实施与验证选择，尚不代表通过数值或检索验收。若需 FP16，转换来源、命令、revision 与校验值必须记录；禁止在请求处理中自动切换精度。
- 8192-token 在 M4 16GB 上的真实运行仍是交付检查。遇到兼容或内存问题先修复既定实现；不能静默降低长度上限、改用 CPU 或更换推理框架来声称通过。
- 用户级服务只在相应登录会话存在时运行；目标机睡眠及登录状态需要在部署说明中写清，未经需要不修改系统电源设置。

## 关联与依据

- [PRD-0001](../prd/0001-embedding-service.md) · [SPEC-0001](../specs/0001-embedding-inference.md) · [HANDOFF](../../HANDOFF.md)
- [MLX 官方安装文档](https://ml-explore.github.io/mlx/build/html/install.html)
- [mlx-embeddings 固定版本源码](https://github.com/Blaizzy/mlx-embeddings/tree/32981fa4e8064ed664b52071789dd18271fe4206)
- [Miniforge 官方仓库](https://github.com/conda-forge/miniforge) · [conda 环境中使用 pip](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html#using-pip-in-an-environment)
