"""Servo task (PLAN_TRAINER.md, library stage 2): move a pointer onto a target with one command.

Image: the pointer is one green pixel, the target one red pixel (yellow if they coincide). The command is the
step (cx, cy), each a signed 4-bit number (two's complement, -8..7), in the 8 "bits" outputs: bits 0-3 = cx,
bits 4-7 = cy (most significant bit first). The target lies within reach (|dx|, |dy| <= 7).

A DEVICE turns the wanted step d = target - pointer into the command that produces it. The base task is the
ideal device (command = d). The other devices are calibrations a fast learner has to pick up (library.py):
    flipx / flipy   one motor is mounted mirrored: that command changes sign
    rot180          both mirrored
    swap            the motors are wired crosswise: (cx, cy) = (dy, dx)
    rot90           swapped and one mirrored: (cx, cy) = (dy, -dx)
    strong          the device moves 2 pixels per unit: command = d / 2 (rounded towards zero)
    weak            the device moves half a pixel per unit: command = 2 d, limited to -8..7 (at the stop)
    offx / offy     the device adds a constant step (+1): command = d - 1 on that axis
    off2            constant step (+2, -1): command = (dx - 2, dy + 1)
Inputs are identical for all devices; only the asked command differs (as the numseq tasks of the library).
Train / test split by (pointer, target), so test situations never occur in training.
"""
import numpy as np

from ..spec import TaskSpec
from .base import SupervisedTask
from .patterns import _split_of

REACH = 7


def _clip(v):
    return np.clip(v, -8, 7)


DEVICES = {
    "ident": lambda dx, dy: (dx, dy),
    "flipx": lambda dx, dy: (-dx, dy),
    "flipy": lambda dx, dy: (dx, -dy),
    "rot180": lambda dx, dy: (-dx, -dy),
    "swap": lambda dx, dy: (dy, dx),
    "rot90": lambda dx, dy: (dy, -dx),
    "strong": lambda dx, dy: (np.fix(dx / 2).astype(np.int64), np.fix(dy / 2).astype(np.int64)),
    "weak": lambda dx, dy: (_clip(2 * dx), _clip(2 * dy)),
    "offx": lambda dx, dy: (_clip(dx - 1), dy),
    "offy": lambda dx, dy: (dx, _clip(dy - 1)),
    "off2": lambda dx, dy: (_clip(dx - 2), _clip(dy + 1)),
}

_TEST = None


def _test_table():
    """[px, py, tx, ty] -> True if the situation belongs to the test split."""
    global _TEST
    if _TEST is None:
        import zlib
        from .patterns import TEST_FRACTION
        idx = np.indices((16, 16, 16, 16)).reshape(4, -1).T
        _TEST = np.array([zlib.crc32(repr(("servo", *map(int, r))).encode()) % TEST_FRACTION == 0
                          for r in idx]).reshape(16, 16, 16, 16)
        assert _TEST[0, 0, 0, 0] == (_split_of(("servo", 0, 0, 0, 0)) == "test")
    return _TEST


def situations(n, rng, split="train"):
    """-> pointer [n, 2], target [n, 2] (x, y), target within reach, from the given split."""
    want, tab = split == "test", _test_table()
    p, t, filled = np.empty((n, 2), np.int64), np.empty((n, 2), np.int64), 0
    while filled < n:
        pp = rng.integers(0, 16, size=(2 * n, 2))
        tt = pp + rng.integers(-REACH, REACH + 1, size=(2 * n, 2))
        ok = ((tt >= 0) & (tt < 16)).all(1)
        ok &= tab[pp[:, 0], pp[:, 1], tt[:, 0].clip(0, 15), tt[:, 1].clip(0, 15)] == want
        m = min(n - filled, int(ok.sum()))
        p[filled:filled + m], t[filled:filled + m] = pp[ok][:m], tt[ok][:m]
        filled += m
    return p, t


def draw(p, t):
    n = len(p)
    img = np.zeros((n, 3, 16, 16), dtype=np.float32)
    i = np.arange(n)
    img[i, 1, p[:, 1], p[:, 0]] = 1.0                      # pointer: green
    img[i, 0, t[:, 1], t[:, 0]] = 1.0                      # target: red
    return img


