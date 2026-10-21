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

此流程按提交号恢复内容，检出后为 detached HEAD。不要用未经核对的 `git pull` 替代版本记录；有意更新上游后应同步此记录，并重新验证实际使用的运行时。

根 `.gitignore` 忽略该本地克隆。当前不是 submodule；在新机器上仅获取父项目文件不会自动带下 MLX 源码，需要执行上述获取步骤。

## 阅读上游源码的入口

以下路径均相对于 `src/vendor/mlx/`：

| 路径 | 内容 |
| --- | --- |
| `README.md` | 框架介绍、安装及文档入口 |
| `mlx/` | C++ 核心实现 |
| `mlx/backend/metal/` | Apple GPU 的 Metal 后端 |
| `python/src/` | Python 绑定 |
| `python/mlx/` | Python 层，包括神经网络与优化器等 |
| `docs/src/install.rst` | 与此提交配套的安装及构建说明 |
| `CMakeLists.txt`、`setup.py`、`pyproject.toml` | C++ 与 Python 构建入口 |

构建或安装前，先确定项目 conda 环境与运行依赖方式，再按对应版本的说明执行。上游测试与本项目的 BGE-M3、API 验收测试分开维护。
