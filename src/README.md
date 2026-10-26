# 源码目录

- `bge_embedding/`：本项目的模型适配、API、队列与启动代码。
- `vendor/mlx/`：Apple 官方 MLX 仓库的独立本地克隆，保留上游目录与 Git 元数据。

实际模块和文件职责见[源码接入与代码结构](../docs/references/0002-source-layout.md)。

## MLX 来源记录

| 项目 | 本次记录 |
| --- | --- |
| 获取日期 | 2026-10-15 |
| 官方远程地址 | `https://github.com/ml-explore/mlx.git` |
| 本地位置 | `src/vendor/mlx/` |
| 获取方式 | `git clone --depth 1 https://github.com/ml-explore/mlx.git src/vendor/mlx` |
| 分支 | `main` |
| 提交号 | `36969c094354086e15d2a327a9c50feb20b9cf11` |
| 提交日期 | 2026-10-14 |
| 提交标题 | `[BUG] Metal fence deadlock (#4689)` |
| 许可证 | MIT，原始文件保留在 `vendor/mlx/LICENSE` |
| 本次修改 | 无；未修改上游源码 |

这是开发分支的源码快照，不是已选定的生产版本。没有执行 MLX 编译、依赖安装或模型下载；本记录不能用作运行时已安装版本的证明。

## 恢复同一份源码

需要重新获取时，在项目根目录运行以下命令；仅用于 `src/vendor/mlx/` 不存在的情况，不用于覆盖已有工作区：

```sh
git init src/vendor/mlx
git -C src/vendor/mlx remote add origin https://github.com/ml-explore/mlx.git
git -C src/vendor/mlx fetch --depth 1 origin 36969c094354086e15d2a327a9c50feb20b9cf11
git -C src/vendor/mlx checkout --detach 36969c094354086e15d2a327a9c50feb20b9cf11
```

检出后为 detached HEAD；更新上游须同步本记录并重新验证运行时。根 `.gitignore` 忽略该克隆，也不是 submodule，新机器需单独获取。
