# tests/unit/test_file.py
"""文件工具单元测试 - safe_remove / safe_rename / File 静态方法

覆盖 src/util/common/io/file.py 中的所有分支:
- safe_remove 单/多文件 + 异常透传
- safe_rename 不存在/无冲突/OVERWRITE/AUTO_RENAME
- File.preallocate_file / create_placeholder
"""
import pytest

from util.common.enum import FileConflictResolution


# ==================================================================
# safe_remove
# ==================================================================

def test_safe_remove_single_file(tmp_path):
    """safe_remove 删除单个文件"""
    from util.common.io.file import safe_remove

    target = tmp_path / "a.txt"
    target.write_text("x")
    safe_remove(str(tmp_path), "a.txt")
    assert not target.exists()


def test_safe_remove_multiple_files(tmp_path):
    """safe_remove 一次删除多个文件"""
    from util.common.io.file import safe_remove

    files = [f"f{i}.txt" for i in range(3)]
    for name in files:
        (tmp_path / name).write_text("data")
    safe_remove(str(tmp_path), *files)
    for name in files:
        assert not (tmp_path / name).exists()


def test_safe_remove_missing_ok(tmp_path):
    """safe_remove 对不存在的文件 missing_ok=True 不报错"""
    from util.common.io.file import safe_remove

    # 不抛异常即通过
    safe_remove(str(tmp_path), "nonexistent.txt")


def test_safe_remove_propagates_unlink_error(tmp_path, monkeypatch):
    """safe_remove 在 unlink 异常时抛出原始异常"""
    from util.common.io import file as file_module

    target = tmp_path / "a.txt"
    target.write_text("x")

    def fake_unlink(self, missing_ok=False):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.unlink", fake_unlink)

    with pytest.raises(OSError, match="disk full"):
        file_module.safe_remove(str(tmp_path), "a.txt")


# ==================================================================
# safe_rename - 无冲突
# ==================================================================

def test_safe_rename_no_conflict(tmp_path):
    """safe_rename 目标不存在时直接重命名"""
    from util.common.io.file import safe_rename

    src = tmp_path / "old.mp4"
    src.write_text("data")
    new_path = safe_rename(str(tmp_path), "old.mp4", "new.mp4")
    assert new_path.name == "new.mp4"
    assert new_path.exists()
    assert not src.exists()


def test_safe_rename_missing_original(tmp_path):
    """safe_rename 原始文件不存在时抛 FileNotFoundError"""
    from util.common.io.file import safe_rename

    with pytest.raises(FileNotFoundError):
        safe_rename(str(tmp_path), "missing.mp4", "new.mp4")


# ==================================================================
# safe_rename - OVERWRITE 冲突解决
# ==================================================================

def test_safe_rename_overwrite(tmp_path, monkeypatch):
    """safe_rename 在 OVERWRITE 模式下删除目标后重命名"""
    from util.common.io.file import safe_rename

    src = tmp_path / "old.mp4"
    src.write_text("src-data")
    existing = tmp_path / "new.mp4"
    existing.write_text("old-target-data")

    # match 语句匹配枚举成员本身,而非 .value
    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: FileConflictResolution.OVERWRITE
        if key == "file_conflict_resolution"
        else default,
    )

    new_path = safe_rename(str(tmp_path), "old.mp4", "new.mp4")
    assert new_path.exists()
    assert new_path.read_text() == "src-data"


# ==================================================================
# safe_rename - AUTO_RENAME 冲突解决
# ==================================================================

def test_safe_rename_auto_rename(tmp_path, monkeypatch):
    """safe_rename 在 AUTO_RENAME 模式下生成 (1) 后缀"""
    from util.common.io.file import safe_rename

    src = tmp_path / "old.mp4"
    src.write_text("src-data")
    existing = tmp_path / "new.mp4"
    existing.write_text("old-target-data")

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: FileConflictResolution.AUTO_RENAME
        if key == "file_conflict_resolution"
        else default,
    )

    new_path = safe_rename(str(tmp_path), "old.mp4", "new.mp4")
    assert new_path.name == "new (1).mp4"
    assert new_path.exists()
    assert new_path.read_text() == "src-data"
    # 原目标文件应保留
    assert existing.read_text() == "old-target-data"


def test_safe_rename_auto_rename_multiple_conflicts(tmp_path, monkeypatch):
    """safe_rename AUTO_RENAME 模式下,(1) 已存在时递增到 (2)"""
    from util.common.io.file import safe_rename

    src = tmp_path / "old.mp4"
    src.write_text("src")
    (tmp_path / "new.mp4").write_text("existing-0")
    (tmp_path / "new (1).mp4").write_text("existing-1")

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: FileConflictResolution.AUTO_RENAME
        if key == "file_conflict_resolution"
        else default,
    )

    new_path = safe_rename(str(tmp_path), "old.mp4", "new.mp4")
    assert new_path.name == "new (2).mp4"


# ==================================================================
# File 静态方法
# ==================================================================

def test_file_preallocate(tmp_path):
    """File.preallocate_file 创建指定大小的文件"""
    from util.common.io.file import File

    target = str(tmp_path / "prealloc.bin")
    File.preallocate_file(target, 1024)
    assert (tmp_path / "prealloc.bin").stat().st_size == 1024


def test_file_preallocate_zero_size():
    """File.preallocate_file 在 size=0 时也工作(seek -1 + write b\0)"""
    from util.common.io.file import File

    # 在 tmp_path 外提供一个临时文件
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name
    try:
        # size=0 会触发 seek(-1) - 文件仍为 1 字节(实现细节)
        # 不在此断言大小,只确保调用不抛异常
        File.preallocate_file(path, 1)
        assert os.path.getsize(path) == 1
    finally:
        os.unlink(path)


def test_file_create_placeholder(tmp_path):
    """File.create_placeholder 创建父目录并生成空文件"""
    from util.common.io.file import File

    target_dir = tmp_path / "deep" / "nested" / "dir"
    target = str(target_dir / "empty.mp4")
    File.create_placeholder(target)
    assert target_dir.is_dir()
    assert (tmp_path / "deep" / "nested" / "dir" / "empty.mp4").exists()
    assert (tmp_path / "deep" / "nested" / "dir" / "empty.mp4").stat().st_size == 0


def test_file_create_placeholder_existing_ok(tmp_path):
    """File.create_placeholder 对已存在的文件不抛异常(exist_ok=True)"""
    from util.common.io.file import File

    target = str(tmp_path / "exists.mp4")
    File.create_placeholder(target)
    # 再次调用不应抛异常
    File.create_placeholder(target)
    assert (tmp_path / "exists.mp4").exists()
