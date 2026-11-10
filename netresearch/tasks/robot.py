"""Robot perception tasks (bridge to the robot project rdf_thalamus_sml, stage a): fovea images of the MuJoCo
arm scene with labels, exported there by src/pc_cvnn/export_netresearch.py into data/robot/.

The image is the 16 x 16 hex fovea of the robot's overview camera (RGB as floats 0..1, NOT binary; outer cells
sample further out, so the periphery is compressed). The arm is visible. Objects: red / green / blue cubes,
an L and a U, plus target markers.
    robot_gaze   where is the red cube relative to the image centre? (dx, dy) in fovea cells = the gaze shift
                 that centres it
    robot_reach  hand and red cube are in view: (dx, dy) = cell of the cube - cell of the grasp point
Output as the servo task (tasks/servo.py): two signed 4-bit steps in the 8 "bits" outputs. Train and test
come from separate scenes (separate random streams in the export).
"""
from pathlib import Path

import numpy as np

from ..spec import TaskSpec
from .base import SupervisedTask
from .servo import command_bits

DATA = Path(__file__).resolve().parents[2] / "data" / "robot"


class _Robot(SupervisedTask):
    kind, text = "", ""

    def __init__(self):
        self.spec = TaskSpec("robot_" + self.kind, "robot", "supervised", "bits", 8, seq_len=1, chance=0.0,
                             description=self.text)
        self._data = {}

    def _load(self, split):
        if split not in self._data:
            p = DATA / f"{self.kind}_{split}.npz"
            if not p.exists():
                raise FileNotFoundError(f"{p} is missing: export it in the robot project with "
                                        f"src/pc_cvnn/export_netresearch.py --out <NetResearch>/data/robot")
            d = np.load(p)
            self._data[split] = (d["obs"], command_bits(d["target"][:, 0], d["target"][:, 1]))
        return self._data[split]

    def sample(self, batch, rng, split="train"):
        obs, tgt = self._load(split)
        i = rng.integers(0, len(obs), size=batch)
        return {"obs": (obs[i].astype(np.float32) / 255.0)[None], "target": tgt[i][None],
                "mask": np.ones((1, batch), np.float32)}


class RobotFind(SupervisedTask):
    """Look at the object the COMMAND names. Images with all three cubes in view (gazemulti); the command is
    the colour of the wanted cube as a vector (its RGB in the first 3 of N_CMD values, a continuous address,
    not a class id); output = the gaze shift (dx, dy) that centres that cube. Without the command the task is
    ambiguous (three possible answers). held_out(k) gives the same for the L and the U (colours never
    commanded in training): does the address generalise to a new object?"""
    CUBES = 3

    def __init__(self):
        self.spec = TaskSpec("robot_find", "robot", "supervised", "bits", 8, seq_len=1, chance=0.0,
                             description="robot fovea image + command (colour of the wanted cube) -> gaze shift "
                                         "(dx, dy) that centres it")
        self._data = {}

    def _load(self, split):
        if split not in self._data:
            self._data[split] = dict(np.load(DATA / f"gazemulti_{split}.npz"))
        return self._data[split]

    def _batch(self, d, i, k):
        from ..models import N_CMD
        c = d["cells"][i].astype(np.int64)
        cmd = np.zeros((len(i), N_CMD), np.float32)
        cmd[:, :3] = d["colors"][k]
        r = np.arange(len(i))
        return {"obs": (d["obs"][i].astype(np.float32) / 255.0)[None], "cmd": cmd[None],
                "target": command_bits(c[r, 2 * k], c[r, 2 * k + 1])[None],
                "mask": np.ones((1, len(i)), np.float32)}

    def sample(self, batch, rng, split="train"):
        d = self._load(split)
        return self._batch(d, rng.integers(0, len(d["obs"]), size=batch), rng.integers(0, self.CUBES, size=batch))

    def held_out(self, k, split="test"):
        """All examples of the split in which object k (3 = L, 4 = U; 0..2 = the cubes) is in view."""
        d = self._load(split)
        i = np.flatnonzero(d["cells"][:, 2 * k] > -128)
        return self._batch(d, i, np.full(len(i), k))


