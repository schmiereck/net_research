"""Bit-pattern tasks: continue cycles, count."""
import numpy as np

from ..spec import TaskSpec
from .base import SupervisedTask


def _cycle_streams(batch, length, rng, lmin=2, lmax=12):
    """Return int array [batch, length] of periodic bit streams."""
    out = np.empty((batch, length), dtype=np.int64)
    for b in range(batch):
        L = rng.integers(lmin, lmax + 1)
        while True:
            p = rng.integers(0, 2, size=L)
            if 0 < p.sum() < L:   # not constant
                break
        phase = rng.integers(L)
        out[b] = p[(np.arange(length) + phase) % L]
    return out


class Cycle(SupervisedTask):
    """Last 16 bits visible as vertical stripes (white=1); predict the next bit."""
    HIST = 16

    def __init__(self):
        self.spec = TaskSpec("cycle", "patterns", "supervised", "class", 2, seq_len=4, chance=0.5,
                             description="periodic bit stream, 16 bits history visible -> next bit")

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        s = _cycle_streams(batch, self.HIST + T, rng)           # [B, 16+T]
        obs = np.zeros((T, batch, 3, 16, 16), dtype=np.float32)
        target = np.empty((T, batch), dtype=np.int64)
        for t in range(T):
            hist = s[:, t:t + self.HIST]                         # [B,16], last column = current bit
            obs[t] = hist[:, None, None, :]
            target[t] = s[:, t + self.HIST]
        return {"obs": obs, "target": target, "mask": np.ones((T, batch), dtype=np.float32)}


class CycleMem(SupervisedTask):
    """Only the current bit is visible (whole frame white=1 / black=0): needs memory."""

    def __init__(self):
        self.spec = TaskSpec("cycle_mem", "patterns", "supervised", "class", 2, seq_len=40, chance=0.5,
                             needs_memory=True,
                             description="periodic bit stream, only current bit visible -> next bit")
        self.warmup = 24

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        s = _cycle_streams(batch, T + 1, rng)
        obs = np.broadcast_to(s[:, :T].T[:, :, None, None, None].astype(np.float32),
                              (T, batch, 3, 16, 16)).copy()
        target = s[:, 1:].T.copy()
        mask = np.zeros((T, batch), dtype=np.float32)
        mask[self.warmup:] = 1.0
        return {"obs": obs, "target": target, "mask": mask}


class Count(SupervisedTask):
    """Last 4 values of an arithmetic sequence (mod 256, step 1..7) shown as 8-bit rows -> next value bits."""

    def __init__(self):
        self.spec = TaskSpec("count", "patterns", "supervised", "bits", 8, seq_len=1, chance=1 / 256,
                             description="4 numbers v, v+k, ... as bit rows -> bits of next number")

    @staticmethod
    def _bits(v):
        return ((v[..., None] >> np.arange(7, -1, -1)) & 1).astype(np.float32)  # MSB first

    def sample(self, batch, rng, split="train"):
        v0 = rng.integers(0, 256, size=batch)
        k = rng.integers(1, 8, size=batch)
        vals = (v0[:, None] + k[:, None] * np.arange(5)) % 256      # [B,5]
        bits = self._bits(vals)                                      # [B,5,8]
        img = np.zeros((batch, 3, 16, 16), dtype=np.float32)
        for i in range(4):
            row = np.repeat(bits[:, i], 2, axis=1)                   # [B,16]
            img[:, :, 2 * i:2 * i + 2, :] = row[:, None, None, :]
        return {"obs": img[None], "target": bits[:, 4][None], "mask": np.ones((1, batch), np.float32)}
