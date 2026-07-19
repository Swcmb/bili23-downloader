# src/util/common/translator.py
"""翻译器 - 纯 Python dict,替代 QTranslator + .qm 文件

设计要点:
- 从 src/res/i18n/*.ts 解析 <source>/<translation> 对,运行时用 dict 查找
- tr(key, **kwargs) 支持 {placeholder} 插值(Python format 语法)
- 不存在的键返回键本身,避免空字符串导致 UI 显示空白

注意:原 Translator 类的静态方法(VIDEO_QUALITY/AUDIO_QUALITY 等)已移除,
调用方应改为 translator.tr("source text") 风格(待 Task 2 全量替换)。
"""
import os
import logging
import xml.etree.ElementTree as ET
from typing import Dict

logger = logging.getLogger(__name__)


class Translator:
    """翻译器,从内存 dict 查找键值

    初始化时尝试加载默认语言(zh_CN)的 .ts 文件。若文件不存在或解析
    失败,则使用空 dict,tr() 退化为返回键本身(英语直显)。
    """

    def __init__(self):
        self._dict: Dict[str, str] = {}
        self._load_default()

    def _load_default(self) -> None:
        """加载默认语言(zh_CN)翻译

        路径计算:src/util/common/translator.py → src/res/i18n/bili23.zh_CN.ts
        即从当前文件向上 2 层到 src/,再进入 res/i18n/。
        """
        ts_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "res", "i18n", "bili23.zh_CN.ts"
        )
        ts_path = os.path.normpath(ts_path)
        if os.path.exists(ts_path):
            self._load_from_ts(ts_path)

    def _load_from_ts(self, ts_path: str) -> None:
        """从 Qt .ts XML 文件解析翻译

        .ts 结构:<context><message><source>原文</source><translation>译文</translation></message></context>
        解析后以 source 为键、translation 为值存入 _dict。
        """
        try:
            tree = ET.parse(ts_path)
            root = tree.getroot()
            for msg in root.iter("message"):
                source = msg.find("source")
                translation = msg.find("translation")
                # 仅当 source 和 translation 都有非空文本时才收录
                if source is not None and translation is not None and translation.text:
                    self._dict[source.text] = translation.text
        except (ET.ParseError, OSError) as e:
            # 静默失败,后续以 key 兜底;记录 warning 便于排查
            logger.warning("加载翻译文件 %s 失败: %s", ts_path, e)

    def tr(self, key: str, **kwargs) -> str:
        """翻译键,支持 {placeholder} 插值

        查不到翻译时返回 key 本身;若插值失败(占位符不匹配)返回未插值的原文。
        """
        text = self._dict.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                # 占位符不匹配时返回原文,避免抛异常中断调用方
                return text
        return text


# 模块级单例,保持与原代码 `from util.common.translator import translator` 兼容
translator = Translator()