class RobotFindColor(SupervisedTask):
    """robot_find with RANDOM cube colours per scene (gazecolor): the command is the colour of the wanted cube
    (RGB in the first 3 command values), so it is a continuous address and not one of three fixed codes. The
    hue band 0.25-0.40 (green) never occurs in training; held_out() gives test scenes in which the commanded
    cube has a hue from that band (gazecolorheld): does the address generalise to a colour never seen?"""

    def __init__(self):
        self.spec = TaskSpec("robot_findc", "robot", "supervised", "bits", 8, seq_len=1, chance=0.0,
                             description="robot fovea image, cubes in random colours + command (colour of the "
                                         "wanted cube) -> gaze shift (dx, dy) that centres it")
        self._data = {}

    def _load(self, name):
        if name not in self._data:
            self._data[name] = dict(np.load(DATA / f"{name}.npz"))
        return self._data[name]

    @staticmethod
    def _batch(d, i, k):
        from ..models import N_CMD
        c = d["cells"][i].astype(np.int64)
        r = np.arange(len(i))
        cmd = np.zeros((len(i), N_CMD), np.float32)
        cmd[:, :3] = (c[r[:, None], 6 + 3 * k[:, None] + np.arange(3)] + 128) / 255.0
        return {"obs": (d["obs"][i].astype(np.float32) / 255.0)[None], "cmd": cmd[None],
                "target": command_bits(c[r, 2 * k], c[r, 2 * k + 1])[None],
                "mask": np.ones((1, len(i)), np.float32)}

    files = ("gazecolor", "gazecolorheld_test")

    def make(self, d, i, k):
        return self._batch(d, i, k)

    def sample(self, batch, rng, split="train"):
        d = self._load(f"{self.files[0]}_{split}")
        return self.make(d, rng.integers(0, len(d["obs"]), size=batch), rng.integers(0, 3, size=batch))

    def held_out(self, other=False):
        """Test scenes with one cube in a held-out hue; the command names that cube (other=True: a cube with a
        trained hue in the same scenes, as the control)."""
        d = self._load(self.files[1])
        k = d["cells"][:, 15].astype(np.int64)
        return self.make(d, np.arange(len(k)), (k + 1) % 3 if other else k)


class RobotFindImage(RobotFindColor):
    """robot_findc, but the wanted cube is named by a PICTURE of it (batch entry "ref": the cube alone in
    another scene, the gaze on it) instead of its colour. A net with an address encoder ("+ref") has to form
    its own address of the object from the picture. The batch also carries the colour command ("cmd"), so a
    "+cmd" net trained on the same scenes is the reference for "address given from outside"."""
    files = ("gazecolorref", "gazecolorrefheld_test")

    def __init__(self):
        super().__init__()
        self.spec = TaskSpec("robot_findi", "robot", "supervised", "bits", 8, seq_len=1, chance=0.0,
                             description="robot fovea image + a picture of the wanted cube -> gaze shift "
                                         "(dx, dy) that centres it")

    def make(self, d, i, k):
        b = self._batch(d, i, k)
        b["ref"] = (d["refs"][i, k].astype(np.float32) / 255.0)[None]
        return b


class RobotFindShape(RobotFindColor):
    """Three objects of the SAME colour and DIFFERENT shape (cube, L, U, T, cross; any rotation); the wanted one
    is shown as a picture ("ref": the object alone in another scene, in another rotation; one of two views,
    drawn at random in training). Only the shape tells the objects apart, so the address a "+ref" net forms
    has to carry the form. The Y never occurs in training (held_out). "cmd" carries the shape as a one-hot
    code (first 6 command values): a "+cmd" net on the same scenes is the reference "name given from outside"
    (it cannot know the Y)."""
    files = ("gazeshape", "gazeshapeheld_test")
    HELD_COL = 12

    def __init__(self):
        super().__init__()
        self.spec = TaskSpec("robot_finds", "robot", "supervised", "bits", 8, seq_len=1, chance=0.0,
                             description="robot fovea image, three shapes of one colour + a picture of the "
                                         "wanted one -> gaze shift (dx, dy) that centres it")
        self._rng = np.random.default_rng(0)

    def make(self, d, i, k, view=None):
        from ..models import N_CMD
        c = d["cells"][i].astype(np.int64)
        r = np.arange(len(i))
        cmd = np.zeros((len(i), N_CMD), np.float32)
        cmd[r, c[r, 9 + k]] = 1.0
        v = self._rng.integers(0, 2, size=len(i)) if view is None else np.full(len(i), view)
        return {"obs": (d["obs"][i].astype(np.float32) / 255.0)[None], "cmd": cmd[None],
                "ref": (d["refs"][i, k, v].astype(np.float32) / 255.0)[None],
                "target": command_bits(c[r, 2 * k], c[r, 2 * k + 1])[None],
                "mask": np.ones((1, len(i)), np.float32)}

    def held_out(self, other=False, view=0):
        d = self._load(self.files[1])
        k = d["cells"][:, self.HELD_COL].astype(np.int64)
        return self.make(d, np.arange(len(k)), (k + 1) % 3 if other else k, view)


