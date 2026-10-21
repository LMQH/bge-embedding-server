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

## 当前使用范围

服务使用上面的现有 8bit 快照，未改动其配置、tokenizer 或权重。官方参考对照已按用户要求退出首版范围，额外下载的参考权重已移除；默认安装和部署不需要下载另一份模型，详见 [ADR-0004](../docs/adr/0004-minimal-verification.md)。早期对照的已执行摘要仅保留在 [PLAN-0002](../docs/plans/0002-minimal-service.md)。
