# tests/unit/test_no_config_attr_access.py
"""T2.13 验证全仓库不再有 config.get(config.xxx).value 模式

原 GUI 代码使用 qfluentwidgets.QConfig API,调用形如:
    config.get(config.video_quality_id).value

新 Config 类已重写为:
    config.get("video_quality_id")

本测试通过 grep 扫描 src/util/ 下所有 .py 文件,确保 legacy 模式已全部替换。
"""
import subprocess


def test_no_legacy_config_access_pattern():
    """验证 src/util/ 下不再有 config.get(config.xxx) 模式"""
    # 注意:BRE 中 \) 会触发 "Unmatched ) or \)" 错误,
    # 因此此处直接使用 ( 与 ) 字面量(在 BRE 中字面量圆括号无需转义)
    result = subprocess.run(
        ["grep", "-rn", "--include=*.py",
         "config\\.get(config\\.", "src/util/"],
        capture_output=True, text=True
    )
    assert result.stdout == "", f"仍有 legacy config 访问模式:\n{result.stdout}"


def test_no_legacy_config_attr_pattern():
    """验证 src/util/ 下不再有 config.get(config.xxx).value 模式"""
    # BRE 中 ) 为字面量,无需转义;圆括号转义 \( \) 表示分组
    result = subprocess.run(
        ["grep", "-rn", "--include=*.py",
         "config\\.get(config\\.[a-zA-Z_][a-zA-Z0-9_]*)\\.value", "src/util/"],
        capture_output=True, text=True
    )
    assert result.stdout == "", f"仍有 config.get(config.xxx).value 模式:\n{result.stdout}"
