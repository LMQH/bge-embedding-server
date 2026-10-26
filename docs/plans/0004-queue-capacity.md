# PLAN-0004：扩充等待队列

> 历史恢复（2026-10-26）：恢复自 `e1ab99c` 删除前的版本，以下内容保留当时的执行范围、状态和验证记录，不作为当前部署状态或待执行命令。当前状态见 [HANDOFF](../../HANDOFF.md)。

- 状态：已完成（本地实现与验证），2026-10-21。
- 来源：用户明确要求由 1 个执行位 + 4 个等待位调整为 1 个执行位 + 19 个等待位，总计 20 个位置。
- 依据：[SPEC-0001 基本容量与执行顺序](../specs/0001-embedding-inference.md#基本容量与执行顺序)。

## 实施与验证

1. 将调度器等待上限改为 19；验证 1 个执行中请求、19 个等待请求可被接纳，第 21 个请求返回 429 / queue_full。
2. 复用现有接口测试验证 FIFO，定向检查取消、超时与关闭行为；保持默认两项 smoke 范围。
3. 同步 Spec、连接说明和交接记录，检查文档链接与容量描述。

## 证据

- 已核实本机项目解释器 `${LOCAL_CONDA_ROOT}/envs/bge-embedding/bin/python`，Python 3.12.15 / arm64；未使用 base 或系统 Python 运行测试。
- 使用上述解释器执行 `python -m pytest -q -o addopts='' tests/test_api.py -k 'http_fifo_overload_health_and_shutdown or client_disconnect_releases_queue_but_not_active_slot or queue_timeout_and_shutdown_waiters or asgi_disconnect_event_frees_waiting_slot or success_preserves_text_usage_and_order or missing_key_fails_startup'`：6 passed，29 deselected。覆盖 20 个位置接纳、第 21 个返回 queue_full、FIFO、取消释放等待位且不提前释放执行位、30 秒默认等待值、超时及关闭行为，含默认 2 项 smoke。
- 本轮仅修改本地项目，尚未更新或重启 M4 服务；新容量需同步调度器并重启后生效。未做真实模型并发压测，不将队列位置数视为吞吐保证。
- 文档检查：HANDOFF 与 docs 下共 19 份 Markdown、90 个本地链接路径均存在；Spec 与连接说明均为 19 个等待位，PLAN-0002 保留初版历史值并链接本次变更。
