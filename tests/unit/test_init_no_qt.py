# tests/unit/test_init_no_qt.py
"""T2.14 验证 util 下所有 __init__.py 无 PySide6 导入

util/ 作为业务逻辑层,应彻底去除 Qt 依赖。任何 __init__.py 中的
PySide6 直接或间接导入都会污染整个子包,导致 CLI 模式下也不可避免地
加载 Qt,违反"业务层纯 Python"的设计约束。
"""
import pathlib


def test_all_init_files_no_qt():
    """遍历 util 下所有 __init__.py,断言无 PySide6 导入"""
    util_root = pathlib.Path("/workspace/src/util")
    init_files = list(util_root.rglob("__init__.py"))
    assert init_files, "应至少找到一个 __init__.py"
    violations = []
    for init in init_files:
        content = init.read_text(encoding="utf-8")
        if "PySide6" in content:
            violations.append(str(init))
    assert not violations, f"以下 __init__.py 仍含 PySide6: {violations}"
