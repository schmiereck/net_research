"""Memory battery: tasks that separate memory architectures by the kind of memory they need.

recall   associative recall: 2-6 (key, value) pairs one per frame, then the keys are asked in random order
         -> value. Needs memory that can be addressed by content.
delay    one marked word, then 8-30 frames that are blank or show unmarked distractor words, then a cue
         -> the marked word. Needs long, interference-protected storage (gating).
crossmem 4 words appear in the LEFT half, a few blank frames, then the RIGHT half points at one of the rows
         -> that word. Stored information and the question are in different image regions, so they have to
         be brought together (in modular nets: across modules).

All outputs are 8-bit words in the bits area; score = exact match. Train/test split by hash of the stored
content: test episodes only contain (key, value) pairs / words that never occur as stored content in
training, so the nets must bind and recall, not memorise associations.
"""
import numpy as np

from ..spec import TaskSpec
from .base import SupervisedTask
from .patterns import WORD, _split_of, to_bits

_TEST_WORD = np.array([_split_of(("memword", v)) == "test" for v in range(256)])
_TEST_PAIR = np.array([[_split_of(("pair", k, v)) == "test" for v in range(256)] for k in range(16)])


def _words(rng, shape, split):
    """Random 8-bit words that belong to the given split."""
    pool = np.flatnonzero(_TEST_WORD == (split == "test"))
    return pool[rng.integers(len(pool), size=shape)]


def _put_word(img, row, word, col0):
    """img [3,16,16]: word as 8 white pixels at row, columns col0..col0+7 (MSB left)."""
    img[:, row, col0:col0 + WORD] = to_bits(word)[None]


class Recall(SupervisedTask):
    MAX_PAIRS = 6

    def __init__(self):
        self.spec = TaskSpec("recall", "memory", "supervised", "bits", WORD, seq_len=2 * self.MAX_PAIRS,
                             chance=0.0, needs_memory=True,
                             description="associative recall: 2-6 (key, value) pairs one per frame, then each "
                                         "key is asked (random order) -> value; test pairs held out")

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        obs = np.zeros((T, batch, 3, 16, 16), np.float32)
        target = np.zeros((T, batch, WORD), np.float32)
        mask = np.zeros((T, batch), np.float32)
        want = split == "test"
        for b in range(batch):
            K = int(rng.integers(2, self.MAX_PAIRS + 1))
            keys = rng.choice(16, size=K, replace=False)
            vals = np.array([rng.choice(np.flatnonzero(_TEST_PAIR[k] == want)) for k in keys])
            for i, (k, v) in enumerate(zip(keys, vals)):       # store frames
                f = obs[i, b]
                f[1, 0, 0] = 1.0                                # green marker: store frame
                f[0, 2, k] = 1.0                                # key: red pixel at column k
                _put_word(f, 5, v, 8)                           # value
            for j, i in enumerate(rng.permutation(K)):          # query frames
                t = K + j
                obs[t, b, 2, 2, keys[i]] = 1.0                  # key asked: blue pixel at column k
                target[t, b] = to_bits(vals[i])
                mask[t, b] = 1.0
        return {"obs": obs, "target": target, "mask": mask}


class Delay(SupervisedTask):
    DMIN, DMAX = 8, 30

    def __init__(self):
        self.spec = TaskSpec("delay", "memory", "supervised", "bits", WORD, seq_len=self.DMAX + 2, chance=0.0,
                             needs_memory=True,
                             description="one marked word, 8-30 frames blank or with unmarked distractor "
                                         "words, then a cue -> the marked word; test words held out")

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        obs = np.zeros((T, batch, 3, 16, 16), np.float32)
        target = np.zeros((T, batch, WORD), np.float32)
        mask = np.zeros((T, batch), np.float32)
        word = _words(rng, batch, split)
        D = rng.integers(self.DMIN, self.DMAX + 1, size=batch)
        distract = rng.integers(0, 256, size=(batch, T))
        for b in range(batch):
            _put_word(obs[0, b], 7, word[b], 8)
            obs[0, b, 0, 7, 0] = 1.0                            # red marker: this is the word to keep
            for t in range(1, D[b] + 1):
                if rng.random() < 0.5:
                    _put_word(obs[t, b], 7, distract[b, t], 8)  # same place and look, but unmarked
            cue = D[b] + 1
            obs[cue, b, 2, 15, :] = 1.0                         # blue bar at the bottom: answer now
            target[cue, b] = to_bits(word[b])
            mask[cue, b] = 1.0
        return {"obs": obs, "target": target, "mask": mask}


class CrossMem(SupervisedTask):
    ROWS = (2, 5, 8, 11)
    DMIN, DMAX, QUERIES = 2, 8, 3

    def __init__(self):
        self.spec = TaskSpec("crossmem", "memory", "supervised", "bits", WORD,
                             seq_len=1 + self.DMAX + self.QUERIES, chance=0.0, needs_memory=True,
                             description="4 words in the left half, 2-8 blank frames, then the right half "
                                         "points at a row (3 queries) -> that word; test words held out")

    def sample(self, batch, rng, split="train"):
        T = self.spec.seq_len
        obs = np.zeros((T, batch, 3, 16, 16), np.float32)
        target = np.zeros((T, batch, WORD), np.float32)
        mask = np.zeros((T, batch), np.float32)
        words = _words(rng, (batch, len(self.ROWS)), split)
        D = rng.integers(self.DMIN, self.DMAX + 1, size=batch)
        for b in range(batch):
            for i, r in enumerate(self.ROWS):
                _put_word(obs[0, b], r, words[b, i], 0)         # left half, columns 0..7
                obs[0, b, 0, r, 8] = 1.0                        # red marker: a word is stored in this row
            for q in range(self.QUERIES):
                t = 1 + D[b] + q
                i = int(rng.integers(len(self.ROWS)))
                obs[t, b, 2, self.ROWS[i], 15] = 1.0            # right edge: blue pointer at the asked row
                target[t, b] = to_bits(words[b, i])
                mask[t, b] = 1.0
        return {"obs": obs, "target": target, "mask": mask}
