"""只收集 Stardot 实际使用的 QML 模块，避免打入整个 Qt 附加模块集。"""

from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
source_root = Path(pyside6_library_info.location["QmlImportsPath"])
destination_root = Path(pyside6_library_info.qt_rel_dir) / "qml"
# 当前界面显式使用 Basic；新增 QML import 时需要同步检查此列表。
modules = (
    "QtQml", "QtQml/Models", "QtQml/WorkerScript", "QtQuick", "QtQuick/Window",
    "QtQuick/Layouts", "QtQuick/Templates", "QtQuick/Controls",
    "QtQuick/Controls/impl", "QtQuick/Controls/Basic", "QtQuick/Controls/Basic/impl",
)
for module in modules:
    qmldir = source_root / module / "qmldir"
    if not qmldir.is_file():
        raise RuntimeError(f"Required Qt module missing: {qmldir}")
    plugin_binaries, plugin_datas = pyside6_library_info._process_qml_plugin(qmldir)
    for sources, output in ((plugin_binaries, binaries), (plugin_datas, datas)):
        for source in sources:
            source = Path(source)
            if source.suffix == ".qmltypes":
                continue
            relative = source.relative_to(source_root)
            destination = destination_root / (relative if source.is_dir() else relative.parent)
            output.append((str(source), str(destination)))
