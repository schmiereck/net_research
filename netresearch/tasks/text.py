"""Next-character prediction on a public-domain text (Alice in Wonderland, Project Gutenberg)."""
from pathlib import Path

import numpy as np

from ..spec import TaskSpec
from .base import SupervisedTask

DATA = Path(__file__).resolve().parents[2] / "data"
VOCAB = "abcdefghijklmnopqrstuvwxyz .,;:!?'\"-()"      # 38 symbols (<= 48 = 16 cols x 3 channels)
FALLBACK = "the quick brown fox jumps over the lazy dog. " * 400


def load_corpus():
    p = DATA / "alice.txt"
    raw = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else FALLBACK
    if "*** START OF" in raw:
        raw = raw.split("*** START OF", 1)[1].split("\n", 1)[1]
    if "*** END OF" in raw:
        raw = raw.split("*** END OF", 1)[0]
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("_", "")):
        raw = raw.replace(a, b)
    raw = " ".join(raw.lower().split())   # collapse whitespace/newlines
    idx = {c: i for i, c in enumerate(VOCAB)}
    return np.array([idx[c] for c in raw if c in idx], dtype=np.int64)


class CharNext(SupervisedTask):
    CTX = 16

    def __init__(self):
        ids = load_corpus()
        cut = int(len(ids) * 0.9)
        self.ids = {"train": ids[:cut], "test": ids[cut:]}
        majority = np.bincount(ids, minlength=len(VOCAB)).max() / len(ids)
        self.spec = TaskSpec("charnext", "text", "supervised", "class", len(VOCAB), seq_len=8,
                             chance=float(majority),
                             description="next char; last 16 chars as one-hot rows (col=i%16, ch=i//16)")

    def sample(self, batch, rng, split="train"):
        T, K = self.spec.seq_len, self.CTX
        ids = self.ids[split]
        starts = rng.integers(0, len(ids) - (K + T + 1), size=batch)
        win = np.stack([ids[s:s + K + T] for s in starts])          # [B, K+T]
        obs = np.zeros((T, batch, 3, 16, 16), dtype=np.float32)
        target = np.empty((T, batch), dtype=np.int64)
        rows = np.arange(K)
        bidx = np.arange(batch)[:, None]
        for t in range(T):
            ctx = win[:, t:t + K]                                    # [B,16]; row 15 = current char
            obs[t, bidx, ctx // 16, rows[None, :], ctx % 16] = 1.0
            target[t] = win[:, t + K]
        return {"obs": obs, "target": target, "mask": np.ones((T, batch), dtype=np.float32)}
