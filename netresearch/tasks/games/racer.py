"""Racer: drive along a scrolling road and dodge obstacles."""
import numpy as np

from ...spec import GREEN, LEFT, NOOP, RED, RIGHT, YELLOW
from ..base import Game
from .common import canvas

CAR_Y = (14, 15)     # car occupies two rows
XMIN, XMAX = 1, 14   # road; columns 0 and 15 are grass


class Racer(Game):
    max_steps = 300
    actions = [NOOP, LEFT, RIGHT]

    def reset(self):
        self.obst = np.zeros((16, 16), dtype=bool)
        self.x = 7
        self.gap = 0

    def _spawn(self):
        row = np.zeros(16, dtype=bool)
        self.gap -= 1
        if self.gap <= 0:
            w = int(self.rng.integers(2, 5))
            x = int(self.rng.integers(XMIN, XMAX - w + 2))
            row[x:x + w] = True
            self.gap = int(self.rng.integers(2, 4))
        return row

    def _crash(self, obst, x):
        return obst[CAR_Y[0], x] or obst[CAR_Y[1], x]

    def step(self, action):
        if action == LEFT:
            self.x = max(XMIN, self.x - 1)
        elif action == RIGHT:
            self.x = min(XMAX, self.x + 1)
        if self._crash(self.obst, self.x):
            return 0.0, True
        self.obst[1:] = self.obst[:-1].copy()
        self.obst[0] = self._spawn()
        if self._crash(self.obst, self.x):
            return 0.0, True
        return 1.0, False

    def render(self):
        img = canvas()
        img[:, :, 0] = np.array(GREEN, dtype=np.float32)[:, None]
        img[:, :, 15] = np.array(GREEN, dtype=np.float32)[:, None]
        img[:, self.obst] = np.array(RED, dtype=np.float32)[:, None]
        for y in CAR_Y:
            img[:, y, self.x] = YELLOW
        return img

    def expert(self, horizon=13):
        """Search over lane changes with the currently visible obstacles (future spawns unknown)."""
        best_a, best_score = NOOP, -1
        for a in (NOOP, LEFT, RIGHT):
            score = self._survive(a, horizon)
            score = score * 10 - abs((self.x + {NOOP: 0, LEFT: -1, RIGHT: 1}[a]) - 7.5) * 0.1
            if score > best_score:
                best_a, best_score = a, score
        return best_a

    def _survive(self, first, horizon):
        """Max number of steps survivable when starting with action `first` (DP over x)."""
        def shifted(k):
            o = np.zeros_like(self.obst)
            o[k:] = self.obst[:16 - k]
            return o
        x0 = min(max(self.x + {NOOP: 0, LEFT: -1, RIGHT: 1}[first], XMIN), XMAX)
        if self._crash(shifted(0), x0) or self._crash(shifted(1), x0):
            return 0
        alive = {x0}
        for k in range(1, horizon):
            nxt = set()
            o_now, o_next = shifted(k), shifted(k + 1)
            for x in alive:
                for d in (-1, 0, 1):
                    nx = min(max(x + d, XMIN), XMAX)
                    if not self._crash(o_now, nx) and not self._crash(o_next, nx):
                        nxt.add(nx)
            if not nxt:
                return k
            alive = nxt
        return horizon
