# Stardot · 星点

一个暖色、安静的桌面待办应用。Python + PySide6 + Qt Quick/QML + SQLite，使用 uv 管理环境。

## 首版源码

当前源码版本为 `1.0.0`。按用户要求，本轮不生成安装包，直接通过下面的命令运行。`dist/` 中此前的体验版产物不包含本轮新功能；运行新源码前先从托盘退出旧版。

## 运行与构建

```powershell
uv run main.py
uv run --group build python tools/build_preview.py --iscc artifacts/toolchain/inno/ISCC.exe
```

第一条命令用于本轮体验。第二条保留为以后构建时使用，本轮未执行；构建沿用体验版脚本名称，产物版本由 `stardot/__init__.py` 决定。安装器需要 Inno Setup，详细过程见[打包讲解](docs/lesson-05-preview-packaging.md)。

## 首版功能

- 金色桌面星星：悬停微光、拖入与完成表情、边缘吸附、位置记忆、临时隐藏与找回。
- 清单：新增、编辑、完成、归档、恢复，归档删除及 6 秒撤销。
- 手动输入、文字拖入、复制后全局快捷键录入；本地概要整理、明确日期识别。
- 日期点选、小时／分钟选择、滚轮调整与取消；按约定显示黑、橙、赭黄和暖绿色。
- 居中任务日历：格内任务、溢出数量、当天完整列表，与清单共用任务；关闭不自动弹回清单。
- 本机提醒：默认提前 10 分钟，小铃铛可改为准时、30 分钟或关闭；启动、睡眠恢复时合并遗漏提醒，持久化去重。
- 设置中的备份导出与恢复；恢复前校验、展示数量、确认替换，并自动备份当前数据。
- 单实例运行：重复启动打开已有清单，退出时先保存草稿。

## 常用操作

| 操作 | 方法 |
| --- | --- |
| 展开／收起清单 | 点击星星 |
| 新增 | 清单右上角 + |
| 复制文字录入 | 复制后按 `Ctrl + Alt + S` |
| 找回星星 | `Ctrl + Alt + Space` 或托盘菜单 |
| 保存 | `Ctrl + Enter` 或对勾 |
| 确认概要／换行 | 灰色概要时 Enter 确认正文，其余时候换行；输入法组词优先 |
| 编辑／切换 | 单击卡片正文；再次点击保存并关闭，点击另一张先保存再切换 |
| 原文 | 双击编辑区正文切换原文，再双击返回 |
| 日期 | 小日历点选，按需选择时刻；对数字滚轮调整，× 取消 |
| 提醒 | 有时刻的任务点小铃铛设置 |
| 归档／恢复／删除 | 文件夹查看，勾选框恢复，垃圾桶删除 |
| 任务日历 | 清单右侧小日历；点击日期查看完整列表 |
| 设置与备份 | 清单右侧设置图标，或托盘菜单 |
| 退出 | 托盘菜单退出，或应用内 `Ctrl + Q` |

关闭、切换视图和退出均会先保存当前草稿；失败时保留内容。空白新建直接关闭。普通提示约 1.8 秒、错误约 3.5 秒消失，撤销提示保留 6 秒。快捷键可在设置中换组，冲突时不覆盖原有可用配置。

## 提醒与数据

没有具体时刻不提醒，只有日期的任务仍出现在日历中。保持程序在托盘运行才会按时发送通知；重启／唤醒后合并补提醒。完全退出或关机时不通知，系统勿扰模式可能隐藏通知。

数据位于 `%LOCALAPPDATA%\Stardot\stardot.sqlite3`，位置和快捷键设置位于同目录的 `settings.ini`。升级旧数据库会先创建一致性备份，再迁移到 v3；**旧版任务仍保持无提醒状态**，可逐项点铃铛开启。

导出的 `.sqlite3` 备份包含任务、原文、日期、归档状态、提醒设置及发送记录，不包含快捷键和窗口位置。恢复会替换当前任务，并生成 `stardot.before-restore-随机编号.sqlite3` 安全副本；不执行导入文件中的 SQL。

## 验证

```powershell
uv run python -m unittest discover -s tests -v
uv run tools/check_ui.py
uv run tools/check_release.py
uv run tools/check_release.py --native --cycles 300
uv run tools/check_single_instance.py
uv run tools/check_window_lifecycle.py
```

验证均使用临时数据库，不修改日常任务。原生测试会短暂打开测试窗口，注册并注销热键，发送测试按键，完成后退出。截图、性能和结果报告输出到 `artifacts/`。

Edge／微信不同文字区域的拖出能力、真实输入法、物理多屏混合 DPI、实际睡眠恢复和系统勿扰显示仍需在具体设备上体验。自动化测试包含模拟拖放、输入法预编辑、负坐标屏幕、唤醒事件及提醒时钟跳变，不能替代这些外部环境实测。

## 学习文档

- [需求说明书](docs/stardot-requirements.md)
- [技术方案](docs/stardot-technical-plan.md)
- [第 1 轮：Qt 窗口](docs/lesson-01-qt-window.md)
- [第 2 轮：任务与存储](docs/lesson-02-tasks-and-storage.md)
- [第 3 轮：识别与日期](docs/lesson-03-capture-and-dates.md)
- [第 4 轮：交互修正](docs/lesson-04-interaction-polish.md)
- [第 5 轮：体验版打包](docs/lesson-05-preview-packaging.md)
- [第 6 轮：首版功能与验证](docs/lesson-06-first-release.md)
