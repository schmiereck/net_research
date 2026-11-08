"""Grid-World: walk from the start to the goal past walls and pits; optional: push a box onto a target.

grid         16x16 world, fully visible. Expert: shortest path that avoids pits.
grid_follow  32x32 world, the 16x16 view is centred on the player (outside the world = wall). The goal starts
             out of sight. Expert = exploring agent that only knows what it HAS SEEN: if it has seen the goal it
             walks the shortest known path; otherwise it walks to the nearest frontier (a seen free cell next to
             an unseen cell). Its actions depend on the history of views, so the learner needs memory of the
             explored area (and of the goal once it scrolls out of view).
grid_scroll  like grid_follow, but the camera has a dead zone: the player moves freely in the middle
             (columns/rows 4..11 of the image) and drags the view along only near the border; the view stays
             inside the world. The player position in the image changes, so position has to be read.
push         16x16, fully visible: push one box onto the target (sokoban rules: push only, no pull).
             Expert: exact distance-to-solution table from a backward search (pull moves) over all
             (player, box) states, computed once per episode.

Every world exists in a hard and an easy ("_easy") variant: the easy ones have few walls (5 % instead of
20 %), so the way is mostly free and a local "step towards the goal" rule already works often; there the
grid tests steering and the scrolling worlds test memory. The hard ones need real path planning (a local
rule reaches the goal in only 16 % of the hard 16x16 worlds). push_easy: open room, box close to the target.

Colours: wall blue, pit red, goal / target green, player yellow, box magenta (white on the target).
Rewards: goal / box on target +1 (done), pit -1 (done); score is normalised between random and expert.
"""
from collections import deque

import numpy as np

from ...spec import BLUE, DOWN, GREEN, LEFT, MAGENTA, NOOP, RED, RIGHT, UP, WHITE, YELLOW
from ..base import Game
from .common import canvas

DIRS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}
FREE, WALL, PIT = 0, 1, 2
_COL = {WALL: np.array(BLUE, np.float32), PIT: np.array(RED, np.float32)}


def bfs(passable, sx, sy):
    """Distances on a boolean grid [H,W] from (sx,sy), -1 = unreachable."""
    H, W = passable.shape
    dist = np.full((H, W), -1, dtype=np.int32)
    dist[sy, sx] = 0
    q = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for dx, dy in DIRS.values():
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and passable[ny, nx] and dist[ny, nx] < 0:
                dist[ny, nx] = dist[y, x] + 1
                q.append((nx, ny))
    return dist


def step_towards(dist, x, y):
    """Action that moves from (x,y) to a neighbour with distance dist[y,x]-1 (dist = distance TO a target)."""
    for a, (dx, dy) in DIRS.items():
        nx, ny = x + dx, y + dy
        if 0 <= ny < dist.shape[0] and 0 <= nx < dist.shape[1] and dist[ny, nx] == dist[y, x] - 1:
            return a
    return NOOP


def make_world(rng, size, wall_p, n_pits, min_dist):
    """Border walls, random walls and pits; start and goal with a pit-free path of length >= min_dist."""
    while True:
        cell = np.where(rng.random((size, size)) < wall_p, WALL, FREE).astype(np.int8)
        cell[0, :] = cell[-1, :] = cell[:, 0] = cell[:, -1] = WALL
        free = np.argwhere(cell == FREE)
        for y, x in free[rng.choice(len(free), size=min(n_pits, len(free)), replace=False)]:
            cell[y, x] = PIT
        free = np.argwhere(cell == FREE)
        sy, sx = free[rng.integers(len(free))]
        d = bfs(cell == FREE, sx, sy)
        far = np.argwhere(d >= min_dist)
        if len(far):
            gy, gx = far[rng.integers(len(far))]
            return cell, (int(sx), int(sy)), (int(gx), int(gy))


