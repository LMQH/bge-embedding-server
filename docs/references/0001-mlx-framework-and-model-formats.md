# MLX 框架、模型格式与官方资料

整理日期：2026-10-15。

本文汇总本次查阅的官方文档与讨论结论，作为参考资料，不新增或替代项目决策。模型选型以 [ADR-0002：BGE-M3 与 MLX](../adr/0002-bge-m3-mlx.md) 为准，原生 Python 运行方案见 [ADR-0003](../adr/0003-native-python-runtime.md)。本文保留设计阶段的技术资料；实际安装与运行结果见 [HANDOFF](../../HANDOFF.md)。验证范围以用户最新确认的 [ADR-0004](../adr/0004-minimal-verification.md) 为准，链接指向的在线文档可能继续更新。

## 1. MLX 的定位

MLX 是 Apple 官方开源的机器学习数组计算框架，针对 Apple Silicon 的统一内存架构优化，提供数组运算、神经网络层、自动求导与优化器，既可用于推理，也可用于训练。Python API 接近 NumPy，另有 Swift、C++ 和 C 接口；选择 MLX 不代表必须使用 Swift。

Apple 的开源项目页直接链接官方仓库、文档和示例，可用于确认资料来源：[Apple MLX 项目页](https://opensource.apple.com/projects/mlx/)。

与本项目有关的主要特性：

- **统一内存**：CPU 和 GPU 可以访问同一份底层数据，减少显式数据搬运；系统、模型权重和推理中间结果仍共同占用设备内存。见[统一内存说明](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html)。
- **执行设备**：官方仓库列出的执行设备为 CPU 和 GPU；不能把“Apple 原生加速”直接理解为使用 Neural Engine。见[官方仓库](https://github.com/ml-explore/mlx)。
- **惰性计算**：计算在需要结果时执行。性能测量需包含结果求值，避免只测到构图时间。见[惰性计算说明](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html)。
- **模型适配参考**：官方 BERT 示例包含权重转换、分词、前向推理和与 Hugging Face 输出对比的方法，但该示例本身不等于完整的 BGE-M3 实现。见[BERT 示例](https://github.com/ml-explore/mlx-examples/blob/main/bert/README.md)。

## 2. MLX 与模型文件格式

“MLX 仅支持 `.mlx` 格式模型”是不准确的。MLX 是框架；通常所说的“MLX 模型”是适配该框架的模型实现与权重，不要求使用 `.mlx` 后缀。MLX 生态中的权重常以 `.safetensors` 保存，并配合模型配置和 tokenizer 文件使用。

官方文档列出的数组序列化格式如下：

| 格式 | 后缀 | 用途 |
| --- | --- | --- |
| NumPy | `.npy` | 单个数组 |
| NumPy archive | `.npz` | 多个数组 |
| Safetensors | `.safetensors` | 多个张量，常用于模型权重 |
| GGUF | `.gguf` | 多个张量及相关元数据 |

来源：[保存与加载说明](https://ml-explore.github.io/mlx/build/html/usage/saving_and_loading.html)、[`mlx.core.load` API](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.load.html)。

**能读取文件，不等于能直接运行任意模型。** 推理还依赖模型架构实现、权重名称与布局映射、分词器、量化方式和输出处理。MLX 底层支持读取 GGUF，不表示任意上层 MLX 模型库都能直接加载任意 GGUF 模型；同样，任意 `.safetensors` 文件也不一定可以直接用于某个 MLX 模型实现。

## 3. Mac mini 能否运行 MLX 和 GGUF 模型

对于本项目的 Mac mini M4，安装相应推理软件后，可以运行受支持的 MLX 适配模型或 GGUF 模型。是否可用由软件兼容性、模型架构、量化方式和可用内存共同决定，不是硬件直接识别某种模型文件后缀。

| 常见运行路径 | 权重与条件 |
| --- | --- |
| MLX + 对应模型实现 | 使用该实现支持的权重与配置，常见权重后缀为 `.safetensors` |
| llama.cpp | 使用其支持的 GGUF 模型，可通过 Metal 等在 Apple Silicon 上加速 |

`llama.cpp` 官方明确列出 Apple Silicon 优化，包括 ARM NEON、Accelerate 和 Metal。见[官方仓库](https://github.com/ggml-org/llama.cpp)。此处仅说明运行路径，不改变本项目已选择 MLX 的决策。

## 4. BGE-M3 适配注意事项

项目已确定的硬件、模型、维度和输入长度设置见 [ADR-0002](../adr/0002-bge-m3-mlx.md)。Q12 已确认采用 Python 3.12、FastAPI / Uvicorn 单进程、MLX 官方发行包和 `mlx-embeddings`，在 macOS 原生环境运行，由用户级 launchd 管理部署进程，见 [ADR-0003](../adr/0003-native-python-runtime.md)。运行时依赖已锁定，真实服务基本调用已完成，详见 Plan。

已核查并固定的模型实现库基线为社区项目 `mlx-embeddings==0.1.0`，tag `v0.1.0` 对应 commit `32981fa4e8064ed664b52071789dd18271fe4206`。它支持 XLM-RoBERTa，但不是 Apple 官方库。只读检查确认 PyPI wheel 中的模型、加载和归一化源码与该提交一致，当时尚未安装；现已使用该版本运行，证据另见 Plan。来源：[PyPI 0.1.0](https://pypi.org/project/mlx-embeddings/0.1.0/)、[固定源码提交](https://github.com/Blaizzy/mlx-embeddings/tree/32981fa4e8064ed664b52071789dd18271fe4206)。

[BGE-M3 官方文档](https://bge-model.com/bge/bge_m3.html#dense-retrieval) 定义的稠密向量为归一化后的 CLS token 隐藏状态。本项目采用 `outputs.last_hidden_state[:, 0, :]`，转为 float32 后做 L2 归一化，并核对 tokenizer、右侧 padding 与 attention mask。该库 0.1.0 的 `text_embeds` 硬编码 mean pooling 与归一化；`pooler_output` 则经过额外 dense 与 tanh，都不能代替本项目的 dense 输出。不能仅凭输出为 1024 维就判定结果正确。见[固定版本模型源码](https://github.com/Blaizzy/mlx-embeddings/blob/32981fa4e8064ed664b52071789dd18271fe4206/mlx_embeddings/models/xlm_roberta.py#L350)、[归一化源码](https://github.com/Blaizzy/mlx-embeddings/blob/32981fa4e8064ed664b52071789dd18271fe4206/mlx_embeddings/models/base.py#L50)。

首个验证权重为已下载的社区 affine 8bit / group size 64 版本，revision `7eca4a1c6ea1a0c5efc37598b369012f3985910f`，来源与完整性记录见[本地模型说明](../../models/README.md)。0.1.0 的加载器会根据配置与 `.scales` 参数构建量化层并载入权重，已有源码依据，但下载和元数据检查不代表已通过运行或质量验收。若确认问题由量化引起，再验证 FP16 路径；不预先将候选精度写成已验收的生产精度。见[量化加载源码](https://github.com/Blaizzy/mlx-embeddings/blob/32981fa4e8064ed664b52071789dd18271fe4206/mlx_embeddings/utils.py#L242)。

当前验证已按用户要求收缩为基本服务冒烟，不将官方参考对照或极限长度实测作为门槛。固定版本 attention 显式构造 N×N 分数矩阵并转 float32 做 softmax，权重大小不能代表长输入峰值内存；本轮长输入检查取消，不能宣称已验证 8192-token 可用性。见 [attention 源码](https://github.com/Blaizzy/mlx-embeddings/blob/32981fa4e8064ed664b52071789dd18271fe4206/mlx_embeddings/models/xlm_roberta.py#L120)。

## 5. 官方文档导航

| 文档 | 内容 |
| --- | --- |
| [Apple MLX 项目页](https://opensource.apple.com/projects/mlx/) | 官方身份、定位与各语言资源入口 |
| [MLX 文档首页](https://ml-explore.github.io/mlx/build/html/index.html) | 使用指南与 API 索引 |
| [安装说明](https://ml-explore.github.io/mlx/build/html/install.html) | 安装条件、源码构建与环境排查 |
| [快速入门](https://ml-explore.github.io/mlx/build/html/usage/quick_start.html) | 数组、计算与基础使用 |
| [统一内存](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html) | CPU/GPU 数据共享机制 |
| [惰性计算](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html) | 计算图与求值时机 |
| [保存与加载](https://ml-explore.github.io/mlx/build/html/usage/saving_and_loading.html) | 支持的文件格式及读写方法 |
| [`mlx.core.load`](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.load.html) | 加载数组与元数据的 API |
| [MLX 源码](https://github.com/ml-explore/mlx) | 框架实现、版本与问题跟踪 |
| [MLX 示例集合](https://github.com/ml-explore/mlx-examples) | 文本、图像、音频等模型示例 |
| [BERT 示例](https://github.com/ml-explore/mlx-examples/blob/main/bert/README.md) | 编码器权重转换、推理与输出对比 |

本次查阅的安装文档给出的 Mac Python 安装条件为 Apple Silicon、原生 Python ≥ 3.10、macOS ≥ 14.0，基础命令为 `pip install mlx`。项目已选择 Python 3.12 和 MLX 官方发行包；实际安装的 MLX 0.32.4 wheel 要求 macOS 26+；两机均为 macOS 26.5.1，并使用项目对应的 conda 环境。

## 6. Docker 开发与部署核查

2026-10-15，针对需求问询 Q12 的 Docker 问题核查官方资料。用户随后接受原生开发与部署路径，见 [ADR-0003](../adr/0003-native-python-runtime.md)。以下保留该决策的技术依据：

- Docker Desktop 的普通 Linux 容器不提供本项目所需的 macOS Apple GPU / Metal 透传路径。官方将 `--gpus` 的 Desktop 容器透传支持限定为 Windows WSL 2 后端，不能将 Linux CUDA 容器的部署方式直接套用到 Mac mini。见 [Docker GPU 支持说明](https://docs.docker.com/desktop/features/gpu/)。
- MLX 当前支持 macOS Apple Silicon 原生安装，也提供 Linux CPU 和符合 NVIDIA 条件的 Linux CUDA 安装路径；Linux 可运行 MLX 不等于能从 Mac 上的 Linux 容器访问 Metal。见 [MLX 安装文档](https://ml-explore.github.io/mlx/build/html/install.html)。
- Docker Model Runner 在 macOS 上的推理引擎运行于容器外的 macOS 沙箱；它提供 GPU 推理不代表任意 Python / MLX 容器获得 Apple GPU 访问能力。见 [Model Runner 执行环境](https://docs.docker.com/ai/model-runner/#execution-environment)。

本项目据此确定开发和部署均使用 macOS 原生项目 conda 环境，固定依赖与模型 revision，并由用户级 launchd 管理部署进程；首版不引入 Docker，也不拆分容器 API 与宿主机推理进程。现已部署并完成基本调用，结果以 Plan 为准。

## 7. Miniconda 与 Miniforge 项目环境

设计阶段的只读核实记录（后续环境已建立，见 Plan）：开发机 conda 位于 `${LOCAL_CONDA_ROOT}/bin/conda`，根目录为 `${LOCAL_CONDA_ROOT}`，版本 `26.1.1`，平台 `osx-arm64`，环境登记中尚无 `bge-embedding`。目标 Mac mini 使用 Miniforge 是用户提供的信息；其安装路径、版本与平台尚未通过远程访问核实。本次没有创建环境或安装依赖。

两机保留各自发行器，分别重建原生 `osx-arm64` 的 `bge-embedding` 项目环境，统一 Python 3.12、项目指定的 conda channel 和经验证的 pip 依赖锁。Miniconda 与 Miniforge 都提供 conda 环境管理；后者明确提供 macOS arm64 发行版，无需为统一项目依赖更换发行器。来源：[Miniconda 官方说明](https://www.anaconda.com/docs/getting-started/concepts/anaconda-or-miniconda)、[Miniforge 官方仓库](https://github.com/conda-forge/miniforge)。

共享环境声明不保留开发机绝对 `prefix`，不直接复制环境目录。先建立独立的 Python / pip 环境，再安装项目锁定的 pip 依赖；依赖调整后按声明重建并验证。pip 锁定应覆盖间接依赖，二进制包仍须满足目标 macOS 与 ARM64 条件，同一依赖锁不能替代目标机验收。来源：[conda 与 pip 环境管理](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html#using-pip-in-an-environment)、[pip 可复现安装](https://pip.pypa.io/en/stable/topics/repeatable-installs/)。
