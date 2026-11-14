# Z5 Droidspaces Kernel CI

独立的 Galaxy Z Fold5 / Z Flip5 内核构建仓库，为 [Z5 Droidspaces Kernel](https://github.com/Alhkxsj/android_kernel_samsung_sm8550_Z5) 提供构建、验证、发布和上游更新提醒。

## 构建

在 Actions 中运行 **Build Kernel**：

- Project：固定为 `z5_sm8550`
- Branch：`main`（LKM）或 `bakasu`（BakaSU + SUSFS）
- 默认开启 ThinLTO、Hybrid Mount 和正式发布，BBG 默认关闭，SUSFS 自动跟随分支
- 通常只需选择分支；`main`、`bakasu` 被推送时也会自动触发

构建使用 `clang-r450784e`、ThinLTO 和 AnyKernel3，产物包含 ZIP、`.config`、`vmlinux.symvers`，并可自动发布到内核仓库 Releases。

## 验证

每次正式构建都会检查：

- 43 项启用配置和 `IP_SET_MAX=65534`
- `MODVERSIONS=y`
- `CFS_BANDWIDTH`、`CGROUP_PIDS`、`CGROUP_DEVICE`、`NF_TABLES`、`BRIDGE_NETFILTER` 保持关闭
- 15,379 个基线符号：**0 CRC mismatch、0 missing**
- AnyKernel 仅允许 `q5q`、`b5q`
- 工具链 SHA-256

CI Core 测试：

```bash
cargo test --locked --manifest-path ci_core_rs/Cargo.toml
```

## 上游监视

[Watch Z5 Upstream](https://github.com/Alhkxsj/Kokuban_Kernel_CI_Center/actions/workflows/watch-z5-upstream.yml) 每 6 小时检查：

- Z5 `main`
- Z5 `bakasu`
- CI `main`

[监视 Issue #1](https://github.com/Alhkxsj/Kokuban_Kernel_CI_Center/issues/1) 只在发现新提交时追加提醒，不重复刷评论，不依赖 fork 网络，也不会自动合并或覆盖本地修改。

## 主要文件

- `configs/projects.json`：Z5 构建配置、kABI 基线和最终配置门禁
- `configs/anykernel_configs.json`：设备检查和打包规则
- `ci_core_rs/`：Rust 构建核心
- `scripts/watch-z5-upstream.py`：独立上游比较与 Issue 通知
- `.github/workflows/`：构建和监视工作流

构建成功不代表已实机验证，刷入前仍需备份并确认固件兼容性。
