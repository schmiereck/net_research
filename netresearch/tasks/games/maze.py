"""Maze: collect all pellets in a random maze while avoiding two chasers."""
from collections import deque

import numpy as np

from ...spec import BLUE, DOWN, GREEN, LEFT, NOOP, RED, RIGHT, UP, YELLOW
from ..base import Game
from .common import canvas, put

DIRS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}


def make_maze(rng, braid=0.6):
    """Random maze on a 15x15 grid (7x7 cells) with extra loops, padded to 16x16 with walls."""
    wall = np.ones((16, 16), dtype=bool)
    cells = [(x, y) for x in range(7) for y in range(7)]
    visited = {cells[int(rng.integers(len(cells)))]}
    stack = [next(iter(visited))]
    while stack:
        cx, cy = stack[-1]
        wall[2 * cy + 1, 2 * cx + 1] = False
        nb = [(cx + dx, cy + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
              if 0 <= cx + dx < 7 and 0 <= cy + dy < 7 and (cx + dx, cy + dy) not in visited]
        if not nb:
            stack.pop()
            continue
        nx, ny = nb[int(rng.integers(len(nb)))]
        wall[cy + ny + 1, cx + nx + 1] = False
        wall[2 * ny + 1, 2 * nx + 1] = False
        visited.add((nx, ny))
        stack.append((nx, ny))
    # braid: knock out some internal walls between two open cells to create loops
    for y in range(1, 14):
        for x in range(1, 14):
            if wall[y, x] and rng.random() < braid:
                if (not wall[y, x - 1] and not wall[y, x + 1] and wall[y - 1, x] and wall[y + 1, x]) or \
                   (not wall[y - 1, x] and not wall[y + 1, x] and wall[y, x - 1] and wall[y, x + 1]):
                    wall[y, x] = False
    return wall


class Maze(Game):
    max_steps = 400
    actions = [NOOP, UP, DOWN, LEFT, RIGHT]

    def reset(self):
        self.wall = make_maze(self.rng)
        self.pellet = ~self.wall
        self.ax, self.ay = 1, 1
        self.pellet[1, 1] = False
        self.chasers = [[13, 13], [13, 1]]
        self.n_pellets = int(self.pellet.sum())

    def _free(self, x, y):
        return 0 <= x < 16 and 0 <= y < 16 and not self.wall[y, x]

    def _bfs(self, sx, sy, blocked=None):
        dist = np.full((16, 16), -1, dtype=int)
        dist[sy, sx] = 0
        q = deque([(sx, sy)])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRS.values():
                nx, ny = x + dx, y + dy
                if self._free(nx, ny) and dist[ny, nx] < 0 and (blocked is None or not blocked[ny, nx]):
                    dist[ny, nx] = dist[y, x] + 1
                    q.append((nx, ny))
        return dist

    def step(self, action):
        if action in DIRS:
            dx, dy = DIRS[action]
            if self._free(self.ax + dx, self.ay + dy):
                self.ax, self.ay = self.ax + dx, self.ay + dy
        reward = 0.0
        if self.pellet[self.ay, self.ax]:
            self.pellet[self.ay, self.ax] = False
            reward += 1.0
            if not self.pellet.any():
                return reward + 10.0, True
        if self._caught():
            return reward - 5.0, True
        dist = self._bfs(self.ax, self.ay)
        for c in self.chasers:
            if self.rng.random() > 0.6:       # sometimes idle / wander
                opts = [(c[0] + dx, c[1] + dy) for dx, dy in DIRS.values() if self._free(c[0] + dx, c[1] + dy)]
                if opts and self.rng.random() < 0.5:
                    c[0], c[1] = opts[int(self.rng.integers(len(opts)))]
                continue
            best = None
            for dx, dy in DIRS.values():
                nx, ny = c[0] + dx, c[1] + dy
                if self._free(nx, ny) and (best is None or dist[ny, nx] < dist[best[1], best[0]]):
                    best = (nx, ny)
            if best is not None:
                c[0], c[1] = best
        if self._caught():
            return reward - 5.0, True
        return reward, False

    def _caught(self):
        return any(c[0] == self.ax and c[1] == self.ay for c in self.chasers)

    def render(self):
        img = canvas()
        img[:, self.wall] = np.array(BLUE, dtype=np.float32)[:, None]
        img[:, self.pellet] = np.array(GREEN, dtype=np.float32)[:, None]
        put(img, self.ax, self.ay, YELLOW)
        for c in self.chasers:
            put(img, c[0], c[1], RED)
        return img

    def expert(self):
        dc = np.full((16, 16), 999, dtype=int)     # maze distance to the nearest chaser
        for c in self.chasers:
            d = self._bfs(c[0], c[1])
            dc = np.where(d >= 0, np.minimum(dc, d), dc)
        danger = dc <= 3
        danger[self.ay, self.ax] = False
        dist = self._bfs(self.ax, self.ay, blocked=danger)
        cand = np.argwhere(self.pellet & (dist > 0))
        if len(cand):
            # nearest pellet, then walk back along the BFS tree to find the first step
            ty, tx = min(cand, key=lambda p: dist[p[0], p[1]])
            x, y = int(tx), int(ty)
            while dist[y, x] > 1:
                for dx, dy in DIRS.values():
                    px, py = x - dx, y - dy
                    if 0 <= px < 16 and 0 <= py < 16 and dist[py, px] == dist[y, x] - 1:
                        x, y = px, py
                        break
            for a, (dx, dy) in DIRS.items():
                if (self.ax + dx, self.ay + dy) == (x, y):
                    return a
        # no safe pellet path: maximise maze distance to the nearest chaser
        best_a, best_d = NOOP, -1
        for a in [NOOP] + list(DIRS):
            dx, dy = DIRS.get(a, (0, 0))
            nx, ny = self.ax + dx, self.ay + dy
            if not self._free(nx, ny):
                continue
            if dc[ny, nx] > best_d:
                best_a, best_d = a, dc[ny, nx]
        return best_a
