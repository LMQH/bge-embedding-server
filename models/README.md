# 本地模型

模型权重和下载缓存不纳入版本控制。本页记录下载来源；推理验证与生产版本选型状态见 [HANDOFF](../HANDOFF.md)。

## BGE-M3 MLX 8bit

- 获取日期：2026-10-15。
- 来源：[mlx-community/bge-m3-mlx-8bit](https://huggingface.co/mlx-community/bge-m3-mlx-8bit)，社区转换版。
- Revision：`7eca4a1c6ea1a0c5efc37598b369012f3985910f`。
- 本地目录：`models/bge-m3-mlx-8bit/`。
- 下载工具：本机已有的 Hugging Face CLI `1.14.0`，路径 `/opt/homebrew/bin/hf`。
- 配置：XLM-RoBERTa、1024 维；affine 8bit 量化，group size 64。
- 主权重：`model.safetensors`，603,620,090 字节（约 604 MB）。
- 上游主权重 SHA-256：`57b597e5aa8c102c2698cc0915760a839e4c1a30bff0a46d7883d27d3f010720`。

在项目根目录恢复或续传完整仓库：

```sh
hf download mlx-community/bge-m3-mlx-8bit \
  --revision 7eca4a1c6ea1a0c5efc37598b369012f3985910f \
  --local-dir models/bge-m3-mlx-8bit
```

应保留同一 revision 的配置、tokenizer 和权重索引。模型实现及 CLS pooling、归一化一致性要求见[参考资料](../docs/references/0001-mlx-framework-and-model-formats.md)。

## BGE-M3 稀疏头

当前 8bit 快照只包含 encoder / pooler，不含 sparse head。双路输出需要官方 BGE-M3 检查点单独提供的稀疏头：

- 来源：[BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) 的 `sparse_linear.pt`。
- Revision：`5617a9f61b028005a4858fdac845db406aefb181`。
- 原始文件：3,516 字节；SHA-256 `45c93804d2142b8f6d7ec6914ae23a1eee9c6a1d27d83d908a20d2afb3595ad9`。
- 内容：`weight`（1×1024）+ `bias`（1），fp16；不含主模型权重。

在项目根目录运行：

```sh
python deploy/fetch_sparse_head.py
```

脚本下载并校验官方文件，转换为 `models/bge-m3-mlx-8bit/sparse_linear.safetensors`（4,251 字节）。离线或已下载时可用 `--pt /path/to/sparse_linear.pt`。不要将该文件命名为 `model*.safetensors`，否则 `mlx_embeddings` 会把它当作主模型权重加载。权重不纳入版本控制。

## 当前使用范围

服务使用该 8bit 快照，未改动配置、tokenizer 或权重；不需要第二份参考模型，见 [ADR-0004](../docs/adr/0004-minimal-verification.md)。
