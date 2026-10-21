# PLAN-0005：统一文件配置

- 状态：已完成（本地改造、验证与 M4 部署），2026-10-21。
- 来源：用户接受 16 项运行参数集中到 TOML、启动统一校验、私有文件权限 600、修改后重启的建议，并授权改造。
- 依据：[SPEC-0001](../specs/0001-embedding-inference.md) 的启动配置、容量及日志契约。

## 实施与验证

1. 提供 TOML 示例及完整配置加载器；验证缺项、未知项、类型、范围、Key、模型路径和模型长度约束，错误不得回显凭据。
2. 将配置传入 API、调度器、模型与日志；验证现有行为保持，自定义容量、请求限制和日志参数生效。
3. 改造 launchd 安装及 HTTP 冒烟脚本；验证私有文件权限、配置路径及旧 Key 迁移，不启动或重启实际服务。
4. 同步部署说明、Spec、索引与 HANDOFF；记录项目环境中的实际验证结果及未部署状态。

## 验证记录

- 改造前，已核实的本机 `bge-embedding` 解释器执行 `python -m pytest -q -o addopts='' tests/test_api.py`：35 passed。
- 项目解释器：`${LOCAL_CONDA_ROOT}/envs/bge-embedding/bin/python`，Python 3.12.15 / arm64，沿用已核实环境，无新增依赖。
- 改造后执行 `python -m pytest -q -o addopts='' tests/test_api.py tests/test_config.py tests/test_install.py`：65 passed。包含原有接口回归、配置字段 / 类型 / 范围拒绝、模型长度校验、自定义请求与队列限制、MLX 参数传递、日志参数、无效配置安全退出，以及首次安装 / 旧 plist 迁移 / 重复安装保持 TOML 内容和 Key、文件权限 600。
- 默认 `python -m pytest -q`：2 passed；默认范围仍仅 2 项 smoke，两项亦包含在上述最终 65 项中。
- 本机真实模型验证：以临时私有 TOML（权限 600）、动态分配的本地端口和临时日志路径启动服务，执行 `tests/verify_http.py --config <临时文件>`，健康、无 Key 被拒绝、单条 / 两条批量、1024 维有限归一化向量全部通过。随后向该临时进程发送 SIGTERM 并确认退出，临时配置及日志已删除。未创建或修改实际常驻配置。
- 文档检查：23 份 Markdown 的 114 个本地链接路径均存在；示例恰含 16 项参数，Key 为空，队列总位置为 20。根目录未生成私有 `config.toml`。

## 交付与遗留事项

- 运行参数的唯一基线为根目录 `config.example.toml`；实际私有文件需通过安装脚本生成或手工准备。服务不再用四个旧 `BGE_*` 环境变量兜底；路径基于配置文件目录，改动后重启生效。
- 本地改造交付后，用户明确授权同步 M4 并重启，后续部署结果见下节。未做压力测试或参考评测。

## M4 部署与验证（2026-10-21）

- 通过已有 SSH 认证连接 `${REMOTE_USER}@<TAILSCALE_IP>`；核实 `${REMOTE_CONDA_ROOT}/envs/bge-embedding/bin/python` 为 Python 3.12.15 / arm64。原服务健康 200，监听 `0.0.0.0:8000`，原私有 plist 权限 600，原项目无 TOML。
- 将旧源码、文档、测试及私有 plist 备份到目标项目 `.cache/deploy-config-20261021-j_kuhy_5/`；创建时 umask 077，目录权限 700，归档及 plist 权限 600。同步自有源码、部署脚本、测试、文档和示例，未复制权重、缓存、环境或上游源码。
- 目标机项目解释器执行相同定向命令：65 passed。随后 `launchctl bootout` 停止旧任务，以目标解释器运行 `deploy/install.py --config ${REMOTE_PROJECT_DIR}/config.toml`；断言新 TOML 的 Key、host、port 和模型路径与旧 plist 完全一致，等待位为 19，文件权限 600。
- 新 plist 指向目标解释器及 TOML，已移除旧环境变量。首次紧接 bootout 的 bootstrap 返回 5 / Input/output error；复查 plist 语法与所有者正常、任务已卸载，随后重试 bootstrap 成功。最终 launchd 状态 running，检查时 PID 74886，进程命令含正确 `--config` 路径。
- 目标机执行 `python tests/verify_http.py --launchd --url http://<TAILSCALE_IP>:8000`：PASS。另从本机经 Tailscale 真实检查健康、无 Key 返回 401、正确 Key 的单条及两条批量调用、1024 维有限归一化向量：PASS。Key 仅在进程内存用于比对和调用，不打印或复制到本地文件。
- 8 个关键部署文件的 SHA-256 与本地一致。线上当前配置为 1 个执行位 + 19 个等待位，总计 20 个位置，30 秒排队超时；未做线上并发压测。
