from ..spec import TaskSpec
from .base import ControlTask
from .games.bricks import Bricks, BricksMem
from .games.crossing import Crossing
from .games.maze import Maze
from .games.paddle import Paddle, PaddleMem
from .games.racer import Racer
from .images import Digits, Shapes
from .memory import CrossMem, Delay, Recall
from .patterns import BitSeq, Count, Cycle, CycleMem, NumSeq
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
    "bitseq": BitSeq,
    "cycle_mem": CycleMem,
    "count": Count,
    "numseq": NumSeq,
    "shapes": Shapes,
    "digits": Digits,
    "charnext": CharNext,
    "recall": Recall,
    "delay": Delay,
    "crossmem": CrossMem,
    "paddle": _game_task("paddle", Paddle, "paddle duel vs CPU, first to 5 points"),
    "paddle_mem": _game_task("paddle_mem", PaddleMem, "paddle duel without ball trail (needs memory)", True),
    "bricks": _game_task("bricks", Bricks, "clear 64 bricks, 3 lives"),
    "bricks_mem": _game_task("bricks_mem", BricksMem, "bricks without ball trail (needs memory)", True),
    "crossing": _game_task("crossing", Crossing, "cross 10 traffic lanes, +1 per crossing"),
    "racer": _game_task("racer", Racer, "dodge obstacles, +1 per step survived"),
    "maze": _game_task("maze", Maze, "collect pellets, avoid 2 chasers"),
}

_cache = {}


def make_task(name):
    if name not in _cache:
        _cache[name] = TASKS[name]()
    return _cache[name]
