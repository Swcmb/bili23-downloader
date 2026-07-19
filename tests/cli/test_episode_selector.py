# tests/cli/test_episode_selector.py
"""T5.8 测试 - 分集勾选交互组件

覆盖:
- parse_episode_spec 各类规范解析(all / * / 逗号 / 范围 / 混合 / last / last-N / -1)
- select_episodes 非交互模式(有 spec / 无 spec / 有 preselected / 空列表)
- select_episodes 交互模式(取消 / 选择 / 空回车使用预选 / all)

交互模式通过 monkeypatch 替换 builtins.input 模拟用户输入,
不依赖真实 TTY 与第三方 keyboard 库。
"""
import pytest

from cli.exceptions import ParseError, UserCancelledError
from cli.interact.episode_selector import parse_episode_spec, select_episodes


def _sample_episodes(n: int = 5):
    """构造 n 个示例分集,id 从 1 开始,包含 title 与 duration(秒)"""
    return [
        {"id": i, "title": f"第 {i} 集", "duration": 60 * i}
        for i in range(1, n + 1)
    ]


# ------------------------------------------------------------------
# parse_episode_spec - 集号规范解析
# ------------------------------------------------------------------

def test_parse_episode_spec_all():
    """'all' 返回所有集号"""
    assert parse_episode_spec("all", 5) == [1, 2, 3, 4, 5]


def test_parse_episode_spec_star():
    """'*' 作为 all 的别名,返回所有集号"""
    assert parse_episode_spec("*", 3) == [1, 2, 3]


def test_parse_episode_spec_comma():
    """'1,3,5' 返回离散集号 [1,3,5]"""
    assert parse_episode_spec("1,3,5", 5) == [1, 3, 5]


def test_parse_episode_spec_range():
    """'1-3' 返回连续范围 [1,2,3]"""
    assert parse_episode_spec("1-3", 5) == [1, 2, 3]


def test_parse_episode_spec_mixed():
    """'1-3,5,7-9' 返回 [1,2,3,5,7,8,9]"""
    assert parse_episode_spec("1-3,5,7-9", 10) == [1, 2, 3, 5, 7, 8, 9]


def test_parse_episode_spec_last():
    """'last' 返回最后一集 [N]"""
    assert parse_episode_spec("last", 5) == [5]


def test_parse_episode_spec_last_alias():
    """'-1' 作为 last 的别名,返回最后一集"""
    assert parse_episode_spec("-1", 5) == [5]


def test_parse_episode_spec_last_n():
    """'last-3' 返回倒数 3 集 [N-2,N-1,N]"""
    assert parse_episode_spec("last-3", 5) == [3, 4, 5]


def test_parse_episode_spec_last_one():
    """'last-1' 等价于 'last',返回最后一集"""
    assert parse_episode_spec("last-1", 5) == [5]


def test_parse_episode_spec_invalid():
    """'abc' 格式无效,抛 ParseError"""
    with pytest.raises(ParseError):
        parse_episode_spec("abc", 5)


def test_parse_episode_spec_out_of_range():
    """'1-999' 范围越界,抛 ParseError"""
    with pytest.raises(ParseError):
        parse_episode_spec("1-999", 5)


def test_parse_episode_spec_single_out_of_range():
    """单个集号 '99' 超出总集数,抛 ParseError"""
    with pytest.raises(ParseError):
        parse_episode_spec("99", 5)


def test_parse_episode_spec_reverse_range():
    """'3-1' 起始大于结束,抛 ParseError"""
    with pytest.raises(ParseError):
        parse_episode_spec("3-1", 5)


def test_parse_episode_spec_dedup():
    """重复集号自动去重"""
    assert parse_episode_spec("1,1,2,2-3", 5) == [1, 2, 3]


def test_parse_episode_spec_sorted():
    """无序输入返回升序"""
    assert parse_episode_spec("5,1,3", 5) == [1, 3, 5]


def test_parse_episode_spec_with_spaces():
    """允许片段两侧有空格"""
    assert parse_episode_spec(" 1 , 2 , 3 ", 5) == [1, 2, 3]


def test_parse_episode_spec_empty_string():
    """空字符串抛 ParseError"""
    with pytest.raises(ParseError):
        parse_episode_spec("", 5)


def test_parse_episode_spec_zero_total():
    """total=0 时 'all' 返回空列表(无可用分集)"""
    assert parse_episode_spec("all", 0) == []


# ------------------------------------------------------------------
# select_episodes - 非交互模式
# ------------------------------------------------------------------

def test_select_non_interactive_with_spec():
    """non-interactive + spec='1-3' 返回 [1,2,3]"""
    eps = _sample_episodes(5)
    result = select_episodes(eps, interactive=False, episode_spec="1-3")
    assert result == [1, 2, 3]


