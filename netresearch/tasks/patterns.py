"""Bit-pattern tasks: continue bit streams, count.

Train/test split: every generated stream has generator parameters (e.g. the cycle pattern). A hash of those
parameters decides whether it belongs to the train or the test split, so test patterns are guaranteed never
to appear during training ("nicht gelernte Bitmuster").
"""
import zlib

import numpy as np

from ..spec import TaskSpec
from .base import SupervisedTask

TEST_FRACTION = 4          # 1 in 4 parameter sets is reserved for testing


def _split_of(key) -> str:
    return "test" if zlib.crc32(repr(key).encode()) % TEST_FRACTION == 0 else "train"


def _canonical_cycle(p):
    """Rotation-invariant key of a cycle pattern (phase must not leak the split)."""
    s = "".join(map(str, p))
    return min(s[i:] + s[:i] for i in range(len(s)))


# ------------------------------------------------------------------------------------- stream generators
def gen_periodic(rng, length, lmin=2, lmax=12):
    L = int(rng.integers(lmin, lmax + 1))
    while True:
        p = rng.integers(0, 2, size=L)
        if 0 < p.sum() < L:
            break
    phase = int(rng.integers(L))
    return p[(np.arange(length) + phase) % L], ("periodic", _canonical_cycle(p))


def gen_counter(rng, length):
    """Binary numbers n, n+step, n+2*step ... written MSB-first as one bit stream (width w)."""
    w = int(rng.integers(3, 6))
    step = int(rng.integers(1, 4))
    n0 = int(rng.integers(0, 2 ** w))
    nums = (n0 + step * np.arange(length // w + 2)) % (2 ** w)
    bits = ((nums[:, None] >> np.arange(w - 1, -1, -1)) & 1).reshape(-1)
    off = int(rng.integers(w))
    return bits[off:off + length], ("counter", w, step)


def gen_runs(rng, length):
    """Alternating runs with growing lengths a, a+d, a+2d ... (wrapping back to a after max)."""
    a, d, mx = int(rng.integers(1, 3)), int(rng.integers(1, 3)), int(rng.integers(4, 8))
    bit = int(rng.integers(2))
    out, ln = [], a
    while len(out) < length + 40:
        out += [bit] * ln
        bit ^= 1
        ln = ln + d if ln + d <= mx else a
    off = int(rng.integers(20))
    return np.array(out[off:off + length]), ("runs", a, d, mx)


def gen_xor(rng, length):
    """XOR of two periodic streams (long overall period)."""
    s1, k1 = gen_periodic(rng, length, 2, 5)
    s2, k2 = gen_periodic(rng, length, 3, 7)
    return s1 ^ s2, ("xor", k1, k2)


def gen_lfsr(rng, length):
    """Linear feedback shift register: next bit = XOR of selected taps of the last n bits."""
    n = int(rng.integers(3, 6))
    while True:
        taps = tuple(sorted(set(rng.integers(0, n, size=int(rng.integers(2, 4))).tolist())))
        if 0 in taps and len(taps) >= 2:
            break
    state = list(rng.integers(0, 2, size=n))
    if not any(state):
        state[0] = 1
    out = list(state)
    while len(out) < length:
        out.append(int(np.bitwise_xor.reduce([out[-n + t] for t in taps])))
    return np.array(out[:length]), ("lfsr", n, taps)


FAMILIES = {"periodic": gen_periodic, "counter": gen_counter, "runs": gen_runs, "xor": gen_xor, "lfsr": gen_lfsr}


def sample_streams(batch, length, rng, split, families):
    out = np.empty((batch, length), dtype=np.int64)
    fam = list(families)
    for b in range(batch):
        while True:
            f = fam[int(rng.integers(len(fam)))]
            s, key = families[f](rng, length)
            if _split_of(key) == split:
                out[b] = s
                break
    return out


# ---------------------------------------------------------------------------------------------- tasks
class _Window(SupervisedTask):
    """Last 16 bits visible as vertical stripes (white=1, newest bit right); predict the next bit."""
    HIST = 16
    families = None

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        s = sample_streams(batch, self.HIST + T, rng, split, self.families)
        obs = np.zeros((T, batch, 3, 16, 16), dtype=np.float32)
        target = np.empty((T, batch), dtype=np.int64)
        for t in range(T):
            obs[t] = s[:, t:t + self.HIST][:, None, None, :]
            target[t] = s[:, t + self.HIST]
        return {"obs": obs, "target": target, "mask": np.ones((T, batch), dtype=np.float32)}


class BitSeq(_Window):
    """1-D bit stream (16 newest bits as vertical stripes, newest right) from several generator families."""
    families = FAMILIES

    def __init__(self):
        self.spec = TaskSpec("bitseq", "patterns", "supervised", "class", 2, seq_len=4, chance=0.5,
                             description="mixed bit-stream generators (periodic, counter, growing runs, xor of "
                                         "cycles, LFSR), 16 bits visible -> next bit; test params held out")


# ------------------------------------------------------------------------------------- row-based tasks
WORD = 8          # bits per row (right-aligned in columns 8..15, MSB left)


def to_bits(v):
    return ((np.asarray(v)[..., None] >> np.arange(WORD - 1, -1, -1)) & 1).astype(np.float32)


def draw_rows(words, n_visible):
    """words [B, >=n] ints, n_visible [B] -> image [B,3,16,16]; row j (top->bottom) = word j, white = 1."""
    B = len(words)
    img = np.zeros((B, 3, 16, 16), dtype=np.float32)
    for b in range(B):
        n = int(n_visible[b])
        img[b, :, :n, 16 - WORD:] = to_bits(words[b, :n])[None]
    return img


def gen_row_cycle(rng, pmin=2, pmax=8):
    """Random cycle of P words (not all equal). Returns (words, key)."""
    P = int(rng.integers(pmin, pmax + 1))
    while True:
        w = rng.integers(0, 2 ** WORD, size=P)
        if len(set(w.tolist())) > 1:
            break
    rot = min(tuple(np.roll(w, -i).tolist()) for i in range(P))   # rotation-invariant key
    return w, rot


def sample_row_cycles(batch, length, rng, split, pmin=2, pmax=8):
    out = np.empty((batch, length), dtype=np.int64)
    periods = np.empty(batch, dtype=np.int64)
    for b in range(batch):
        while True:
            w, key = gen_row_cycle(rng, pmin, pmax)
            if _split_of(("rows",) + key) == split:
                break
        phase = int(rng.integers(len(w)))
        out[b] = w[(np.arange(length) + phase) % len(w)]
        periods[b] = len(w)
    return out, periods


class Cycle(SupervisedTask):
    """Rows = time steps (top -> bottom). A cycle of P = 2..8 words (8 bit) repeats; 2P..16 rows are
    visible; predict the next row (8 bits). Test cycles never occur in training."""

    def __init__(self):
        self.spec = TaskSpec("cycle", "patterns", "supervised", "bits", WORD, seq_len=1, chance=0.0,
                             description="rows = time steps; repeating cycle of 2-8 words (8 bit), "
                                         "2P..16 rows visible -> next row; test cycles held out")

    def sample(self, batch, rng, split="train"):
        words, P = sample_row_cycles(batch, 17, rng, split)
        n = np.array([rng.integers(2 * p, 17) for p in P])
        target = to_bits(words[np.arange(batch), n])
        return {"obs": draw_rows(words, n)[None], "target": target[None], "mask": np.ones((1, batch), np.float32)}


class CycleMem(SupervisedTask):
    """Same row cycles, but only the current row is visible (top row): the net has to remember."""

    def __init__(self):
        self.spec = TaskSpec("cycle_mem", "patterns", "supervised", "bits", WORD, seq_len=32, chance=0.0,
                             needs_memory=True,
                             description="repeating cycle of 2-8 words, only the current row visible "
                                         "-> next row (needs memory)")
        self.warmup = 16

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        words, _ = sample_row_cycles(batch, T + 1, rng, split)
        obs = np.stack([draw_rows(words[:, t:t + 1], np.ones(batch)) for t in range(T)])
        mask = np.zeros((T, batch), dtype=np.float32)
        mask[self.warmup:] = 1.0
        return {"obs": obs, "target": to_bits(words[:, 1:]).transpose(1, 0, 2).copy(), "mask": mask}


class Count(SupervisedTask):
    """Counter: random start, +1 per row; 2..16 rows visible -> next number (8 bit, wraps at 256)."""

    def __init__(self):
        self.spec = TaskSpec("count", "patterns", "supervised", "bits", WORD, seq_len=1, chance=0.0,
                             description="rows = counter v, v+1, ... (random start), 2-16 rows visible -> next")

    def sample(self, batch, rng, split="train"):
        v0 = rng.integers(0, 256, size=batch)
        words = (v0[:, None] + np.arange(17)) % 256
        n = rng.integers(2, 17, size=batch)
        target = to_bits(words[np.arange(batch), n])
        return {"obs": draw_rows(words, n)[None], "target": target[None], "mask": np.ones((1, batch), np.float32)}


class NumSeq(SupervisedTask):
    """3 rows of a number sequence (mod 256) -> next number. Rule must be inferred: arithmetic with step
    1..63 or Fibonacci-like v[n+1] = v[n] + v[n-1]."""

    def __init__(self):
        self.spec = TaskSpec("numseq", "patterns", "supervised", "bits", WORD, seq_len=1, chance=0.0,
                             description="3 rows, rule arithmetic (k=1..63) or fibonacci-like -> next number")

    def sample(self, batch, rng, split="train"):
        words = np.empty((batch, 4), dtype=np.int64)
        fib = rng.random(batch) < 0.5
        a, b = rng.integers(0, 256, size=batch), rng.integers(0, 256, size=batch)
        k = rng.integers(1, 64, size=batch)
        for i in range(batch):
            if fib[i]:
                seq = [a[i], b[i]]
                while len(seq) < 4:
                    seq.append((seq[-1] + seq[-2]) % 256)
            else:
                seq = [(a[i] + k[i] * j) % 256 for j in range(4)]
            words[i] = seq
        return {"obs": draw_rows(words, np.full(batch, 3))[None], "target": to_bits(words[:, 3])[None],
                "mask": np.ones((1, batch), np.float32)}
