# PLAN-0003：修复长输入注意力内存占用

- 状态：已完成，2026-10-15。
- 来源：用户报告 M4 长输入约 14GB / swap，要求分析并优化。
- 依据：[Spec](../specs/0001-embedding-inference.md)、[最小验证原则](../adr/0004-minimal-verification.md)。本次只针对实际问题验证，不恢复官方参考模型或完整测试套件。

## 实施与验证

1. 用现有权重和 2048-token 输入复现过量中间分配，记录原始向量；不在目标机重跑旧版 8192-token 请求。
2. 仅替换 BGE 自注意力执行路径为 MLX 强制融合 SDPA，保持权重、双向全局注意力、mask、CLS 与输出不变；短输入及已有 2048 样本比较修复前后向量。
3. 在 M4 顺序检查 512 / 2048 / 8192 tokens，记录 Metal 活跃 / 缓存 / 峰值、耗时及系统 swap 变化；根据实际结果限制缓存与工作预算。
4. 更新目标服务，做一次真实长输入及基本接口检查，记录结果与资源保护的实际边界。

## 证据

只在项目 conda 环境执行；未修改第三方包源码、权重或依赖，未下载参考模型。默认仍仅运行两项 smoke；本次增加一项实际问题的定向回归和手动诊断脚本。

### 原因与实施

- mlx-embeddings 0.1.0 的 XLM-R 先完整计算 QKᵀ，再加 float32 mask、softmax、乘 V。8192 × 8192 × 16 个 float32 数值仅一个张量就是 4 GiB；不能把这一实现的占用泛化为 MLX 的必然行为。
- `inference.py` 复用原有量化 Q/K/V 层，替换为强制融合 SDPA，使用 head_dim⁻⁰·⁵ 缩放、float32 Q/K/V 和原 additive mask；无 causal mask，不改变 CLS / L2 输出逻辑。与旧算子顺序存在浮点舍入差异，不承诺逐位相同。
- 单独换融合后，本机 2048-token 峰值从 1674.8 降到 1521.5 MiB；再在每层 attention 结果执行 `mx.eval`，降至 677.3 MiB。这说明跨层计算图的中间结果存活也影响峰值；不能把全部差异归为缓存或泄漏。
- M4 8192-token 峰值实测约 0.95 GiB 后，将工作指导值设为 2 GiB、缓存回收目标设为 256 MiB。强制融合失败直接走既有安全 500，不静默退回完整矩阵。请求长度、逐条执行和队列限制保留。

接口与内存策略依据：[MLX 融合 SDPA](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.fast.scaled_dot_product_attention.html)、[MLX 内存指导值](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_memory_limit.html)，并核对目标安装版本 0.32.4 的实际 docstring。

### 定向验证结果

1. 本机 M5：先运行旧实现的 `tests/test_attention_memory.py`，2048-token 峰值 1674.8 MiB，超过回归门槛 1280 MiB，真实失败。修复及内存策略设置后同一测试通过。该门槛用于捕获本次回退，不是服务资源硬限制。
2. 本机 M5：2 项默认 smoke 通过，35 项 deselected；没有运行完整套件。
3. M4 / 16GB：停常驻服务后，旧实现仅测两个短文本、512 和 2048；随后同权重测修复版，增加 8192。没有重新运行旧版 8192。

| tokens | 旧版耗时 / 秒 | 修复后耗时 / 秒 | 旧版 Metal 活跃分配峰值 / MiB | 修复后峰值 / MiB | 修复后请求结束活跃 / 缓存 MiB |
| --- | --- | --- | --- | --- | --- |
| 512 | 0.156 | 0.150 | 995.2 | 602.2 | 575.7 / 33.1 |
| 2048 | 1.023 | 0.648 | 1674.8 | 677.3 | 575.7 / 127.6 |
| 8192 | 未重跑 | 4.794 | 未重跑 | 977.4 | 575.7 / 273.6 |

每个长度仅单次测量，不是吞吐或延迟基准；长文本使用重复 `test ` 构造精确 token 长度，含特殊 token。另有两条中英 / 空白样本（11、8 tokens），共 4 个新旧向量对照，M4 最低余弦相似度 0.9999999994089134（检查阈值 0.9999）。所有输出 1024 维、有限、L2 范数误差小于 1e-5。8192 仅检查结果合法性，未做旧版数值对照。

Metal 峰值来自 `mx.get_peak_memory`，不是进程 RSS，也不包含所有 Python / 系统占用。修复后诊断进程累计 RSS 高水位约 1359.7 MiB（含模型加载过程），独立于上表统计。每个样本开始前清缓存、重置 Metal 峰值；请求后活跃约 575.7 MiB。缓存回收目标不会阻止最后释放的缓冲暂时超过 256 MiB，8192 请求结束读到 273.6 MiB。

修复后各样本系统 Swapouts 增量均为 0；8192 的 Swapins 增量为 32 页，其他样本为 0。系统原有 swap used 约 2500.62 MiB 前后不变。计数是系统级，不能归因于单一进程，也不能宣称完全没有换页。未复现或重新测量用户此前报告的约 14GB 占用。

4. 恢复 launchd 后，真实 HTTP 8192-token 请求返回 200，usage 为 8192、向量 1024 维、范数 1.0000000324，耗时 4.707 秒；随后基本 HTTP smoke（健康、鉴权、单条、两条批量）通过。服务已恢复 ready。

### 复现命令与证据位置

本机解释器：`${LOCAL_CONDA_ROOT}/envs/bge-embedding/bin/python`；M4 解释器：`${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python`。以下在项目根目录、已激活对应 bge-embedding 环境时运行：

```sh
BGE_MODEL_PATH="$PWD/models/bge-m3-mlx-8bit" python -m pytest -o addopts='' tests/test_attention_memory.py -q
python -m pytest -q
python tests/measure_attention.py --model models/bge-m3-mlx-8bit --output .cache/attention/final --lengths 512 2048 8192
python tests/verify_http.py --launchd
```

已有旧版记录时，可给测量命令添加 `--compare .cache/attention/old.npz`。不要为了重建基线将线上服务恢复为旧实现。

目标机原始证据在 `.cache/attention/{old,fused-eval,final}.{json,npz}` 及对应 `.log`；本机备份在 `.cache/attention/m4/`。本机逐步诊断证据在 `.cache/attention/`。这些是固定诊断样本的忽略文件，不含调用方文本或 Key。

### 边界

本次解决已确认的完整矩阵分配和中间结果存活问题，未引入进程硬内存隔离、压力测试或容量承诺。MLX 指导值允许超过阈值，不能替代操作系统硬配额。单次 8192 成功证明当前样本和环境下可用，不证明任意输入与其他程序争用内存时的稳定性。短输入逐层求值可能增加调度开销，本次优先控制长输入峰值，未做短请求优化。

2026-10-21 配置化后，以上历史命令的当前替代为 `BGE_CONFIG="$PWD/config.toml" python -m pytest -o addopts='' tests/test_attention_memory.py -q` 及 `python tests/measure_attention.py --config "$PWD/config.toml" --output .cache/attention/final --lengths 512 2048 8192`；HTTP 冒烟保持 `--launchd`，读取新 plist 指向的 TOML。需先准备有效私有配置，见 [部署说明](../../deploy/README.md)。