class GridWorld(Game):
    """Fully visible 16x16 grid world."""
    max_steps = 60
    actions = [NOOP, UP, DOWN, LEFT, RIGHT]
    size, wall_p, n_pits, min_dist = 16, 0.2, 8, 10

    def reset(self):
        self.cell, (self.x, self.y), self.goal = make_world(self.rng, self.size, self.wall_p, self.n_pits,
                                                            self.min_dist)
        self.to_goal = bfs(self.cell == FREE, *self.goal)          # true distances (for the full-view expert)
        self.on_reset()

    def on_reset(self):
        pass

    def step(self, action):
        if action in DIRS:
            dx, dy = DIRS[action]
            if self.cell[self.y + dy, self.x + dx] != WALL:
                self.x, self.y = self.x + dx, self.y + dy
        self.on_move()
        if self.cell[self.y, self.x] == PIT:
            return -1.0, True
        if (self.x, self.y) == self.goal:
            return 1.0, True
        return 0.0, False

    def on_move(self):
        pass

    def view_origin(self):
        return 0, 0

    def render(self):
        img = canvas()
        ox, oy = self.view_origin()
        S = self.size
        ys, xs = np.mgrid[oy:oy + 16, ox:ox + 16]
        inside = (xs >= 0) & (xs < S) & (ys >= 0) & (ys < S)
        cell = np.full((16, 16), WALL, np.int8)
        cell[inside] = self.cell[ys[inside], xs[inside]]
        for k, col in _COL.items():
            img[:, cell == k] = col[:, None]
        for (px, py), col in ((self.goal, GREEN), ((self.x, self.y), YELLOW)):
            if 0 <= px - ox < 16 and 0 <= py - oy < 16:
                img[:, py - oy, px - ox] = col
        return img

    def expert(self):
        return step_towards(self.to_goal, self.x, self.y)


class GridFollow(GridWorld):
    """32x32 world, view centred on the player; exploring expert that only uses what it has seen."""
    max_steps = 200
    size, wall_p, n_pits, min_dist = 32, 0.2, 30, 24

    def on_reset(self):
        self.seen = np.zeros((self.size, self.size), dtype=bool)
        self.on_move()

    def view_origin(self):
        return self.x - 8, self.y - 8

    def on_move(self):
        ox, oy = self.view_origin()
        S = self.size
        self.seen[max(0, oy):max(0, min(S, oy + 16)), max(0, ox):max(0, min(S, ox + 16))] = True

    def expert(self):
        known_free = self.seen & (self.cell == FREE)
        gx, gy = self.goal
        if self.seen[gy, gx]:
            d = bfs(known_free, gx, gy)
            if d[self.y, self.x] > 0:
                return step_towards(d, self.x, self.y)
        # nearest frontier: seen free cell with an unseen 4-neighbour
        unseen = ~self.seen
        nb = np.zeros_like(unseen)
        nb[1:] |= unseen[:-1]
        nb[:-1] |= unseen[1:]
        nb[:, 1:] |= unseen[:, :-1]
        nb[:, :-1] |= unseen[:, 1:]
        frontier = known_free & nb
        d = bfs(known_free, self.x, self.y)
        cand = np.argwhere(frontier & (d > 0))
        if not len(cand):
            return NOOP
        fy, fx = min(cand, key=lambda p: (d[p[0], p[1]], p[0], p[1]))
        back = bfs(known_free, int(fx), int(fy))
        return step_towards(back, self.x, self.y)


class GridScroll(GridFollow):
    """Like GridFollow, but the camera has a dead zone (player free in image cells 4..11) and stays in the world."""
    LO, HI = 4, 11

    def on_reset(self):
        self.cx = int(np.clip(self.x - 8, 0, self.size - 16))
        self.cy = int(np.clip(self.y - 8, 0, self.size - 16))
        super().on_reset()

    def view_origin(self):
        return self.cx, self.cy

    def on_move(self):
        if self.x - self.cx < self.LO:
            self.cx = self.x - self.LO
        elif self.x - self.cx > self.HI:
            self.cx = self.x - self.HI
        if self.y - self.cy < self.LO:
            self.cy = self.y - self.LO
        elif self.y - self.cy > self.HI:
            self.cy = self.y - self.HI
        self.cx = int(np.clip(self.cx, 0, self.size - 16))
        self.cy = int(np.clip(self.cy, 0, self.size - 16))
        super().on_move()


