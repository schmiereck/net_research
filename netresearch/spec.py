"""Unified interface constants shared by all tasks and models."""
from dataclasses import dataclass, field

H = W = 16          # raster size
C = 3               # binary RGB channels
OBS_SHAPE = (C, H, W)
OBS_DIM = C * H * W
N_OUT = 64          # every model emits 64 logits

# The 64 outputs are split into fixed areas by function; a task always uses the area of its role, so an
# output unit has the same meaning in every task (important when one model learns several tasks).
#   motor    0..7   game actions (slot = action id)
#   classify 8..17  class of the current image (shapes, digits)
#   bits     18..25 predicted next bits (bit streams, next row of cycle / count / numseq)
#   symbol   26..63 predicted next symbol (next character)
OUT_AREAS = {"motor": (0, 8), "classify": (8, 18), "bits": (18, 26), "symbol": (26, 64)}

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
    role: str = ""             # output area (OUT_AREAS); default derived from kind/head
    parts: dict = field(default_factory=dict)   # bits head: name -> (lo, hi) of the target bits; the
    #                                             evaluation reports the exact-match share of each part

    def __post_init__(self):
        if not self.role:
            self.role = "motor" if self.kind == "control" else "bits" if self.head == "bits" else "classify"
        lo, hi = OUT_AREAS[self.role]
        assert self.n_out <= hi - lo, (self.name, self.n_out, self.role)
        self.out_offset = lo

    @property
    def out_slice(self):
        return slice(self.out_offset, self.out_offset + self.n_out)
