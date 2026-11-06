"""Paddle duel: ball and two paddles; the agent controls the right paddle against a CPU opponent."""
from ...spec import BLUE, DOWN, NOOP, RED, UP, WHITE, YELLOW
from ..base import Game
from .common import canvas, put

PH = 2          # paddle height
WIN = 5         # points to end an episode


class Paddle(Game):
    max_steps = 400
    actions = [NOOP, UP, DOWN]
    trail = True        # draw previous ball position (direction visible in one frame)

    def reset(self):
        self.py = 6          # player paddle top (x=15)
        self.oy = 6          # opponent paddle top (x=0)
        self.score = [0, 0]  # player, opponent
        self._serve(direction=1 if self.rng.random() < 0.5 else -1)

    def _serve(self, direction):
        self.bx, self.by = 7 + (direction < 0), int(self.rng.integers(3, 13))
        self.dx, self.dy = direction, int(self.rng.choice([-1, 1]))
        self.prev = (self.bx - self.dx, self.by - self.dy)

    def _ball_next(self, bx, by, dx, dy):
        ny = by + dy
        if ny < 0 or ny > 15:
            dy = -dy
            ny = by + dy
        return bx + dx, ny, dx, dy

    def step(self, action):
        if action == UP:
            self.py = max(0, self.py - 1)
        elif action == DOWN:
            self.py = min(16 - PH, self.py + 1)
        # opponent: imperfect tracking when ball approaches
        if self.dx < 0 and self.rng.random() < 0.8:
            c = self.oy + 1
            self.oy += (self.by > c) - (self.by < c)
        elif self.dx > 0 and self.rng.random() < 0.2:
            self.oy += (7 > self.oy + 1) - (7 < self.oy + 1)
        self.oy = min(max(self.oy, 0), 16 - PH)

        self.prev = (self.bx, self.by)
        nx, ny, dx, dy = self._ball_next(self.bx, self.by, self.dx, self.dy)
        reward, done = 0.0, False
        if nx == 15:
            if self.py <= ny < self.py + PH:
                off = ny - self.py
                dx, dy = -1, (-1 if off == 0 else (1 if off == PH - 1 else dy))
                nx = 14 + dx
            else:
                reward = -1.0
                self.score[1] += 1
        elif nx == 0:
            if self.oy <= ny < self.oy + PH:
                off = ny - self.oy
                dx, dy = 1, (-1 if off == 0 else (1 if off == PH - 1 else dy))
                nx = 1 + dx
            else:
                reward = 1.0
                self.score[0] += 1
        if reward != 0:
            done = max(self.score) >= WIN
            self._serve(direction=1 if reward < 0 else -1)
        else:
            self.bx, self.by, self.dx, self.dy = nx, ny, dx, dy
        return reward, done

    def render(self):
        img = canvas()
        for i in range(PH):
            put(img, 15, self.py + i, WHITE)
            put(img, 0, self.oy + i, RED)
        if self.trail:
            put(img, self.prev[0], self.prev[1], BLUE)
        put(img, self.bx, self.by, YELLOW)
        return img

    def _intercept(self):
        bx, by, dx, dy = self.bx, self.by, self.dx, self.dy
        for _ in range(40):
            nx, ny, dx, dy = self._ball_next(bx, by, dx, dy)
            if nx >= 15:
                return ny
            if nx <= 0:   # bounce off the opponent side (assume it returns)
                dx = 1
                nx = 1
            bx, by = nx, ny
        return by

    def expert(self):
        target = self._intercept() - 1 if self.dx > 0 else self.by - 1
        target = min(max(target, 0), 16 - PH)
        if target < self.py:
            return UP
        if target > self.py:
            return DOWN
        return NOOP


class PaddleMem(Paddle):
    """No ball trail: the direction of the ball must be remembered from previous frames."""
    trail = False
