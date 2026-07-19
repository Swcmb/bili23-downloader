# src/cli/render/progress.py
"""进度条渲染器

基于 rich.progress.Progress 封装,提供 start/stop/add_task/update 生命周期
方法。task_id 用字符串表示,内部维护 str -> rich task_id 的映射,避免
调用方接触 rich 内部 TaskID 对象。
"""
from typing import Optional

from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)


class ProgressRender:
    """进度条渲染器:封装 rich.progress.Progress 的生命周期管理

    内部用 dict 维护"逻辑任务名 -> rich TaskID"映射,
    外部调用方只需提供字符串任务名即可。
    """

    def __init__(self):
        # 列定义:描述 + 进度条 + 百分比 + 剩余时间
        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        )
        # 逻辑任务名 -> rich TaskID
        self._tasks: dict[str, object] = {}

    def start(self) -> None:
        """启动进度条渲染(开始接收终端输出)"""
        self._progress.start()

    def stop(self) -> None:
        """停止进度条渲染(关闭并清理终端状态)"""
        self._progress.stop()

    def add_task(self, name: str, total: Optional[float] = None) -> None:
        """添加新任务,登记逻辑名到 rich TaskID 的映射

        :param name:  逻辑任务名(外部调用方使用)
        :param total: 任务总量,None 表示不确定进度
        """
        task_id = self._progress.add_task(name, total=total)
        self._tasks[name] = task_id

    def update(self, name: str, advance: Optional[float] = None) -> None:
        """更新指定任务的进度

        :param name:    逻辑任务名
        :param advance: 本次推进的增量,None 则不推进进度
        """
        if name not in self._tasks:
            return
        self._progress.update(self._tasks[name], advance=advance)
