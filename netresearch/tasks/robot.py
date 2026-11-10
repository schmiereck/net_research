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


class RobotGaze(_Robot):
    kind, text = "gaze", "robot fovea image -> gaze shift (dx, dy) in cells that centres the red cube"


class RobotReach(_Robot):
    kind, text = "reach", "robot fovea image with hand and red cube -> step (dx, dy) in cells from hand to cube"
