"""Crossing: move a figure from the bottom over lanes of moving traffic to the top."""

import numpy as np

from ...spec import DOWN, GREEN, LEFT, NOOP, RED, RIGHT, UP, YELLOW
from ..base import Game
from .common import canvas, put

LANES = (13, 12, 11, 10, 9, 7, 6, 5, 4, 3)    # road rows; row 8 is a safe median
GOAL_Y = 2                                       # reaching y <= 2 counts as a crossing
START = (8, 15)
MOVES = {NOOP: (0, 0), LEFT: (-1, 0), RIGHT: (1, 0), UP: (0, -1), DOWN: (0, 1)}


class Crossing(Game):
    max_steps = 300
    actions = [NOOP, LEFT, RIGHT, UP, DOWN]

    def reset(self):
        self.lanes = {}
        for i, y in enumerate(LANES):
            base = np.zeros(16, dtype=bool)
            x = int(self.rng.integers(0, 4))
            while x < 16:
                ln = int(self.rng.integers(2, 4))
                base[x:x + ln] = True
                x += ln + int(self.rng.integers(3, 7))
            direction = 1 if i % 2 == 0 else -1
            period = int(self.rng.integers(1, 3))
            self.lanes[y] = (base, direction, period)
        self.t = 0
        self.x, self.y = START

    def occupied(self, y, t):
        if y not in self.lanes:
            return np.zeros(16, dtype=bool)
        base, d, p = self.lanes[y]
        return np.roll(base, d * (t // p))

    def _hit(self, x, y, t):
        return y in self.lanes and self.occupied(y, t)[x]

    def step(self, action):
        dx, dy = MOVES.get(action, (0, 0))
        self.x = min(max(self.x + dx, 0), 15)
        self.y = min(max(self.y + dy, 0), 15)
        if self._hit(self.x, self.y, self.t):
            return -1.0, True
        self.t += 1
        if self._hit(self.x, self.y, self.t):
            return -1.0, True
        if self.y <= GOAL_Y:
            self.x, self.y = START
            return 1.0, False
        return 0.0, False

    def render(self):
        img = canvas()
        for y in range(0, GOAL_Y + 1):
            img[:, y, :] = np.array(GREEN, dtype=np.float32)[:, None]
        for y in LANES:
            occ = self.occupied(y, self.t)
            img[:, y, occ] = np.array(RED, dtype=np.float32)[:, None]
        put(img, self.x, self.y, YELLOW)
        return img

    def expert(self, horizon=14):
        """Vectorised BFS over (x, y, dt) with exact traffic simulation.

        Maximises progress (smallest y) within the horizon, then minimises time.
        `first[y, x]` holds the first action of a safe path reaching (x, y), -1 if unreachable.
        """
        occ = np.zeros((horizon + 2, 16, 16), dtype=bool)
        for y in LANES:
            base, d, p = self.lanes[y]
            for k in range(horizon + 2):
                occ[k, y] = np.roll(base, d * ((self.t + k) // p))
        first = np.full((16, 16), -1, dtype=int)
        best_y, best_a = self.y, None
        survive_a = NOOP      # first action of the longest-surviving path (fallback)
        for k in range(horizon):
            safe = ~(occ[k] | occ[k + 1])
            new = np.full((16, 16), -1, dtype=int)
            for a in (UP, NOOP, LEFT, RIGHT, DOWN):
                if k == 0:
                    src = np.full((16, 16), -1, dtype=int)
                    src[self.y, self.x] = a
                else:
                    src = first
                dx, dy = MOVES[a]
                sh = np.full((16, 16), -1, dtype=int)
                ys, yd = (slice(max(0, -dy), 16 - max(0, dy)), slice(max(0, dy), 16 - max(0, -dy)))
                xs, xd = (slice(max(0, -dx), 16 - max(0, dx)), slice(max(0, dx), 16 - max(0, -dx)))
                sh[yd, xd] = src[ys, xs]
                upd = (new < 0) & (sh >= 0) & safe
                new[upd] = sh[upd]
            first = new
            rows = np.flatnonzero((first >= 0).any(axis=1))
            if len(rows) == 0:
                break
            alive = first[first >= 0]
            survive_a = NOOP if (alive == NOOP).any() else int(alive[0])
            if rows[0] < best_y:
                best_y = rows[0]
                best_a = int(first[best_y][first[best_y] >= 0][0])
                if best_y <= GOAL_Y:
                    break
        return survive_a if best_a is None else best_a

