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


def _distract(w, rng):
    """For every word a different one: half of them a random other word, half with 1-2 bits flipped."""
    flips = (1 << rng.integers(0, WORD, size=w.shape)) | (1 << rng.integers(0, WORD, size=w.shape))
    return np.where(rng.random(w.shape) < 0.5, w ^ flips, (w + rng.integers(1, 256, size=w.shape)) % 256)


def _place(frames, words, rng, shift, row=5, col=4, rows=(1, 15)):
    """frames [B,3,16,16]: word b as 8 white pixels; at (row, col), or with shift at a random place in rows.
    A blue line under the word marks where it starts and ends: without it a shifted word would be ambiguous
    (00000110 looks like 00001100 one pixel further left)."""
    n = len(words)
    r = rng.integers(*rows, size=n) if shift else np.full(n, row)
    c = rng.integers(0, 16 - WORD + 1, size=n) if shift else np.full(n, col)
    bits = ((words[:, None] >> np.arange(WORD - 1, -1, -1)) & 1).astype(np.float32)
    for i in range(WORD):
        frames[np.arange(n), :, r, c + i] = bits[:, i, None]
        frames[np.arange(n), 2, r + 1, c + i] = 1.0
    return bits


class Match(SupervisedTask):
    """Look and compare without robot data: frame 0 shows a word (green marker), frames 1-3 show three
    candidate words, exactly one of them is the word of frame 0. At each candidate: is it the same? (2 classes)
    Distractors: half of them random words, half the shown word with 1-2 bits flipped. The net has to keep the
    word AND compare it with what it sees (recall / delay only ask to repeat it). chance = 2/3 ("always no").
    SHIFT: every frame puts its word at a random place, so the comparison cannot be done pixel by pixel."""
    name, SHIFT = "match", False

    def __init__(self):
        self.spec = TaskSpec(self.name, "memory", "supervised", "class", 2, seq_len=4, chance=2 / 3,
                             needs_memory=True,
                             description="a word, then three candidate words -> at each: is it the first one?"
                                         + (" (every word at a random place)" if self.SHIFT else ""))

    def draw(self, batch, rng, split):
        """words [B, 4] (the shown word, three candidates), right [B] (index of the equal candidate)."""
        w = _words(rng, batch, split)
        cand = _distract(w[:, None].repeat(3, 1), rng)
        right = rng.integers(0, 3, size=batch)
        cand[np.arange(batch), right] = w
        return np.concatenate([w[:, None], cand], 1), right

    def sample(self, batch, rng, split="train"):
        words, right = self.draw(batch, rng, split)
        obs = np.zeros((4, batch, 3, 16, 16), np.float32)
        obs[0, :, 1, 0, 0] = 1.0                                            # green marker: the shown word
        for t in range(4):
            _place(obs[t], words[:, t], rng, self.SHIFT)
        target = np.zeros((4, batch), np.int64)
        target[1:] = (np.arange(3)[:, None] == right[None]).astype(np.int64)
        mask = np.ones((4, batch), np.float32)
        mask[0] = 0.0
        return {"obs": obs, "target": target, "mask": mask}


class MatchShift(Match):
    name, SHIFT = "match_shift", True


# ---- match_shift taken apart: which part breaks? (every task with SHIFT = word at a random place, and a
# ---- control with the word at a fixed place)
class ReadShift(SupervisedTask):
    """Part 1, reading without memory: one word somewhere in the image -> the word (8 bits)."""
    name, SHIFT = "read_shift", True

    def __init__(self):
        self.spec = TaskSpec(self.name, "patterns", "supervised", "bits", WORD, seq_len=1, chance=0.0,
                             description="one word at a random place -> the word")

    def sample(self, batch, rng, split="train"):
        obs = np.zeros((1, batch, 3, 16, 16), np.float32)
        bits = _place(obs[0], _words(rng, batch, split), rng, self.SHIFT)
        return {"obs": obs, "target": bits[None], "mask": np.ones((1, batch), np.float32)}


class KeepShift(SupervisedTask):
    """Part 2, keeping: frame 0 a word (random place with SHIFT), frame 1 blank, frame 2 a blue cue -> the word."""
    name, SHIFT = "keep_shift", True

    def __init__(self):
        self.spec = TaskSpec(self.name, "memory", "supervised", "bits", WORD, seq_len=3, chance=0.0,
                             needs_memory=True, description="a word"
                             + (" at a random place" if self.SHIFT else "") + ", a blank frame, a cue -> the word")

    def sample(self, batch, rng, split="train"):
        obs = np.zeros((3, batch, 3, 16, 16), np.float32)
        bits = _place(obs[0], _words(rng, batch, split), rng, self.SHIFT)
        obs[2, :, 2, 0, 0] = 1.0
        target = np.zeros((3, batch, WORD), np.float32)
        target[2] = bits
        mask = np.zeros((3, batch), np.float32)
        mask[2] = 1.0
        return {"obs": obs, "target": target, "mask": mask}


class KeepFixed(KeepShift):
    name, SHIFT = "keep_fixed", False


class SameShift(SupervisedTask):
    """Part 3, comparing without memory: two words in ONE image (upper half, lower half), equal in half of the
    cases -> same? (2 classes). SHIFT: each at a random place of its half; else rows 4 and 11, column 4."""
    name, SHIFT = "same_shift", True

    def __init__(self):
        self.spec = TaskSpec(self.name, "patterns", "supervised", "class", 2, seq_len=1, chance=0.5,
                             description="two words in one image" + (" at random places" if self.SHIFT else "")
                                         + " -> are they the same?")

    def sample(self, batch, rng, split="train"):
        w = _words(rng, batch, split)
        same = rng.random(batch) < 0.5
        w2 = np.where(same, w, _distract(w, rng))
        obs = np.zeros((1, batch, 3, 16, 16), np.float32)
        _place(obs[0], w, rng, self.SHIFT, row=4, rows=(0, 7))
        _place(obs[0], w2, rng, self.SHIFT, row=11, rows=(8, 15))
        return {"obs": obs, "target": same.astype(np.int64)[None], "mask": np.ones((1, batch), np.float32)}


class SameFixed(SameShift):
    name, SHIFT = "same_fixed", False
