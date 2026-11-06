"""Unified interface constants shared by all tasks and models."""
from dataclasses import dataclass, field

H = W = 16          # raster size
C = 3               # binary RGB channels
OBS_SHAPE = (C, H, W)
OBS_DIM = C * H * W
N_OUT = 64          # every model emits 64 logits

# fixed action slots for games
NOOP, LEFT, RIGHT, UP, DOWN, FIRE, JUMP, RESERVED = range(8)
ACTION_NAMES = ["noop", "left", "right", "up", "down", "fire", "jump", "reserved"]

# colors (binary RGB)
BLACK = (0, 0, 0)
RED = (1, 0, 0)
GREEN = (0, 1, 0)
BLUE = (0, 0, 1)
YELLOW = (1, 1, 0)
CYAN = (0, 1, 1)
MAGENTA = (1, 0, 1)
WHITE = (1, 1, 1)
COLORS = [RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA, WHITE]


@dataclass
class TaskSpec:
    name: str
    group: str                 # patterns | image | text | game
    kind: str                  # supervised | control
    head: str                  # class | bits
    n_out: int                 # number of used output slots
    seq_len: int = 1           # training sequence length (supervised) / chunk len (control)
    chance: float = 0.0        # chance-level metric for normalisation (supervised)
    valid_actions: list = field(default_factory=list)  # control: allowed action slots
    needs_memory: bool = False
    description: str = ""
