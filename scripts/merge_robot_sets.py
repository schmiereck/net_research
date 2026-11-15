"""Mix two exported robot scene sets into one: the first n scenes of each, a then b.

    python scripts/merge_robot_sets.py gazeshapec gazeshapeu gazeshapem --train 24000 --test 1500

Parts of a set exported in several processes (<name>_<split>_p<k>.npz) are joined first. The scenes keep their
order (first all of a, then all of b), so the first half of the mixed test set is the test set of a.
Copy the result to the shared folder of the workers by hand (<share>/data/robot).
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks.robot import data_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "data" / "robot"


def load(name, split, n):
    files = [data_path(f"{name}_{split}.npz")] + sorted(ROOT.glob(f"{name}_{split}_p[0-9]*.npz"))
    parts = [np.load(f) for f in files if Path(f).exists()]
    keys = [k for k in parts[0].files if k != "colors"]
    d = {k: np.concatenate([p[k] for p in parts])[:n] for k in keys}
    assert len(d["obs"]) == n, f"{name}_{split}: only {len(d['obs'])} scenes"
    return d, parts[0]["colors"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("out")
    ap.add_argument("--train", type=int, default=24000)
    ap.add_argument("--test", type=int, default=1500)
    a = ap.parse_args()
    for split, n in (("train", a.train), ("test", a.test)):
        (x, colors), (y, _) = load(a.a, split, n), load(a.b, split, n)
        keys = [k for k in x if k in y]
        p = ROOT / f"{a.out}_{split}.npz"
        np.savez_compressed(p, colors=colors, **{k: np.concatenate([x[k], y[k]]) for k in keys})
        print(p.name, 2 * n, "scenes, keys", keys, flush=True)


if __name__ == "__main__":
    sys.exit(main())
