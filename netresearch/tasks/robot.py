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


def data_path(name):
    """A robot data file: in the repository (data/robot), else in the shared folder of the workers
    (<share>/data/robot; large sets that are not committed, e.g. gazeshape*). The share is $NETRESEARCH_SHARE or
    the usual place in one of the OneDrive folders of this machine."""
    import os
    drives = [Path.home() / "OneDrive", *(Path(os.environ[k]) for k in
                                          ("OneDrive", "OneDriveConsumer", "OneDriveCommercial") if os.environ.get(k))]
    shares = [Path(os.environ["NETRESEARCH_SHARE"])] if os.environ.get("NETRESEARCH_SHARE") else []
    shares += [d / docs / "#Projekte" / "NetResearch" for d in drives for docs in ("Dokumente", "Documents")]
    roots = list(dict.fromkeys([DATA, *(r / "data" / "robot" for r in shares)]))
    for root in roots:
        if (root / name).exists():
            return root / name
    raise FileNotFoundError(f"{name} not found in: " + ", ".join(str(r) for r in roots))


class _Robot(SupervisedTask):
    kind, text = "", ""

    def __init__(self):
        self.spec = TaskSpec("robot_" + self.kind, "robot", "supervised", "bits", 8, seq_len=1, chance=0.0,
                             description=self.text)
        self._data = {}

    def _load(self, split):
        if split not in self._data:
            p = data_path(f"{self.kind}_{split}.npz")
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
            self._data[split] = dict(np.load(data_path(f"gazemulti_{split}.npz")))
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
            self._data[name] = dict(np.load(data_path(f"{name}.npz")))
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


def _fine(d):
    if "f32" not in d:
        raise FileNotFoundError("gazeshape*.npz without the dense view (f32): export it again in the robot project")
    return d["f32"]


class RobotFindShapeF32(RobotFindShape):
    """robot_finds with the search scene sampled twice as densely (32 x 32 over the same field of view, key
    "f32"); the picture of the wanted object stays 16 x 16. Needs a net with a front stage ("+rezN")."""

    def __init__(self):
        super().__init__()
        self.spec.name = "robot_finds_f32"

    def make(self, d, i, k, view=None):
        b = super().make(d, i, k, view)
        b["obs"] = (_fine(d)[i].astype(np.float32) / 255.0)[None]
        return b


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
            self._data[name] = dict(np.load(data_path(f"{name}.npz")))
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


class RobotShape(SupervisedTask):
    """Resolution test: the fovea looks at one of three same-coloured bodies -> its shape (5 classes: cube, L, U,
    T, cross). The same scenes in four samplings (data/robot/shapeview_*, key VIEW):
        robot_shape      obs  16 x 16, the fovea as everywhere else (4 px per cell)
        robot_shape_z2   z2   16 x 16, zoomed in 2x (half the field of view)
        robot_shape_z4   z4   16 x 16, zoomed in 4x
        robot_shape_f32  f32  32 x 32 over the field of view of obs (twice as dense); needs a net with a front
                              stage ("+retN", models.Retina)."""
    name, VIEW, FILE, TRAIN = "robot_shape", "obs", "shapeview", None

    def __init__(self):
        self.spec = TaskSpec(self.name, "robot", "supervised", "class", 5, seq_len=1, chance=0.2,
                             description=f"robot fovea ({self.VIEW}) on one of three same-coloured bodies -> its shape")
        self._data = {}

    def sample(self, batch, rng, split="train"):
        if split not in self._data:
            p = data_path(f"{self.TRAIN if split == 'train' and self.TRAIN else self.FILE + '_' + split}.npz")
            if not p.exists():
                raise FileNotFoundError(f"{p} is missing: export it in the robot project (task {self.FILE})")
            d = np.load(p)
            self._data[split] = (d[self.VIEW], d["cells"][:, 0].astype(np.int64))
        obs, tgt = self._data[split]
        i = rng.integers(0, len(obs), size=batch)
        return {"obs": (obs[i].astype(np.float32) / 255.0)[None], "target": tgt[i][None],
                "mask": np.ones((1, batch), np.float32)}


