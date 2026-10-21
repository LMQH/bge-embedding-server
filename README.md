# BGE-Embedding

基于 BGE-M3 与 MLX 的文本嵌入推理 API 服务，面向 Mac mini M4（16GB 统一内存）。选型依据见 [ADR-0002](docs/adr/0002-bge-m3-mlx.md)。

采用 SDD（Specification-Driven Development，规格驱动开发）：先确认可验证的 Spec，再据此规划、实现与验收。开发理念与流程见 [文档中心](docs/README.md)。

## 目录

- `src/`：推理服务、API 与上游源码。
- `models/`：模型配置与获取说明，权重不纳入版本控制。
- `deploy/`：部署配置与运行说明。
- `tests/`：测试代码与必要数据。
- `docs/`：需求、决策、契约、实施计划与参考资料。

## 导航

- [文档中心](docs/README.md)
- [项目进度与交接](HANDOFF.md)
- [开发协作约定](AGENTS.md)
- [源码说明](src/README.md)
- [模型来源与下载](models/README.md)
- [运行与部署](deploy/README.md)
