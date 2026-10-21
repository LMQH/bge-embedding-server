# ADR-0002：初版采用 BGE-M3 与 MLX

## 状态

已接受，2026-10-15。依据：用户明确确认 BGE-M3、568M 参数、1024 维、8192 tokens 长度设置，以及 MLX 推理框架和 Apple 原生加速；目标服务器为此前明确的 Mac mini M4 16GB。

## 上下文

项目通过 API 提供 BGE 文本嵌入推理服务，需要确定首版模型、硬件与推理框架，作为后续接口设计和实现验证的依据。

## 决策

| 项目 | 已确认选择 |
| --- | --- |
| 目标硬件 | Mac mini M4，16GB 统一内存 |
| 模型 | `BAAI/bge-m3`，约 568M 参数 |
| 稠密向量维度 | 1024 |
| 最大输入长度设置 | 8192 tokens，按模型 tokenizer 计数；不是字符数，也不要求每次输入填充到此长度 |
| 推理框架 | MLX，采用 Apple 原生加速 |

用户选择以 MLX 配合 Apple Silicon 作为初版推理底座。该决策不代表已确认具体 MLX 实现库、开发语言、权重转换方式、精度或部署方式，也不代表已验证性能。

## 替代方案

此前讨论过 BGE 中文 v1.5 的 small、base、large，以及 TEI Metal、SentenceTransformers / PyTorch MPS、FlagEmbedding / PyTorch 和 Ollama。用户已选择 BGE-M3 与 MLX，其他方案不作为初版选型；未通过实测宣称其效果或性能较差。

## 后果

- 后续实现与验收以本决策的模型、维度、长度设置、硬件和框架为约束。
- 8192-token 输入在目标设备上的真实推理、内存峰值及可用批量需验证；不承诺长文本并发和吞吐。
- 具体 MLX 实现需核对分词、pooling、归一化与参考模型输出的一致性。
- sparse 和 ColBERT 输出是否纳入 API 尚未确认，不因模型具备这些能力就自动纳入范围。
- 权重 revision、数值精度、超长输入拒绝或截断策略、API 契约、批处理、并发、macOS 版本及部署方式仍待明确。

## 关联

- [PRD-0001](../prd/0001-embedding-service.md)
- [SPEC-0001](../specs/0001-embedding-inference.md)
- [PLAN-0001](../plans/0001-project-foundation.md)