def test_select_non_interactive_no_spec():
    """non-interactive + 无 spec 返回全部集号"""
    eps = _sample_episodes(5)
    result = select_episodes(eps, interactive=False)
    assert result == [1, 2, 3, 4, 5]


def test_select_non_interactive_with_preselected():
    """non-interactive + preselected 返回预选集号(升序)"""
    eps = _sample_episodes(5)
    result = select_episodes(eps, preselected={4, 2}, interactive=False)
    assert result == [2, 4]


def test_select_non_interactive_preselected_filtered():
    """preselected 中不在分集列表内的集号会被过滤"""
    eps = _sample_episodes(5)
    result = select_episodes(eps, preselected={2, 99}, interactive=False)
    assert result == [2]


def test_select_non_interactive_spec_all():
    """non-interactive + spec='all' 全选"""
    eps = _sample_episodes(3)
    result = select_episodes(eps, interactive=False, episode_spec="all")
    assert result == [1, 2, 3]


def test_select_non_interactive_spec_last():
    """non-interactive + spec='last' 返回最后一集"""
    eps = _sample_episodes(5)
    result = select_episodes(eps, interactive=False, episode_spec="last")
    assert result == [5]


def test_select_non_interactive_spec_invalid():
    """non-interactive + spec 非法时抛 ParseError"""
    eps = _sample_episodes(5)
    with pytest.raises(ParseError):
        select_episodes(eps, interactive=False, episode_spec="abc")


def test_select_empty_episodes():
    """空分集列表始终返回空列表"""
    assert select_episodes([], interactive=False) == []
    assert select_episodes([], interactive=True) == []


def test_select_accepts_number_field():
    """兼容分集 dict 使用 'number' 字段(实际 ParseWorker 输出)"""
    eps = [{"number": i, "title": f"ep{i}", "duration": 10} for i in range(1, 4)]
    result = select_episodes(eps, interactive=False, episode_spec="1-2")
    assert result == [1, 2]


# ------------------------------------------------------------------
# select_episodes - 交互模式(通过 monkeypatch.input 模拟)
# ------------------------------------------------------------------

def test_select_interactive_cancel(monkeypatch):
    """模拟用户输入 'q',抛 UserCancelledError"""
    eps = _sample_episodes(5)
    monkeypatch.setattr("builtins.input", lambda _: "q")
    with pytest.raises(UserCancelledError):
        select_episodes(eps, interactive=True)


def test_select_interactive_select(monkeypatch):
    """模拟用户输入 '1-3,5',返回 [1,2,3,5]"""
    eps = _sample_episodes(5)
    monkeypatch.setattr("builtins.input", lambda _: "1-3,5")
    result = select_episodes(eps, interactive=True)
    assert result == [1, 2, 3, 5]


def test_select_interactive_default_enter(monkeypatch):
    """模拟空回车,使用 preselected"""
    eps = _sample_episodes(5)
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = select_episodes(eps, preselected={2, 3}, interactive=True)
    assert result == [2, 3]


def test_select_interactive_empty_no_preselected(monkeypatch):
    """空回车且无 preselected 时,默认全选(便于快速确认)"""
    eps = _sample_episodes(3)
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = select_episodes(eps, interactive=True)
    assert result == [1, 2, 3]


def test_select_interactive_all(monkeypatch):
    """模拟输入 'all',全选"""
    eps = _sample_episodes(3)
    monkeypatch.setattr("builtins.input", lambda _: "all")
    result = select_episodes(eps, interactive=True)
    assert result == [1, 2, 3]


def test_select_interactive_last(monkeypatch):
    """模拟输入 'last',返回最后一集"""
    eps = _sample_episodes(5)
    monkeypatch.setattr("builtins.input", lambda _: "last")
    result = select_episodes(eps, interactive=True)
    assert result == [5]


def test_select_interactive_eof(monkeypatch):
    """input 抛 EOFError 时转 UserCancelledError(无可用输入)"""
    eps = _sample_episodes(5)

    def _raise_eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    with pytest.raises(UserCancelledError):
        select_episodes(eps, interactive=True)


def test_select_interactive_invalid_spec(monkeypatch):
    """交互模式下输入非法 spec,抛 ParseError"""
    eps = _sample_episodes(5)
    monkeypatch.setattr("builtins.input", lambda _: "abc")
    with pytest.raises(ParseError):
        select_episodes(eps, interactive=True)


def test_select_interactive_shows_preselected_count(monkeypatch):
    """有 preselected 时,prompt 文本中包含预选数量"""
    eps = _sample_episodes(5)
    captured = {}

    def _capture(prompt):
        captured["prompt"] = prompt
        return "q"

    monkeypatch.setattr("builtins.input", _capture)
    with pytest.raises(UserCancelledError):
        select_episodes(eps, preselected={1, 2, 3}, interactive=True)
    # prompt 应包含预选数量提示
    assert "3" in captured["prompt"]
