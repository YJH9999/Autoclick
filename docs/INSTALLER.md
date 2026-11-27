# 安装器与安装目录说明

## 推荐目录结构

源码继续采用 `src/autoclicker` 分层模块；发布时采用 PyInstaller `onedir`，安装后目录如下：

```text
AutoClicker/
├─ AutoClicker.exe          # 唯一启动入口，用户和快捷方式只调用它
├─ _internal/
│  ├─ assets/icon.ico       # 图标资源
│  ├─ customtkinter/        # GUI 框架及主题、字体资源
│  ├─ pynput/               # 鼠标与全局热键后端
│  ├─ pystray/              # 托盘后端
│  ├─ mss/                  # 可选画面检测后端
│  ├─ PIL/                  # 图像处理模块
│  ├─ *.dll                 # Python 与原生依赖
│  └─ *.pyz / *.zip         # 按模块编译打包的应用与标准库归档
└─ unins000.exe / unins000.dat
```

应用自身模块在 `src/autoclicker/` 中保持独立：主窗口通过明确导入调用 `ClickEngine`、`ConfigStore`、`HotkeyManager`、取点和托盘组件。PyInstaller 将这些 Python 模块编译进 PYZ 归档，而不是把源码散落到安装目录；DLL、第三方包和资源仍作为独立文件加载。这样既能防止用户误改运行模块，也满足多文件发布和统一入口要求。

## 安装器功能

`installer/AutoClicker.iss` 提供：

- 简体中文图形化向导与 MIT 许可页；
- 自定义安装目录，默认 `%LOCALAPPDATA%\Programs\AutoClicker`；
- 可选桌面快捷方式和开始菜单快捷方式；
- 安装后启动、运行中实例检测和 Windows 卸载入口；
- 当前用户安装，无需管理员权限；
- 完整复制 `_internal`，不依赖目标电脑已有 Python。

卸载只移除程序文件和快捷方式，不删除 `%LOCALAPPDATA%\AutoClicker` 中的用户配置与日志。

## 本地构建

先安装 Python 3.10～3.13 和 Inno Setup 6.5 或更新版本，然后在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```

脚本会创建 `.venv`、安装依赖、执行测试、构建文件夹版并编译安装器。输出：

```text
dist/installer/AutoClicker-5.0.0-Windows-Setup.exe
dist/installer/SHA256SUMS.txt
```

跳过已经执行过的测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1 -SkipTests
```

如果 ISCC 不在常见位置，可显式传入：

```powershell
.\scripts\build_installer.ps1 -IsccPath "C:\path\to\ISCC.exe"
```

## 静默验证参数

安装器也保留 Inno Setup 标准命令行能力，便于测试：

```powershell
.\AutoClicker-5.0.0-Windows-Setup.exe /VERYSILENT /NORESTART /DIR="D:\Apps\AutoClicker" /TASKS="desktopicon,startmenuicon"
```

生产发布建议使用图形化向导，不向普通用户宣传静默安装。

## 签名说明

仓库不包含证书或签名密钥。未签名安装器可能触发 Windows SmartScreen，这是当前已知发布限制。正式分发时可使用受信任代码签名证书，对主 EXE 和安装器签名，并将签名步骤接入本地安全构建流程；不要把证书、密码或令牌提交到仓库。
