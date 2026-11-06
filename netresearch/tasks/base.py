"""Task base classes.

Supervised tasks produce batches of sequences:
    obs    float32 [T, B, 3, 16, 16]
    target int64 [T, B] (head=class) or float32 [T, B, n_out] (head=bits)
    mask   float32 [T, B]  (which steps count for loss / metric)

Control tasks provide a vectorised environment with a scripted expert.
"""
import numpy as np

from ..spec import OBS_SHAPE


class SupervisedTask:
    spec = None

    def sample(self, batch: int, rng: np.random.Generator, split: str = "train") -> dict:
        raise NotImplementedError


class Game:
    """Single game instance. Subclasses implement reset/step/render/expert."""
    max_steps = 300

    def __init__(self, rng: np.random.Generator):
        self.rng = rng

    def reset(self):
        raise NotImplementedError

    def step(self, action: int):
        """Returns (reward, done)."""
        raise NotImplementedError

    def render(self) -> np.ndarray:
        raise NotImplementedError

    def expert(self) -> int:
        raise NotImplementedError


class VecEnv:
    """Batch of independent game instances with auto-reset."""

    def __init__(self, game_cls, n: int, seed: int):
        self.rng = np.random.default_rng(seed)
        self.games = [game_cls(np.random.default_rng(self.rng.integers(1 << 31))) for _ in range(n)]
        self.n = n
        for g in self.games:
            g.reset()
        self.ep_return = np.zeros(n)
        self.ep_len = np.zeros(n, dtype=int)

    def obs(self) -> np.ndarray:
        out = np.empty((self.n,) + OBS_SHAPE, dtype=np.float32)
        for i, g in enumerate(self.games):
            out[i] = g.render()
        return out

    def expert(self) -> np.ndarray:
        return np.array([g.expert() for g in self.games], dtype=np.int64)

    def step(self, actions):
        """Returns (reward[n], done[n], finished list of (env_idx, return, length))."""
        rew = np.zeros(self.n, dtype=np.float32)
        done = np.zeros(self.n, dtype=bool)
        finished = []
        for i, (g, a) in enumerate(zip(self.games, actions)):
            r, d = g.step(int(a))
            self.ep_return[i] += r
            self.ep_len[i] += 1
            if self.ep_len[i] >= g.max_steps:
                d = True
            rew[i] = r
            done[i] = d
            if d:
                finished.append((i, self.ep_return[i], self.ep_len[i]))
                self.ep_return[i] = 0
                self.ep_len[i] = 0
                g.reset()
        return rew, done, finished


class ControlTask:
    spec = None
    game_cls = None

    def make_env(self, n: int, seed: int) -> VecEnv:
        return VecEnv(self.game_cls, n, seed)
