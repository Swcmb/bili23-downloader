# tests/unit/test_no_gui_files.py
"""T3 资源清理验证 - 确保 GUI 专属文件全部删除"""
import os
import pathlib


def test_gui_dir_removed():
    """T3.1: src/gui/ 目录应已删除"""
    assert not os.path.isdir("/workspace/src/gui"), "src/gui/ 目录应已删除"


def test_res_gui_subdirs_removed():
    """T3.2: src/res/{html,icon,image,qss}/ 应已删除"""
    for sub in ("html", "icon", "image", "qss"):
        path = f"/workspace/src/res/{sub}"
        assert not os.path.isdir(path), f"src/res/{sub}/ 应已删除"


def test_qrc_files_removed():
    """T3.3: resources.qrc 与 resources_rc.py 应已删除"""
    assert not os.path.exists("/workspace/src/res/resources.qrc")
    assert not os.path.exists("/workspace/src/res/resources_rc.py")


def test_assets_dir_removed():
    """T3.4: assets/ 目录应已删除"""
    assert not os.path.isdir("/workspace/assets"), "assets/ 应已删除"


def test_publish_workflow_removed():
    """T3.5: .github/workflows/publish.yml 应已删除"""
    assert not os.path.exists("/workspace/.github/workflows/publish.yml")


def test_issue_template_removed():
    """T3.5: .github/ISSUE_TEMPLATE/ 应已删除"""
    assert not os.path.isdir("/workspace/.github/ISSUE_TEMPLATE")


def test_translate_script_removed():
    """T3.6: scripts/translate.py 应已删除"""
    assert not os.path.exists("/workspace/scripts/translate.py")


def test_res_only_i18n_remains():
    """T3 验收: src/res/ 仅剩 i18n/"""
    res_path = pathlib.Path("/workspace/src/res")
    if res_path.exists():
        subdirs = [p.name for p in res_path.iterdir() if p.is_dir()]
        assert subdirs == ["i18n"], f"src/res/ 应仅剩 i18n/,实际: {subdirs}"
