# PLAN-0013：sparse 输出改为 Milvus 可直插形态

- 状态：已完成（本机），M4 同步与真机复验待执行
- 关联 PRD / ADR / Spec：[PRD-0002](../prd/0002-dense-sparse-embeddings.md) REQ-013、REQ-016；[ADR-0005](../adr/0005-native-sparse-head.md)（决策不变）；[SPEC-0002](../specs/0002-dense-sparse-output.md) AC-202、AC-203、AC-210；[SPEC-0003](../specs/0003-result-cache.md) AC-305

## 目标与前置条件

把 `return_sparse=true` 的稀疏输出从“十进制字符串键对象”改为 `[[token_id, weight], ...]`，使调用方可原样作为 Milvus `SPARSE_FLOAT_VECTOR` 字段值插入。用户于 2026-10-26 指示按 Milvus 适配改造并授权硬切；聚合（同 token 取最大）、过滤（特殊 token、非正权重）与顺序（首次出现）语义不变。

前置事实：pymilvus 的稀疏入参为 `dict[int,float]`、二元组/二元数组列表或 CSR，索引为整数且 `0 ≤ id ≤ 2^32-2`，SDK 内部排序；JSON 对象键只能是字符串。本机原缺 `sparse_linear.safetensors`，实施后用 `deploy/fetch_sparse_head.py` 补齐。

## 实施步骤

| 状态 | 步骤与关联 Spec 场景 | 涉及目录或文件 | 验证标准 |
| --- | --- | --- | --- |
| 完成 | 稀疏输出改为整数 id + 权重二元数组（AC-202） | `src/bge_embedding/inference.py` | 单元测试校验 id 唯一、uint32 范围、float32 值、max 聚合 |
| 完成 | 缓存存储与容量估算跟随新形态（AC-305） | `src/bge_embedding/cache.py` | 缓存命中回放与推理输出条目一致 |
| 完成 | 测试与 HTTP 冒烟断言更新 | `tests/test_api.py`、`test_cache.py`、`test_inference.py`、`test_sparse.py`、`verify_http.py` | `pytest -m "not real"` 全绿 |
| 完成 | 契约与文档同步（AC-209） | SPEC-0002/0003、PRD-0002、REF-0003/0004、README、`docs/service-connection.md`、`deploy/README.md`、HANDOFF | 无残留旧形态描述 |
| 完成 | 补齐官方稀疏头 | `models/bge-m3-mlx-8bit/sparse_linear.safetensors` | 脚本校验 SHA-256 后生成 4251 字节文件 |
| 完成 | pymilvus 形状校验（AC-210） | 临时 venv，pymilvus 3.0.2 | `sparse_rows_to_proto` 通过并回读一致 |
| 待办 | M4 代码仓同步、权重同步与真机复验（AC-202、AC-205） | 目标机 | 需先授权 SSH 访问；见遗留事项 |

## 验证记录

环境：本机 Miniconda `bge-embedding`（Python 3.12.15），Apple arm64，2026-10-26。

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 单元与冒烟 | `python -m pytest -q -m "not real"` | 109 passed，3 deselected |
| 真实推理 | `BGE_REAL_TESTS=1 BGE_CONFIG=<临时 TOML> pytest tests/test_inference.py -m real -q` | 2 passed（含 batch/single 稀疏一致性） |
| 真实 HTTP | `python tests/verify_http.py --config <临时 TOML> --url http://127.0.0.1:18080 --sparse --long` | PASS：health、鉴权、单条、双条、dense 1024 归一化、sparse、8192 tokens（1.12 s） |
| 真实输出样例 | `POST /v1/embeddings` 中文 + 英文 | sparse 分别为 3 与 8 项，形如 `[[21001, 0.1883], [30094, 0.2461], ...]` |
| pymilvus 校验 | `sparse_rows_to_proto([...真实响应...])`（pymilvus 3.0.2） | accepted=True；2 行，24 / 64 字节；`sparse_proto_to_rows` 回读值与 float32 响应逐位一致 |

说明：临时 TOML 指向仓库内模型目录，日志写入 `/tmp`，未改动私有配置；冒烟服务绑定 `127.0.0.1:18080`，结束后已停止。pymilvus 仅装在 `/tmp` 临时 venv，未加入项目依赖。

## 交付与遗留事项

- 已交付：代码、测试、Spec/文档、本机稀疏头与上述证据。破坏性变更，旧客户端需按 SPEC-0002 更新。
- M4 未同步：本执行环境 SSH 公钥未获目标机授权（`Permission denied (publickey)`），代码拉取与权重复制均未执行。
- M4 线上仍运行字符串键版本，进程未重启；部署与重启属独立授权项。
- 空 sparse（`[]`）保留返回，但 Milvus 拒绝空稀疏行，调用方入库前需跳过。
- Milvus 落库为 float32，检索分数与响应权重存在 float32 舍入差异。