class Push(Game):
    """Push one box onto the target. Expert: exact distances over (player, box) states (backward search)."""
    max_steps = 80
    actions = [NOOP, UP, DOWN, LEFT, RIGHT]
    wall_p, min_dist, max_dist = 0.1, 8, 10 ** 6

    def reset(self):
        while True:
            free = self.rng.random((16, 16)) >= self.wall_p
            free[0, :] = free[-1, :] = free[:, 0] = free[:, -1] = False
            cells = np.argwhere(free)
            ty, tx = cells[self.rng.integers(len(cells))]
            self.free, self.target = free, (int(tx), int(ty))
            self._solve()
            ok = np.argwhere((self.dist >= self.min_dist) & (self.dist <= self.max_dist))
            if len(ok):
                p, b = ok[self.rng.integers(len(ok))]
                self.x, self.y = int(p % 16), int(p // 16)
                self.bx, self.by = int(b % 16), int(b // 16)
                return

    def _solve(self):
        """dist[p, b] = pushes+moves to bring the box at b onto the target with the player at p (-1 = never)."""
        free = self.free.ravel()
        dist = np.full((256, 256), -1, dtype=np.int32)
        t = self.target[1] * 16 + self.target[0]
        q = deque()
        for p in np.flatnonzero(free):
            if p != t:
                dist[p, t] = 0
                q.append((p, t))
        steps = [-16, 16, -1, 1]
        while q:
            p, b = q.popleft()
            nd = dist[p, b] + 1
            for s in steps:
                pp = p - s                                    # player came from pp by moving +s
                if not free[pp] or pp == b:
                    continue
                if dist[pp, b] < 0:                           # plain move pp -> p
                    dist[pp, b] = nd
                    q.append((pp, b))
                if b == p + s:                                # p + s was pushed: before, box at p, player at pp
                    if dist[pp, p] < 0:
                        dist[pp, p] = nd
                        q.append((pp, p))
        self.dist = dist

    def _next(self, action):
        if action not in DIRS:
            return self.x, self.y, self.bx, self.by
        dx, dy = DIRS[action]
        nx, ny = self.x + dx, self.y + dy
        if not self.free[ny, nx]:
            return self.x, self.y, self.bx, self.by
        if (nx, ny) == (self.bx, self.by):
            if not self.free[ny + dy, nx + dx]:
                return self.x, self.y, self.bx, self.by
            return nx, ny, nx + dx, ny + dy
        return nx, ny, self.bx, self.by

    def step(self, action):
        self.x, self.y, self.bx, self.by = self._next(action)
        if (self.bx, self.by) == self.target:
            return 1.0, True
        return 0.0, False

    def render(self):
        img = canvas()
        img[:, ~self.free] = _COL[WALL][:, None]
        tx, ty = self.target
        img[:, ty, tx] = GREEN
        img[:, self.by, self.bx] = WHITE if (self.bx, self.by) == self.target else MAGENTA
        img[:, self.y, self.x] = YELLOW
        return img

    def expert(self):
        best, best_d = NOOP, None
        for a in self.actions:
            x, y, bx, by = self._next(a)
            d = self.dist[y * 16 + x, by * 16 + bx]
            if d >= 0 and (best_d is None or d < best_d):
                best, best_d = a, d
        return best


# ------------------------------------------------------------------------------------------- easy variants
class GridWorldEasy(GridWorld):
    wall_p, n_pits, min_dist = 0.05, 6, 6


class GridFollowEasy(GridFollow):
    wall_p = 0.05


class GridScrollEasy(GridScroll):
    wall_p = 0.05


class PushEasy(Push):
    """Open room (no inner walls), the solution takes 3-12 steps."""
    max_steps = 50
    wall_p, min_dist, max_dist = 0.0, 3, 12


# ------------------------------------------------------------------ frame test: same world, two views
class GridSmall(GridWorld):
    """8x8 world, fully visible at a fixed place in the image (allocentric: the player moves in the image;
    outside the world = wall)."""
    max_steps = 30
    size, wall_p, n_pits, min_dist = 8, 0.2, 2, 5

    def view_origin(self):
        return -4, -4


class GridSmallEgo(GridSmall):
    """The same 8x8 worlds, but the 16x16 view is centred on the player (egocentric). The whole world is
    still always visible, so both variants carry the same information; only the reference frame differs."""

    def view_origin(self):
        return self.x - 8, self.y - 8
