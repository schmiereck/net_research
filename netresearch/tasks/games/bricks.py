"""Bricks: clear a wall of bricks with a ball bounced off a paddle."""
import numpy as np

from ...spec import BLUE, CYAN, GREEN, LEFT, MAGENTA, NOOP, RED, RIGHT, WHITE, YELLOW
from ..base import Game
from .common import canvas, put

PW = 3                      # paddle width
ROWS = (1, 2, 3, 4)         # brick rows
ROW_COLORS = (RED, YELLOW, GREEN, CYAN)
LIVES = 3


class Bricks(Game):
    max_steps = 600
    actions = [NOOP, LEFT, RIGHT]
    trail = True

    def reset(self):
        self.bricks = np.zeros((16, 16), dtype=bool)
        for r in ROWS:
            self.bricks[r, :] = True
        self.px = 6
        self.lives = LIVES
        self._serve()

    def _serve(self):
        self.bx, self.by = int(self.rng.integers(2, 14)), 10
        self.dx, self.dy = int(self.rng.choice([-1, 1])), 1
        self.prev = (self.bx - self.dx, self.by - self.dy)

    def _move(self, bx, by, dx, dy, bricks=None):
        """Advance ball one step. Returns (bx, by, dx, dy, hit_brick_xy or None, fell)."""
        hit = None
        nx = bx + dx
        if nx < 0 or nx > 15:
            dx = -dx
            nx = bx + dx
        ny = by + dy
        if ny < 0:
            dy = -dy
            ny = by + dy
        if bricks is not None and 0 <= ny < 16 and bricks[ny, nx]:
            hit = (nx, ny)
            dy = -dy
            return bx, by, dx, dy, hit, False
        if ny == 15 and dy > 0:
            if self.px <= nx < self.px + PW:
                off = nx - self.px
                dx = -1 if off < PW // 2 else 1
                dy = -1
                return nx, 14, dx, dy, None, False
            return nx, ny, dx, dy, None, True
        return nx, ny, dx, dy, None, False

    def step(self, action):
        if action == LEFT:
            self.px = max(0, self.px - 1)
        elif action == RIGHT:
            self.px = min(16 - PW, self.px + 1)
        self.prev = (self.bx, self.by)
        bx, by, dx, dy, hit, fell = self._move(self.bx, self.by, self.dx, self.dy, self.bricks)
        reward, done = 0.0, False
        if hit is not None:
            self.bricks[hit[1], hit[0]] = False
            reward = 1.0
            if not self.bricks.any():
                return reward + 5.0, True
        if fell:
            self.lives -= 1
            if self.lives <= 0:
                return reward, True
            self._serve()
            return reward, done
        self.bx, self.by, self.dx, self.dy = bx, by, dx, dy
        return reward, done

    def render(self):
        img = canvas()
        for r, col in zip(ROWS, ROW_COLORS):
            for x in np.flatnonzero(self.bricks[r]):
                put(img, int(x), r, col)
        for i in range(PW):
            put(img, self.px + i, 15, MAGENTA)
        if self.trail:
            put(img, self.prev[0], self.prev[1], BLUE)
        put(img, self.bx, self.by, WHITE)
        return img

    def _landing_x(self):
        bx, by, dx, dy = self.bx, self.by, self.dx, self.dy
        bricks = self.bricks.copy()
        for _ in range(80):
            if dy > 0 and by == 14:
                nx = bx + dx
                return nx if 0 <= nx <= 15 else bx - dx
            bx, by, dx, dy, hit, _ = self._move(bx, by, dx, dy, bricks)
            if hit is not None:
                bricks[hit[1], hit[0]] = False
        return bx

    def expert(self):
        if self.dy > 0:
            lx = self._landing_x()
            off = 0 if lx >= 8 else PW - 1       # send ball back towards the centre
            target = lx - off
        else:
            target = self.bx - 1
        target = min(max(target, 0), 16 - PW)
        if target < self.px:
            return LEFT
        if target > self.px:
            return RIGHT
        return NOOP


class BricksMem(Bricks):
    """No ball trail: the direction of the ball must be remembered from previous frames."""
    trail = False
