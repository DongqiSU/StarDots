# 第 5 轮：把 Stardot 打成 Windows 体验版

## 1. 体验版的范围

版本标识：`0.1.0-preview.1`，面向 Windows 11 x64。现有任务清单功能可以安装体验；提醒、完整任务日历、全局快捷键、备份恢复和位置记忆继续在后续模块实现。设置日期暂时不会发送通知。

## 2. 打包与安装器是两件事

平时执行 `uv run main.py`，依靠的是 `.venv` 中的 Python、Qt 和第三方模块。打包会把运行必需的解释器、动态库、QML 和星星图像一并收集，让另一台没有 Python 的电脑也能启动程序。

安装器负责把这些文件放到合适的位置、创建快捷方式、登记卸载入口。程序运行时不需要安装器继续工作。

本轮提供目录形式的程序、便携 ZIP，以及 Windows 安装包。便携版需要整个目录一起使用，不能只拷走 `Stardot.exe`。

## 3. 为什么本轮使用 PyInstaller

原方案优先验证 pyside6-deploy / Nuitka。本机已安装的是 Visual Studio 2019；当前 Nuitka 文档要求 Visual Studio 2022 或更新版本，Python 3.13 的 MinGW 路线也有额外限制。

体验版采用 PyInstaller 收集现成运行库，再用 Inno Setup 生成安装包，避免为这次验证升级整套 C 编译工具。应用仍使用原来的 Python + Qt + QML，uv 继续管理环境；PyInstaller 单独放在 `build` 依赖组，版本由 `uv.lock` 锁定。

- [Nuitka 编译器要求](https://nuitka.net/user-documentation/user-manual.html#c-compiler)
- [Qt 的 PyInstaller 部署说明](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
- [Inno Setup 官方下载](https://jrsoftware.org/isdl.php)

## 4. 哪些文件负责构建

| 文件 | 职责 |
| --- | --- |
| `tools/build_preview.py` | 生成多尺寸图标、版本信息，执行打包、自检、压缩和安装器编译 |
| `build-support/Stardot.spec` | 指定启动入口、界面资源、程序图标及目录式输出 |
| `build-support/hooks/hook-PySide6.QtQml.py` | 只收集当前使用的 QML 模块与 Basic 样式 |
| `build-support/Stardot.iss` | 安装位置、快捷方式、卸载入口和安装界面语言 |
| `stardot/smoke.py` | 在打包后的程序内部检查窗口、图像、识别和数据库操作 |
| `tools/check_installer.py` | 在工作区测试目录验证安装、重复安装、卸载及独立数据保留 |

“只收集用到的模块”会减少安装体积；以后增加新的 QML 模块，需要同步更新收集清单并重新验证。安装体积和运行内存是两个指标，不能因为压缩包小就宣称运行省内存。

本轮还遇到一个典型打包问题：构建进程继承了其他工具的 `PATH`，把同名的 ICU 动态库收进了程序，导致 Qt 导入失败。现在构建和运行自检都会隔离搜索路径，并检查动态库来源。源码能跑、打包后不能跑，往往就需要检查这种环境差异。

## 5. 重复构建

仅生成便携版：

```powershell
uv run --frozen --group build python tools/build_preview.py
```

生成便携版和安装包：

```powershell
uv run --frozen --group build python tools/build_preview.py --iscc artifacts/toolchain/inno/ISCC.exe
```

Inno Setup 是独立工具，不通过 uv 安装。上面的编译器路径是本次配置的位置；其他电脑需从官方渠道安装，再通过 `--iscc` 指定自己的路径。

产物放在 `dist/`，中间文件在 `build/`，自检报告在 `artifacts/packaging/`。这些生成文件都已从版本控制中忽略。`SHA256SUMS.txt` 可以校验分发文件是否完整。

## 6. 安装和数据

- 默认仅为当前用户安装到 `%LOCALAPPDATA%\Programs\Stardot`，无需管理员权限。
- 任务仍在 `%LOCALAPPDATA%\Stardot\stardot.sqlite3`，与程序文件分开。
- 更新前从托盘退出旧程序，然后覆盖安装；数据库保留。
- 卸载删除程序和快捷方式，保留任务数据。
- 源码版、便携版和安装版在同一个 Windows 账户下共用任务目录，体验时只运行其中一份。
- 本体验版未进行代码签名，Windows 可能显示未识别发布者提示；目前用于本机或熟悉用户的内部体验。

## 7. 验证的边界

冻结程序自检会清除子进程中的开发环境路径，用临时数据库验证 Qt 窗口、QML、SVG、概要日期、保存、编辑、归档、删除撤销和数据库重开。安装检查还会将程序安装到带中文与空格的新目录，再重复安装和卸载。

这些检查是在当前 Windows 11 上进行，不能代替另一台干净 Windows 电脑的验证。实际 Edge／微信拖放、不同输入法、显卡和多屏缩放的覆盖，以及长期内存表现仍需持续收集。

本次构建结果：25 项单元测试通过；无开发路径的冻结程序自检通过，未记录 Qt 错误；中文及空格路径安装、安装后运行、重复覆盖安装、卸载和独立 SQLite 样本保留均通过。测试程序已卸载，没有替用户安装到默认程序目录。

| 产物 | 大小 |
| --- | --- |
| 安装包 `Stardot-0.1.0-preview.1-windows-x64-setup.exe` | 约 34.7 MiB |
| 便携包 `Stardot-0.1.0-preview.1-windows-x64-portable.zip` | 约 49.7 MiB |
| 解压后的程序目录 | 约 130.8 MiB |
