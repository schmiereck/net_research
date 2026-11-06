from ..spec import TaskSpec
from .base import ControlTask
from .games.bricks import Bricks
from .games.crossing import Crossing
from .games.maze import Maze
from .games.paddle import Paddle
from .games.racer import Racer
from .images import Digits, Shapes
from .patterns import Count, Cycle, CycleMem
from .text import CharNext


def _game_task(name, cls, desc, memory=False):
    class _T(ControlTask):
        game_cls = cls

        def __init__(self):
            self.spec = TaskSpec(name, "game", "control", "class", 8, seq_len=16,
                                 valid_actions=list(cls.actions), needs_memory=memory, description=desc)
    _T.__name__ = cls.__name__ + "Task"
    return _T


TASKS = {
    "cycle": Cycle,
    "cycle_mem": CycleMem,
    "count": Count,
    "shapes": Shapes,
    "digits": Digits,
    "charnext": CharNext,
    "paddle": _game_task("paddle", Paddle, "paddle duel vs CPU, first to 5 points"),
    "bricks": _game_task("bricks", Bricks, "clear 64 bricks, 3 lives"),
    "crossing": _game_task("crossing", Crossing, "cross 10 traffic lanes, +1 per crossing"),
    "racer": _game_task("racer", Racer, "dodge obstacles, +1 per step survived"),
    "maze": _game_task("maze", Maze, "collect pellets, avoid 2 chasers"),
}

_cache = {}


def make_task(name):
    if name not in _cache:
        _cache[name] = TASKS[name]()
    return _cache[name]