class RobotLook(SupervisedTask):
    """Look and compare, stage 1: "is it this one?". The image is the fovea centred on ONE of the three
    same-coloured shapes of a search scene (the others around it); "ref" is a picture of an object (alone, other
    scene, other rotation): the same object in half of the cases, another object of the scene otherwise.
    Output: 2 classes, 1 = it is the shown object. For nets with an address encoder ("+ref")."""
    name, T = "robot_look", 1

    def __init__(self):
        self.spec = TaskSpec(self.name, "robot", "supervised", "class", 2, seq_len=self.T, chance=self.chance,
                             needs_memory=self.T > 1, description=self.text)
        self._data = {}

    chance = 0.5
    text = "robot fovea on one of three shapes + a picture of an object -> is it the shown object? (2 classes)"

    def _load(self, name):
        if name not in self._data:
            self._data[name] = dict(np.load(DATA / f"{name}.npz"))
        return self._data[name]

    @staticmethod
    def _img(a):
        return a.astype(np.float32) / 255.0

    def make(self, d, i, k, j, v):
        """Candidate k of scene i in view, the picture shows object j (view v)."""
        return {"obs": self._img(d["cands"][i, k])[None], "ref": self._img(d["refs"][i, j, v])[None],
                "target": (k == j).astype(np.int64)[None], "mask": np.ones((1, len(i)), np.float32)}

    def _pairs(self, n, rng, k=None):
        k = rng.integers(0, 3, size=n) if k is None else k
        same = rng.random(n) < 0.5
        return k, np.where(same, k, (k + rng.integers(1, 3, size=n)) % 3), rng.integers(0, 2, size=n)

    def sample(self, batch, rng, split="train"):
        d = self._load(f"gazeshape_{split}")
        return self.make(d, rng.integers(0, len(d["obs"]), size=batch), *self._pairs(batch, rng))

    def held_out(self, rng, on_y=True):
        """Scenes with the Y (never trained). on_y: the Y is looked at (picture: the Y or another object);
        else another object is looked at (picture: itself or another one, possibly the Y)."""
        d = self._load("gazeshapeheld_test")
        y = d["cells"][:, 12].astype(np.int64)
        n = len(y)
        k = y if on_y else (y + rng.integers(1, 3, size=n)) % 3
        return self.make(d, np.arange(n), *self._pairs(n, rng, k))


class RobotLookMem(RobotLook):
    """Look and compare, stage 2, with memory and without any extra input port: step 0 shows the picture of the
    wanted object as the image; steps 1-3 show the fovea on the three shapes of the search scene one after the
    other. At every candidate step: is it the object shown at the beginning? (exactly one of the three is).
    The net has to keep what it saw at step 0. chance = 2/3, the accuracy of "always no"."""
    name, T, chance = "robot_lookmem", 4, 2 / 3
    text = ("picture of an object, then the fovea on three shapes one after the other -> at each: is it the one "
            "shown first? (needs memory)")

    def seq(self, d, i, w, v):
        obs = np.stack([self._img(d["refs"][i, w, v])] + [self._img(d["cands"][i, k]) for k in range(3)])
        tgt = np.stack([np.zeros(len(i), np.int64)] + [(w == k).astype(np.int64) for k in range(3)])
        mask = np.ones((4, len(i)), np.float32)
        mask[0] = 0.0
        return {"obs": obs, "target": tgt, "mask": mask}

    def sample(self, batch, rng, split="train"):
        d = self._load(f"gazeshape_{split}")
        return self.seq(d, rng.integers(0, len(d["obs"]), size=batch), rng.integers(0, 3, size=batch),
                        rng.integers(0, 2, size=batch))

    def held_out(self, rng, on_y=True):
        """Scenes with the Y: the Y is the wanted object (on_y) or another object of the scene is."""
        d = self._load("gazeshapeheld_test")
        y = d["cells"][:, 12].astype(np.int64)
        w = y if on_y else (y + rng.integers(1, 3, size=len(y))) % 3
        return self.seq(d, np.arange(len(y)), w, rng.integers(0, 2, size=len(y)))


class RobotGaze(_Robot):
    kind, text = "gaze", "robot fovea image -> gaze shift (dx, dy) in cells that centres the red cube"


class RobotReach(_Robot):
    kind, text = "reach", "robot fovea image with hand and red cube -> step (dx, dy) in cells from hand to cube"
