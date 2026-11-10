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

    def sample(self, batch, rng, split="train"):
        d = self._load(f"gazecolor_{split}")
        return self._batch(d, rng.integers(0, len(d["obs"]), size=batch), rng.integers(0, 3, size=batch))

    def held_out(self, other=False):
        """Test scenes with one cube in a held-out hue; the command names that cube (other=True: a cube with a
        trained hue in the same scenes, as the control)."""
        d = self._load("gazecolorheld_test")
        k = d["cells"][:, 15].astype(np.int64)
        return self._batch(d, np.arange(len(k)), (k + 1) % 3 if other else k)


class RobotGaze(_Robot):
    kind, text = "gaze", "robot fovea image -> gaze shift (dx, dy) in cells that centres the red cube"


class RobotReach(_Robot):
    kind, text = "reach", "robot fovea image with hand and red cube -> step (dx, dy) in cells from hand to cube"
