# PLAN-0008：仓库连接信息脱敏与历史清理

> 历史恢复（2026-10-26）：恢复自 `e1ab99c` 删除前的版本，以下内容保留当时的执行范围、状态和验证记录，不作为当前部署状态或待执行命令。当前状态见 [HANDOFF](../../HANDOFF.md)。

状态：已完成（本轮文档脱敏、远端 main 重写与当前本地仓库清理；其他副本单独处理）。日期：2026-10-22。依据：用户要求内网 Tailscale 地址、本机路径等不留在 Git 历史中。本任务只修改文档与 Git 数据，不改变服务行为，无需新增行为 Spec。

## 范围与原则

- 清除真实内网 IP、设备名、登录用户名、本机与目标机用户目录；不在本 Plan 重复原值。
- 文档统一使用 `<TAILSCALE_IP>`、`<REMOTE_HOSTNAME>`、`<REMOTE_USER>`、`${LOCAL_CONDA_ROOT}`、`${REMOTE_CONDA_ROOT}`、`${REMOTE_HOME}`、`${REMOTE_PROJECT_DIR}` 等占位符；命令使用的变量须从私有记录设置。不要据占位符猜实际安装路径。
- 保留 localhost、通配监听地址、环境名称、硬件规格和历史验证结论。保留作者身份元数据；作者邮箱是否改为 GitHub noreply 地址，待用户另行确定，不猜造地址。
- 实际连接信息仅存私有配置或被忽略的 `docs/service-connection.local.md`；不把原值清单、备份、替换规则或未脱敏补丁提交到 Git。

## 审计结果

- 远端只发布 `main`，无标签；清理前起点为 `34aede4191b9c6743b503415dfb0c3fba3b421a3`。
- 从首次提交起即有连接信息，5 个提交均需重写。已检查所有本地引用可达的 5 个提交、79 个唯一文件 blob、文件路径与提交消息；发现项在 12 份 Markdown 中，提交消息未命中同类信息。扫描针对连接信息，不等同于完整凭据审计。
- 清理前工作仓库另有 Codex 私有引用；仅移动 `main` 或清理 reflog，不能清除仍被这些引用保留的旧对象。推荐在远端替换成功后重新克隆工作仓库，单独迁移被忽略的配置和模型，不复制旧 `.git`。

## 执行与验证

| 步骤 | 状态 | 验证标准 |
| --- | --- | --- |
| 当前文档脱敏，补充忽略项与协作约束 | 已完成 | 跟踪文件不再包含已发现原值，示例变量含义明确 |
| 在独立远端镜像中使用 git-filter-repo 演练 | 已完成 | 全部历史文件与消息无原值；提交数量、父子关系及非文档 blob 保持一致 |
| 发布当前文档变更并替换远端历史 | 已完成 | 使用明确旧 SHA 的 lease；远端最终指向已验证的新历史 |
| 清理当前本地仓库并重新克隆验证远端 | 已完成 | 新克隆与本地全部 Git 对象扫描通过 |
| 重建其他机器克隆，处理 GitHub 残留引用 | 后续，未执行 | 新克隆扫描通过；旧克隆不再用于推送 |

演练产物均位于 Git 忽略的 `.cache/privacy/`，目录权限 700；替换规则权限 600，包含原值，完成后删除。工具使用任务局部 venv 内的 git-filter-repo 2.47.0，不修改应用 conda 环境。

在新建的远端镜像中执行（路径由仓库根目录解析）：

```sh
ROOT="$PWD"
git clone --mirror https://github.com/LMQH/bge-embedding-server.git .cache/privacy/clean.git
cd .cache/privacy/clean.git
"$ROOT/.cache/privacy/tool-env/bin/git-filter-repo" \
  --sensitive-data-removal \
  --replace-text "$ROOT/.cache/privacy/replacements.txt" \
  --replace-message "$ROOT/.cache/privacy/replacements.txt"
# 本次 sensitive-data-removal 模式仍保留 origin，显式移除以防误推送。
git remote remove origin
```

替换规则需覆盖所有已核实原值及其历史变体。本次实测 `--sensitive-data-removal` 模式保留 origin，演练后已显式移除以防误推送。不要在原工作仓库直接执行上述重写命令。

2026-10-22 演练验证结果：