class RobotShapeZ2(RobotShape):
    name, VIEW = "robot_shape_z2", "z2"


class RobotShapeZ4(RobotShape):
    name, VIEW = "robot_shape_z4", "z4"


class RobotShapeF32(RobotShape):
    name, VIEW = "robot_shape_f32", "f32"


class RobotShapeEdge(RobotShape):
    """The body lies anywhere in the field of view, up to 7 cells from the centre (data shapeedge_*; cells[:, 1]
    = ring = distance from the centre in cells; beyond 5 cells the fovea gets coarser). Scores by ring:
    scripts/shape_ring_eval.py."""
    name, FILE = "robot_shape_edge", "shapeedge"


class RobotShapeEdgeF32(RobotShapeEdge):
    name, VIEW = "robot_shape_edge_f32", "f32"


class RobotShapeEdgeBig(RobotShapeEdge):
    """48000 training images in place of 12000, same test set."""
    name, TRAIN = "robot_shape_edge_big", "shapeedge48_train"


class RobotShapeEdgeF32Big(RobotShapeEdgeF32):
    name, TRAIN = "robot_shape_edge_f32_big", "shapeedge48_train"


class RobotGaze(_Robot):
    kind, text = "gaze", "robot fovea image -> gaze shift (dx, dy) in cells that centres the red cube"


class RobotReach(_Robot):
    """Data: reachcells_* (since 2026-11-12; the same generator as reach_*, other random scenes, plus "cells" =
    column, row of the hand and of the cube, which robot_reach_parts asks for)."""
    kind, text = "reachcells", "robot fovea image with hand and red cube -> step (dx, dy) in cells from hand to cube"

    name = "robot_reach"

    def __init__(self):
        super().__init__()
        self.spec.name = self.name

    def _load(self, split):
        if split not in self._data:
            d = np.load(data_path(f"{self.kind if split == 'train' else 'reachcells'}_{split}.npz"))
            self._data[split] = (d["obs"], command_bits(d["target"][:, 0], d["target"][:, 1]))
        return self._data[split]


class RobotReachBig(RobotReach):
    """robot_reach with 48000 training images (reachcells48_train; its first 12000 are reachcells_train), same test set."""
    kind, name = "reachcells48", "robot_reach_big"


def _nibbles(v):
    """ints 0..15 [..., n] -> bits [..., 4n] (MSB first)."""
    return ((v[..., None] >> np.arange(3, -1, -1)) & 1).reshape(*v.shape[:-1], -1).astype(np.float32)


class RobotReachParts(SupervisedTask):
    """Intermediate quantities of robot_reach as an auxiliary task: the same images -> cell (column, row) of the
    hand and cell of the cube, 16 bits in the SYMBOL area, so that it can be trained together with robot_reach
    (bits area). robot_reach = cube - hand."""

    name, train = "robot_reach_parts", "reachcells"

    def __init__(self):
        self.spec = TaskSpec(self.name, "robot", "supervised", "bits", 16, seq_len=1, chance=0.0,
                             role="symbol", parts={"hand": (0, 8), "cube": (8, 16)},
                             description="robot fovea image with hand and red cube -> cell of "
                                         "the hand and cell of the cube (auxiliary task)")
        self._data = {}

    def sample(self, batch, rng, split="train"):
        if split not in self._data:
            d = np.load(data_path(f"{self.train if split == 'train' else 'reachcells'}_{split}.npz"))
            self._data[split] = (d["obs"], _nibbles(d["cells"].astype(np.int64)))
        obs, tgt = self._data[split]
        i = rng.integers(0, len(obs), size=batch)
        return {"obs": (obs[i].astype(np.float32) / 255.0)[None], "target": tgt[i][None],
                "mask": np.ones((1, batch), np.float32)}


class RobotReachPartsBig(RobotReachParts):
    name, train = "robot_reach_parts_big", "reachcells48"


