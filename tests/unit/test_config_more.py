# tests/unit/test_config_more.py
"""Config 补充测试 - 覆盖 load / save / reload / 范围校验边界

补充 tests/unit/test_config.py 未覆盖的分支:
- Config() 无 config_path 参数时,使用 platformdirs 默认路径
- Config.load 在文件不存在时直接 return
- Config.load 在根节点非 dict 时备份并重置
- Config.load 在 OSError 时备份并重置
- Config.save 显式保存
- Config.reload 重置为默认值后重新加载
- Config.set 在 bool 值(非 int)通过校验时的边界行为
- _DEFAULT_VALUES 深拷贝隔离(单例间不共享可变对象)
"""
import json
import os
import threading
import pytest


def test_config_default_path_uses_platformdirs(monkeypatch, tmp_path):
    """Config() 无参数时使用 platformdirs 默认路径"""
    from util.common.config import Config

    # 重定向到 tmp_path 避免污染真实配置目录
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    cfg = Config()
    # 路径应以 config.json 结尾
    assert cfg._path.endswith("config.json")
    # config_dir 应已由 __init__ 中 makedirs 创建
    assert os.path.isdir(os.path.dirname(cfg._path))
    # 调用 set 后文件才会实际创建
    cfg.set("video_quality_id", 80)
    assert os.path.exists(cfg._path)


def test_load_silent_when_file_missing(tmp_path):
    """load() 在文件不存在时直接 return,不抛异常"""
    from util.common.config import Config

    path = str(tmp_path / "absent.json")
    cfg = Config(config_path=path)
    # 文件不存在,load 直接返回;但 set 后会创建
    assert not os.path.exists(path)
    cfg.set("video_quality_id", 80)
    assert os.path.exists(path)


def test_load_resets_when_root_not_dict(tmp_path):
    """load() 在 JSON 根节点非 dict 时备份并重置"""
    from util.common.config import Config

    path = str(tmp_path / "config.json")
    # 写入一个 list 而非 dict
    with open(path, "w") as f:
        json.dump([1, 2, 3], f)

    cfg = Config(config_path=path)
    # 应有 .bak 备份
    assert os.path.exists(path + ".bak")
    # 内部状态应保持默认值
    assert cfg.get("download_threads") == 8


def test_load_backup_failure_continues_silently(tmp_path, monkeypatch):
    """load() 在备份失败时记录 error 但不抛异常"""
    from util.common import config as config_module

    path = str(tmp_path / "config.json")
    with open(path, "w") as f:
        f.write("{invalid json")

    # 让 os.replace 抛 OSError
    real_replace = os.replace
    call_count = {"n": 0}

    def failing_replace(src, dst):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OSError("simulated backup failure")
        return real_replace(src, dst)

    monkeypatch.setattr(config_module.os, "replace", failing_replace)

    # 不抛异常
    cfg = config_module.Config(config_path=path)
    # 默认值可用
    assert cfg.get("download_threads") == 8


def test_save_explicit(tmp_path):
    """save() 显式保存到文件"""
    from util.common.config import Config

    path = str(tmp_path / "config.json")
    cfg = Config(config_path=path)
    cfg.set("video_quality_id", 80)

    # 删除文件后 save
    os.unlink(path)
    cfg.save()
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert data["video_quality_id"] == 80


def test_reload_resets_to_defaults(tmp_path):
    """reload() 重置为默认值后重新加载文件"""
    from util.common.config import Config

    path = str(tmp_path / "config.json")
    cfg = Config(config_path=path)
    cfg.set("video_quality_id", 100)

    cfg.reload()
    # reload 后 video_quality_id 应回到默认值 80(因文件中已是 100,reload 会重新加载)
    # 注意:reload() 会先重置 _data 为 _DEFAULT_VALUES,再 load() 合并文件内容
    # 文件中保存的是 100,所以 reload 后还是 100
    assert cfg.get("video_quality_id") == 100


def test_reload_to_clean_state(tmp_path):
    """删除配置文件后 reload 应恢复到默认值"""
    from util.common.config import Config

    path = str(tmp_path / "config.json")
    cfg = Config(config_path=path)
    cfg.set("video_quality_id", 100)
    # 删除文件
    os.unlink(path)

    cfg.reload()
    # 现在应回到默认值 80
    assert cfg.get("video_quality_id") == 80


def test_set_with_bool_value_rejected_for_int_keys(tmp_path):
    """set() 对 int 范围键拒绝 bool 值(因为 bool 是 int 子类)"""
    from util.common.config import Config, ConfigError

    cfg = Config(config_path=str(tmp_path / "c.json"))
    # bool 是 int 子类,但代码显式拒绝(isinstance(value, bool))
    with pytest.raises(ConfigError):
        cfg.set("download_threads", True)


def test_default_values_isolated_between_instances(tmp_path):
    """两个 Config 实例的 _data 不应共享可变默认对象(如 list)"""
    from util.common.config import Config

    cfg1 = Config(config_path=str(tmp_path / "c1.json"))
    cfg2 = Config(config_path=str(tmp_path / "c2.json"))

    cfg1.set("video_quality_priority", [127])
    # cfg2 的 video_quality_priority 不应受影响
    assert cfg2.get("video_quality_priority") == [127, 126, 125, 120, 116, 112, 100, 80, 64, 32, 16]


def test_set_value_persists_across_instances(tmp_path):
    """set() 持久化后,新 Config 实例能读到该值"""
    from util.common.config import Config

    path = str(tmp_path / "shared.json")
    cfg1 = Config(config_path=path)
    cfg1.set("user_agent", "test-agent/1.0")

    cfg2 = Config(config_path=path)
    assert cfg2.get("user_agent") == "test-agent/1.0"


def test_get_returns_default_for_missing_key(tmp_path):
    """get() 对不存在的键返回 None 或自定义 default"""
    from util.common.config import Config

    cfg = Config(config_path=str(tmp_path / "c.json"))
    assert cfg.get("nonexistent") is None
    assert cfg.get("nonexistent", default="fallback") == "fallback"


def test_set_int_at_boundary_passes(tmp_path):
    """set() 在范围边界值通过校验"""
    from util.common.config import Config

    cfg = Config(config_path=str(tmp_path / "c.json"))
    cfg.set("download_threads", 1)  # 最小值
    assert cfg.get("download_threads") == 1
    cfg.set("download_threads", 32)  # 最大值
    assert cfg.get("download_threads") == 32


def test_set_float_rejected_for_int_keys(tmp_path):
    """set() 对 int 范围键拒绝 float 值"""
    from util.common.config import Config, ConfigError

    cfg = Config(config_path=str(tmp_path / "c.json"))
    with pytest.raises(ConfigError):
        cfg.set("download_threads", 8.5)


def test_set_non_range_key_accepts_any_type(tmp_path):
    """set() 对无范围规则的键接受任意类型"""
    from util.common.config import Config

    cfg = Config(config_path=str(tmp_path / "c.json"))
    cfg.set("custom_str", "hello")
    cfg.set("custom_list", [1, 2, 3])
    cfg.set("custom_dict", {"a": 1})
    cfg.set("custom_bool", True)
    cfg.set("custom_none", None)

    assert cfg.get("custom_str") == "hello"
    assert cfg.get("custom_list") == [1, 2, 3]
    assert cfg.get("custom_dict") == {"a": 1}
    assert cfg.get("custom_bool") is True
    assert cfg.get("custom_none") is None