- 5 个提交全部重写，提交数、父子关系、作者 / 提交者及时间保留，消息按替换规则核对一致。
- 逐提交核对全部文件内容与替换规则一致；116 次非文档 blob 比对完全一致，服务实现、配置示例及测试均未改变。
- 扫描清理镜像的全部 115 个现存 Git 对象，未发现已核实原值、用户绝对目录、已发现设备 / 用户名或 Tailscale IPv4；`git fsck --full` 通过。
- 当前 32 份 Markdown、183 个本地链接检查通过；私有连接记录与替换规则的 ignore 检查通过；`git diff --check` 通过。
- 镜像新 main 为 `1756474e57a106d77eb622d862ddcfd27898547b`，仅用于演练，不包含本轮尚未提交的文档补充；映射与验证明细见被忽略的 `.cache/privacy/clean.git/filter-repo/commit-map` 和 `.cache/privacy/verification.json`。
- 未运行服务测试：此次修改仅涉及文档和 Git；未推送、未替换原工作仓库历史、未操作部署机或其他克隆。

2026-10-22 用户已明确授权“重写并推送远端 main”；发布前再次核对远端仍为审计起点，无新增分支或标签。

## 正式执行结果

2026-10-22 按用户授权执行：

- 将本轮 16 个文件的脱敏及维护改动纳入清理后的历史，新增提交 `7cb70ea`；以清理前完整 SHA 作为 `--force-with-lease` 条件，成功替换远端 `main`。保留 5 个原提交的顺序和信息，全部原 SHA 已改变。
- 从 GitHub 重新建立镜像，确认只发布 `main`；6 个提交、128 个全部现存 Git 对象扫描通过，未检出本轮原值及同类连接信息；`git fsck --full` 通过。源码、测试与配置示例均与清理前一致，只有文档和 ignore 规则变化。
- 逐文件确认当前工作区与已发布树完全一致后，同步本地 `main` / `origin/main`，删除 5 个旧 Codex 引用，执行 `git reflog expire --expire=now --all` 和 `git gc --prune=now`。本地全部 128 个 Git 对象复扫与 `git fsck --full` 通过，工作区干净。
- 本节与 HANDOFF 的完成记录随后作为普通文档提交发布；该提交延续已清理历史，不重复重写。
- 临时替换规则含原值，验证结束后删除；模型、私有配置及运行缓存不移动。作者身份元数据保留。
- 不改变服务行为，未运行服务测试，未连接部署机；部署机及其他旧克隆、fork、GitHub 缓存与 PR 引用未清理。其他克隆应重新获取新历史，避免推回旧提交；不能承诺所有外部副本已删除。

## 最终发布步骤与影响

1. 确认当前脱敏 diff；将这些改动纳入清理副本的新提交，或先提交当前文档后重新建立镜像演练，确保新规则、索引和 Plan 一并发布。当前镜像演练只重写原有 5 个提交，不自动包含未提交的文档补充。
2. 再次核对远端 refs；如出现新提交、分支或标签，先补充扫描与重写，不覆盖他人更新。
3. 核实并显式指定发布目标，使用 `git push --force-with-lease=refs/heads/main:<已核实的远端旧SHA> <远端URL> refs/heads/main:refs/heads/main`。不使用盲目 `--force` 或 `--mirror` 推送，不默认删除 GitHub 管理的 refs。分支保护若禁止重写，需仓库管理员配合。
4. 重写使受影响提交的 SHA 全部变化，并使相关签名失效。所有开发机、部署机及其他克隆应切换到新历史，避免把旧分支重新 merge / push 回来。重建前保留未提交工作与私有运行文件，避免影响服务；本轮不连接或修改部署机。
5. 已有 fork、PR 引用、GitHub 缓存及旧克隆不会因 force push 自动消失。检查相关副本；必要时向 GitHub Support 申请清除缓存与 PR 引用，是否受理以其敏感数据政策为准。不能承诺删除所有外部副本。
6. 确认远端新历史可重新克隆且扫描通过后，再删除旧克隆及临时含原值规则。若必须保留旧工作仓库，需要单独处理全部旧 refs、reflog 和不可达对象，不能只执行 `git gc` 就称清理完成。

参考：[GitHub 敏感数据清理指南](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)、[git-filter-repo 官方手册](https://github.com/newren/git-filter-repo/blob/main/Documentation/git-filter-repo.txt)。
