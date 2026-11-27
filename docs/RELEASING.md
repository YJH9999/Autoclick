# GitHub Releases 发布流程

## 自动发布（推荐）

1. 确认版本号一致：`src/autoclicker/__init__.py`、`installer/version_info.txt`、`installer/AutoClicker.iss` 和 `CHANGELOG.md`。
2. 提交并推送源码到默认分支。
3. 创建与源码版本一致的标签并推送：

```powershell
git tag -a v5.0.0 -m "AutoClicker 5.0.0"
git push origin v5.0.0
```

`.github/workflows/release.yml` 会在 Windows Runner 上安装 Inno Setup、运行测试、构建安装器、生成 SHA-256 并创建 Release。Release 包含：

- `AutoClicker-<版本>-Windows-Setup.exe`
- `SHA256SUMS.txt`
- GitHub 自动生成的源码压缩包

仓库的 Actions 需要具备 `contents: write`；工作流已显式声明该权限。

## 使用 GitHub CLI 手动发布

先登录一次：

```powershell
gh auth login --hostname github.com --git-protocol https --web
```

本地构建安装器后：

```powershell
gh release create v5.0.0 `
  "dist/installer/AutoClicker-5.0.0-Windows-Setup.exe" `
  "dist/installer/SHA256SUMS.txt" `
  --repo YJH9999/Autoclick `
  --title "AutoClicker 5.0.0" `
  --generate-notes
```

不要把访问令牌写进脚本、README、Git 配置或 Release 说明。优先使用 Git Credential Manager、GitHub CLI 或 GitHub Actions 的临时 `GITHUB_TOKEN`。

## 发布后检查

- 在干净 Windows 用户环境下载并核对 SHA-256；
- 测试默认安装、自定义目录和两类快捷方式；
- 从开始菜单启动，确认 `_internal` 完整；
- 测试覆盖安装、运行中实例和卸载；
- 确认卸载不删除用户配置；
- 检查 Release 资产和源码标签一致。
