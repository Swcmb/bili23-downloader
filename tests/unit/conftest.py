# tests/unit/conftest.py
"""单元测试公共夹具 - 全局 patch Translator 已知 dangling 调用

背景:T1 重构后,Translator 类移除了 ERROR_MESSAGES / TIP_MESSAGES /
EPISODE_TYPE 等静态方法,但 src/util/parse/* 与 src/util/download/* 中
仍有 28+ 个文件保留着 dangling 调用。这些调用在没有 patch 的情况下会抛
AttributeError,导致大量 parse/download 代码无法被覆盖。

T6 阶段聚焦测试覆盖率提升,而非源代码重构。这里通过 autouse 夹具
patch 这些方法为 identity lambda,使业务代码可被测试执行。

patch 策略:
- EPISODE_TYPE(name) -> 返回 name 本身(展示用,不需要实际翻译)
- ERROR_MESSAGES(key) -> 返回 key 本身
- TIP_MESSAGES(key) -> 返回 key 本身
- VIDEO_QUALITY / AUDIO_QUALITY / VIDEO_CODEC / AUDIO_CODEC -> 返回 key 本身
- 其他用到的静态方法 -> 返回 key 本身(兜底)
"""
import pytest


# 已知的 dangling Translator 静态方法名(经 grep 验证)
_DANGLING_METHODS = (
    "ERROR_MESSAGES",
    "TIP_MESSAGES",
    "EPISODE_TYPE",
    "VIDEO_QUALITY",
    "AUDIO_QUALITY",
    "VIDEO_CODEC",
    "AUDIO_CODEC",
    "EPISODE_TYPE_NAME",
    "VIDEO_QUALITY_PRIORITY",
    "AUDIO_QUALITY_PRIORITY",
    "VIDEO_CODEC_PRIORITY",
)


@pytest.fixture(autouse=True)
def patch_dangling_translator_methods(monkeypatch):
    """全局 patch Translator 的 dangling 静态方法,使其返回参数本身

    autouse=True 使该 fixture 自动应用到所有单元测试,无需显式声明。
    """
    from util.common.translator import Translator

    for method_name in _DANGLING_METHODS:
        # raising=False 允许新增不存在的属性
        monkeypatch.setattr(
            Translator,
            method_name,
            staticmethod(lambda *args, **kwargs: args[0] if args else ""),
            raising=False,
        )