def place_code(dx, dy):
    """A place in the field of view (dx, dy in cells, -8..7) as a command: per axis 8 values, each a bump
    around one of 8 evenly spaced centres (a population code), so that near places get similar commands."""
    from ..models import N_CMD
    ctr = np.arange(-7, 8, 2)[None]
    bump = lambda v: np.exp(-0.5 * ((np.asarray(v, np.float32)[:, None] - ctr) / 1.5) ** 2)
    out = np.concatenate([bump(dx), bump(dy)], 1).astype(np.float32)
    assert out.shape[1] == N_CMD
    return out


class RobotShapeAt(RobotFindColor):
    """Diagnosis for robot_finds: the search scene itself (three bodies of one colour and different shape) and,
    as the command, the PLACE of one of them (its step from the centre in cells, place_code) -> the shape of
    that body (5 classes). No picture, no comparison, no gaze step: only "read the shape at a named place" in
    the scene the search runs on. Reference: robot_shape_edge (one body alone, same field of view)."""
    files = ("gazeshape", "gazeshapeheld_test")
    name, VIEW = "robot_shape_at", "obs"

    def __init__(self):
        self.spec = TaskSpec(self.name, "robot", "supervised", "class", 5, seq_len=1, chance=0.2,
                             description=f"search scene ({self.VIEW}) + place of one of the three bodies -> its shape")
        self._data = {}

    def make(self, d, i, k):
        if self.VIEW not in d:
            raise FileNotFoundError(f"gazeshape*.npz without the view {self.VIEW}: export it again")
        c = d["cells"][i].astype(np.int64)
        r = np.arange(len(i))
        return {"obs": (d[self.VIEW][i].astype(np.float32) / 255.0)[None],
                "cmd": place_code(c[r, 2 * k], c[r, 2 * k + 1])[None],
                "target": c[r, 9 + k][None], "mask": np.ones((1, len(i)), np.float32)}

    def held_out(self, other=False):
        raise NotImplementedError("the Y has no class here")


class RobotShapeAtF32(RobotShapeAt):
    name, VIEW = "robot_shape_at_f32", "f32"


class RobotFindShapeParts(RobotFindShape):
    """Intermediate quantities of robot_finds as an auxiliary task (same scenes, same picture of the wanted
    object): for the three objects ordered from left to right (then top to bottom) the gaze step to each
    (3 x 8 bits) and the shape of each (3 x 3 bits), then the shape shown in the picture (3 bits): 36 bits in
    the SYMBOL area. robot_finds = the step of the object whose shape is the shown one."""

    def __init__(self):
        super().__init__()
        self.spec = TaskSpec("robot_finds_parts", "robot", "supervised", "bits", 36, seq_len=1, chance=0.0,
                             role="symbol", parts={"step1": (0, 8), "step2": (8, 16), "step3": (16, 24),
                                                   "shape1": (24, 27), "shape2": (27, 30), "shape3": (30, 33),
                                                   "shown": (33, 36)}, description="robot_finds scene + picture -> step and shape of each "
                                                        "of the three objects, shape in the picture (auxiliary)")

    def make(self, d, i, k, view=None):
        b = super().make(d, i, k, view)
        c = d["cells"][i].astype(np.int64)
        r = np.arange(len(i))[:, None]
        pos, shp = c[:, :6].reshape(-1, 3, 2), c[:, 9:12]
        order = np.lexsort((pos[:, :, 1], pos[:, :, 0]), axis=1)                # by column, then row
        pos, shp = pos[r, order], shp[r, order]
        steps = np.concatenate([command_bits(pos[:, j, 0], pos[:, j, 1]) for j in range(3)], 1)
        three = lambda v: ((v[..., None] >> np.arange(2, -1, -1)) & 1).reshape(len(i), -1).astype(np.float32)
        b["target"] = np.concatenate([steps, three(shp), three(c[r[:, 0], 9 + k][:, None])], 1)[None]
        return b


class RobotFindShapePartsF32(RobotFindShapeParts):
    def __init__(self):
        super().__init__()
        self.spec.name = "robot_finds_parts_f32"

    def make(self, d, i, k, view=None):
        b = super().make(d, i, k, view)
        b["obs"] = (_fine(d)[i].astype(np.float32) / 255.0)[None]
        return b
