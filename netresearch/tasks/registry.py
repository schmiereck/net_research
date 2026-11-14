from ..spec import TaskSpec
from .base import ControlTask
from .games.bricks import Bricks, BricksMem
from .games.crossing import Crossing
from .games.gridworld import (GridFollow, GridFollowEasy, GridScroll, GridScrollEasy, GridWorld,
                              GridWorldEasy, GridSmall, GridSmallEgo, Push, PushEasy)
from .games.maze import Maze
from .games.paddle import Paddle, PaddleMem
from .games.racer import Racer
from .images import Digits, Shapes
from .memory import (CrossMem, Delay, KeepFixed, KeepShift, Match, MatchShift, ReadShift, Recall, SameFixed,
                     SameShift)
from .patterns import BitSeq, Count, Cycle, CycleMem, NumSeq
from .robot import (RobotFind, RobotFindColor, RobotFindImage, RobotFindShape, RobotFindShapeF32,
                    RobotFindShapeParts, RobotFindShapePartsF32, RobotGaze, RobotShapeAt, RobotShapeAtF32, IN_TASKS,
                    RobotLook, RobotLookMem, RobotReach, RobotReachBig, RobotReachParts,
                    RobotReachPartsBig, RobotShape, RobotShapeEdge, RobotShapeEdgeBig,
                    RobotShapeEdgeF32, RobotShapeEdgeF32Big, RobotShapeF32, RobotShapeZ2, RobotShapeZ4)
from .servo import Servo, pop_variant
from .text import CharNext


def _game_task(name, cls, desc, memory=False, seq_len=16):
    class _T(ControlTask):
        game_cls = cls

        def __init__(self):
            self.spec = TaskSpec(name, "game", "control", "class", 8, seq_len=seq_len,
                                 valid_actions=list(cls.actions), needs_memory=memory, description=desc)
    _T.__name__ = cls.__name__ + "Task"
    return _T


# Step tasks with the step as a population code instead of 8 bits ("_pop": Gaussian bumps, width one cell;
# "_hot": one unit per value, no neighbourhood). Same images and steps as the base task.
POP_TASKS = {f"{n}_{tag}": pop_variant(c, f"{n}_{tag}", sigma)
             for n, c in (("servo", Servo), ("robot_findc", RobotFindColor),
                          ("robot_finds_in_f32", IN_TASKS["robot_finds_in_f32"]),
                          ("robot_finds_c_f32", IN_TASKS["robot_finds_c_f32"]))
             for tag, sigma in (("pop", 1.0), ("hot", 0.0), ("p05", 0.5))}

TASKS = {
    "cycle": Cycle,
    "bitseq": BitSeq,
    "cycle_mem": CycleMem,
    "count": Count,
    "numseq": NumSeq,
    "servo": Servo,
    "robot_gaze": RobotGaze,
    "robot_reach": RobotReach,
    "robot_find": RobotFind,
    "robot_findc": RobotFindColor,
    "robot_findi": RobotFindImage,
    "robot_finds": RobotFindShape,
    "robot_finds_parts": RobotFindShapeParts,
    "robot_finds_f32": RobotFindShapeF32,
    "robot_finds_parts_f32": RobotFindShapePartsF32,
    "robot_shape_at": RobotShapeAt,
    "robot_shape_at_f32": RobotShapeAtF32,
    **IN_TASKS,
    **POP_TASKS,
    "robot_reach_parts": RobotReachParts,
    "robot_reach_big": RobotReachBig,
    "robot_reach_parts_big": RobotReachPartsBig,
    "robot_shape": RobotShape,
    "robot_shape_z2": RobotShapeZ2,
    "robot_shape_z4": RobotShapeZ4,
    "robot_shape_f32": RobotShapeF32,
    "robot_shape_edge": RobotShapeEdge,
    "robot_shape_edge_f32": RobotShapeEdgeF32,
    "robot_shape_edge_big": RobotShapeEdgeBig,
    "robot_shape_edge_f32_big": RobotShapeEdgeF32Big,
    "robot_look": RobotLook,
    "robot_lookmem": RobotLookMem,
    "shapes": Shapes,
    "digits": Digits,
    "charnext": CharNext,
    "recall": Recall,
    "delay": Delay,
    "match": Match,
    "match_shift": MatchShift,
    "read_shift": ReadShift,
    "keep_shift": KeepShift,
    "keep_fixed": KeepFixed,
    "same_shift": SameShift,
    "same_fixed": SameFixed,
    "crossmem": CrossMem,
    "paddle": _game_task("paddle", Paddle, "paddle duel vs CPU, first to 5 points"),
    "paddle_mem": _game_task("paddle_mem", PaddleMem, "paddle duel without ball trail (needs memory)", True),
    "bricks": _game_task("bricks", Bricks, "clear 64 bricks, 3 lives"),
    "bricks_mem": _game_task("bricks_mem", BricksMem, "bricks without ball trail (needs memory)", True),
    "crossing": _game_task("crossing", Crossing, "cross 10 traffic lanes, +1 per crossing"),
    "racer": _game_task("racer", Racer, "dodge obstacles, +1 per step survived"),
    "maze": _game_task("maze", Maze, "collect pellets, avoid 2 chasers"),
    "grid": _game_task("grid", GridWorld, "grid world 16x16, fully visible: reach the goal, avoid pits"),
    "grid_follow": _game_task("grid_follow", GridFollow, "grid world 32x32, view centred on the player, "
                              "goal out of sight; expert explores with what it has seen", True, seq_len=32),
    "grid_scroll": _game_task("grid_scroll", GridScroll, "like grid_follow, camera with dead zone", True,
                              seq_len=32),
    "push": _game_task("push", Push, "push a box onto the target (16x16, fully visible)"),
    "grid_small": _game_task("grid_small", GridSmall, "grid world 8x8, fixed view (player moves in the image)"),
    "grid_small_ego": _game_task("grid_small_ego", GridSmallEgo, "grid world 8x8, view centred on the player"),
    "grid_easy": _game_task("grid_easy", GridWorldEasy, "grid world 16x16, few walls"),
    "grid_follow_easy": _game_task("grid_follow_easy", GridFollowEasy, "grid_follow with few walls", True,
                                   seq_len=32),
    "grid_scroll_easy": _game_task("grid_scroll_easy", GridScrollEasy, "grid_scroll with few walls", True,
                                   seq_len=32),
    "push_easy": _game_task("push_easy", PushEasy, "push a box onto a near target in an open room"),
}

_cache = {}


def make_task(name):
    if name not in _cache:
        _cache[name] = TASKS[name]()
    return _cache[name]