def command_bits(cx, cy):
    """Signed steps -> [n, 8] float bits (two's complement nibbles, MSB first)."""
    v = np.stack([np.asarray(cx) & 15, np.asarray(cy) & 15], 1)                 # [n, 2]
    return ((v[:, :, None] >> np.arange(3, -1, -1)) & 1).reshape(len(v), 8).astype(np.float32)


def bits_steps(bits):
    """Inverse of command_bits: [n, 8] bits -> [n, 2] signed steps."""
    v = (np.asarray(bits).reshape(-1, 2, 4).astype(np.int64) * np.array([8, 4, 2, 1])).sum(-1)
    return np.where(v > 7, v - 16, v)


def pop_code(steps, sigma=1.0):
    """[n, 2] signed steps -> [n, 32] population code: per axis 16 units for the values -8..7, each a Gaussian bump
    of the distance to the true value (width sigma in cells; sigma = 0: one-hot)."""
    d = np.arange(-8, 8)[None, None, :] - np.asarray(steps)[:, :, None]
    c = (d == 0).astype(np.float32) if sigma == 0 else np.exp(-0.5 * (d / sigma) ** 2).astype(np.float32)
    return c.reshape(len(c), 32)


STEP_SIGMA = 0.5     # width (cells) of the bump in the step code of the step tasks; 0 = one unit per value.
#                      1.0 won the rule on seeds 5 and 6 (learning speed on servo), but servo saturates anyway
#                      and 0.5 is about 0.07 better in the exact score of the fine search scenes; the user chose
#                      0.5 (LOGBUCH 2026-11-14). Results with 1.0: results/step_pop*.jsonl


def decode_step(x, spec, logits=True):
    """Outputs of a step task (numpy, [n, n_out]; logits, or with logits=False targets) -> [n, 2] signed steps.
    Works for both codes: 8 bits (spec.step) and the population code (spec.pop)."""
    x = np.asarray(x)
    if spec.pop:
        return x.reshape(len(x), 2, 16).argmax(-1).astype(np.int64) - 8
    return bits_steps(x > (0.0 if logits else 0.5))


def bits_variant(base, name):
    """The step task `base` in its original 8-bit code under another name (the reference for old results)."""
    class Bits(base):
        def __init__(self):
            super().__init__()
            self.spec.name = name

    Bits.__name__ = Bits.name = name
    return Bits


def pop_variant(base, name, sigma):
    """The step task `base` with the step given as a population code (32 outputs in the symbol area) instead of
    8 bits. Same images, same steps; only the output code differs. All batches the task hands out (sample, make,
    held_out) carry the population code as target."""
    from dataclasses import replace

    class Pop(base):
        def __init__(self):
            super().__init__()
            assert self.spec.step, base
            self.spec = replace(self.spec, name=name, n_out=32, role="symbol", step=False, pop=True)

        @staticmethod
        def _pop(b):
            t = b["target"]
            if t.shape[-1] == 8:                                     # not yet converted (sample calls make)
                b["target"] = pop_code(bits_steps(t.reshape(-1, 8)), sigma).reshape(*t.shape[:-1], 32)
            return b

        def sample(self, *a, **k):
            return self._pop(super().sample(*a, **k))

    for fn in ("make", "held_out"):
        if hasattr(base, fn):
            setattr(Pop, fn, (lambda f: lambda self, *a, **k: self._pop(getattr(base, f)(self, *a, **k)))(fn))

    Pop.__name__ = Pop.name = name
    return Pop


def servo_batch(device, n, rng, split="train"):
    p, t = situations(n, rng, split)
    d = t - p
    cx, cy = DEVICES[device](d[:, 0], d[:, 1])
    return {"obs": draw(p, t)[None], "target": command_bits(cx, cy)[None], "mask": np.ones((1, n), np.float32)}


class Servo(SupervisedTask):
    """Pointer (green) and target (red) in the image -> the step that moves the pointer onto the target."""

    def __init__(self):
        self.spec = TaskSpec("servo", "patterns", "supervised", "bits", 8, seq_len=1, chance=0.0, step=True,
                             description="pointer and target pixel -> signed step (dx, dy), 2 x 4 bit")

    def sample(self, batch, rng, split="train"):
        return servo_batch("ident", batch, rng, split)
