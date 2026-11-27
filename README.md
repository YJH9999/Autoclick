# AutoClicker

一个面向 Windows 10/11 的轻量级自动点击器。基于 Python、CustomTkinter 和 pynput，提供区域选点、定时连点、全局热键、预设、托盘运行与多显示器支持。

## 下载 Windows 安装程序

前往 **[GitHub Releases](https://github.com/YJH9999/Autoclick/releases/latest)** 下载最新的 `AutoClicker-<版本>-Windows-Setup.exe` 和同目录的 `SHA256SUMS.txt`。

安装器提供简体中文图形化向导，可选择安装目录、桌面快捷方式和开始菜单快捷方式。默认安装到当前用户目录，无需安装 Python 或管理员权限。安装后主入口为 `AutoClicker.exe`，运行模块、DLL 与资源位于 `_internal`；请通过安装器或快捷方式启动，不要只复制主 EXE。

详细结构、构建和卸载说明见 [安装器文档](docs/INSTALLER.md)，发布流程见 [GitHub Releases 指南](docs/RELEASING.md)。

## 功能

- 固定坐标或跟随鼠标；支持左/右键/中键、单击/双击。
- 1 ms～1 小时间隔，无限或指定次数，0～60 秒启动倒计时。
- 区域选点、鼠标位置拾取、手动 X/Y 坐标和可点击的虚拟桌面预览。
- 选区内随机位置；可选“点击后恢复光标”。
- 默认 F6 开始/停止、F7 暂停/继续、F8 区域选点、F9 紧急停止；热键可修改。
- 8 套内置预设，自定义预设保存/删除，配置导入/导出。
- 深色/浅色主题、窗口置顶、提示音、低配模式、任务栏和按需托盘。
- 可选的区域画面“智能停止”（默认关闭，实验性）。
- 原子配置保存、异常日志、单实例和完整的无真实点击测试。

> 仅将本工具用于你有权操作的软件。部分游戏或网站禁止自动化，请遵守其规则。随机位置不用于、也不能保证绕过任何检测机制。

## 环境要求

- Windows 10/11（核心代码可跨平台测试，但窗口辅助、托盘与全局热键主要面向 Windows）。
- 源码运行：64 位 Python 3.10～3.13，需包含 Tkinter。
- 直接使用打包版本时不需要安装 Python。

## 源码运行

在项目根目录执行（PowerShell）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

也可不激活环境：

```powershell
.\.venv\Scripts\python.exe run.py
```

快速核心自检（不会移动真实鼠标或产生真实点击）：

```powershell
.\.venv\Scripts\python.exe run.py --self-test
```

## 使用方法

1. **设置位置**：点击“区域选点”拖拽选择区域，或点击“拾取鼠标位置”后单击目标点。也可以直接输入 X/Y，或在预览图上点击。选区中心是默认点击点。
2. **设置规则**：选择间隔、鼠标按键、单击/双击和重复次数。双击模式下，界面中的“点击 1 次”代表一轮双击操作。
3. **设置运行方式**：固定位置或跟随鼠标；按需启用倒计时、提示音、光标恢复、智能停止或低配模式。
4. **开始**：点击“开始点击”或按 F6。设置延迟后可切换到目标窗口；倒计时中再次按 F6 可取消。
5. **暂停/停止**：F7 暂停或继续，F6 停止。F9 会立即停止点击并取消倒计时。
6. **复用参数**：在“预设”中选择内置方案，或保存当前规则。预设只包含点击规则，不保存坐标。
7. **首选项**：标题栏“设置”可修改四个热键、关闭按钮行为，以及导入/导出 JSON 配置。

热键支持 `F6`、`Ctrl+Shift+K` 等格式，同一按键不能分配给多个动作。修改热键时会重启监听；失败会显示原因并尝试恢复旧配置。

### 区域随机范围

只有固定位置且存在选区时生效：

- `0%`：固定点击选区中心。
- `100%`：在选区中心周围、最大约覆盖整个选区的矩形范围内随机。
- 单点拾取、预览点击或手动坐标会清除旧选区，避免误用旧范围。

### 智能停止

启用后每三轮操作比较一次选区（单点时为点附近 48×48 区域）：

- 与初始画面差异过大时停止；
- 连续多次画面几乎不变时停止。

大选区仅采样中心 256×256 区域，避免高频大图截图。

该功能适合规则明确的简单场景。动画、光标、计时器、抗锯齿或完全静态的正常目标都可能导致误判，因此默认关闭。它依赖 `mss` 和 Pillow，检测失败时本次运行会安全关闭检测而不影响手动停止。

## 配置与日志

- 配置：`%LOCALAPPDATA%\AutoClicker\config.json`
- 日志：`%LOCALAPPDATA%\AutoClicker\logs\autoclicker.log`（滚动日志，单文件 512 KiB，保留 2 份）
- 未找到配置或字段无效时使用安全默认值；配置损坏会提示，不会直接覆盖原文件。
- 保存使用同目录临时文件与原子替换，避免中途退出留下半个 JSON。
- 测试可设置 `AUTOCLICKER_CONFIG_DIR` 隔离配置，设置 `AUTOCLICKER_DISABLE_FILE_LOG=1` 禁用文件日志。

如果目标应用以管理员身份运行，Windows 可能限制普通权限进程向其发送点击。通常不建议为此提升权限；确需操作时请了解安全风险，并保持目标与工具权限一致。

## 测试与验证

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -t . -v
python -m compileall -q run.py src scripts tests
```

测试覆盖配置校验/恢复/原子保存、点击引擎状态、次数限制、双击、暂停、光标恢复、异常上报、热键、智能停止、多显示器坐标及真实 Tk 窗口冒烟。鼠标后端全部使用模拟对象，不会执行真实点击。UI 测试在非 Windows 平台自动跳过。

## 构建 Windows 安装程序

安装 Inno Setup 6.5+ 后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```

输出 `dist/installer/AutoClicker-<版本>-Windows-Setup.exe` 和 `SHA256SUMS.txt`。脚本会同时构建完整的多文件应用目录，而不是将安装内容做成孤立 EXE。

## 构建可执行文件

安装开发依赖后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

输出为 `dist\AutoClicker\AutoClicker.exe`，属于启动较快的文件夹版本，必须保留旁边的 `_internal` 目录。

构建便携单文件版：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -OneFile
```

输出为 `dist\AutoClicker.exe`。构建脚本会先运行测试，再进行干净打包。首次构建会按需创建 `.venv` 并安装依赖。图标如需重新生成：

```powershell
.\.venv\Scripts\python.exe scripts\generate_icon.py
```

## 项目结构

```text
autoclick/
├─ assets/                 # 图标资源
├─ scripts/                # 图标生成、测试与打包脚本
├─ src/autoclicker/
│  ├─ app.py               # 主窗口与 UI 状态编排
│  ├─ engine.py            # 可注入鼠标后端的线程化点击引擎
│  ├─ models.py            # 数据模型、默认值、输入校验
│  ├─ config.py            # 配置迁移、规范化、原子持久化
│  ├─ hotkeys.py           # 全局热键校验与生命周期
│  ├─ overlays.py          # 单点/区域取点
│  ├─ widgets.py           # 卡片与虚拟桌面预览
│  ├─ smart.py             # 可选区域画面检测
│  ├─ platform.py          # DPI、虚拟屏幕、单实例
│  └─ ...                  # 对话框、托盘、日志、自检
├─ tests/                  # 无真实点击的单元与 UI 测试
├─ run.py                  # 源码入口
├─ requirements.txt        # 运行依赖
├─ requirements-dev.txt    # 构建依赖
└─ AutoClicker.spec        # PyInstaller 配置
```

## 已知限制

- 极高点击频率会受到 Windows、硬件和目标应用处理能力限制，不保证达到理论值。
- 取点覆盖整个 Windows 虚拟桌面；锁屏、UAC 安全桌面等系统隔离界面不在支持范围内。
- 托盘和全局热键受系统权限及其他程序占用影响；失败时仍可使用窗口按钮。
- 配置导入会安全规范化字段，但外部配置仍应来自可信来源。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
