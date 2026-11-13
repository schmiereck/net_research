"""Do the robot_shape_at nets use the place command? Per net (mean over seeds 0-2, gazeshape_test): accuracy with the
own place, accuracy when the command names ANOTHER body of the scene (scored against the first), share of
predictions that change with the command, and the first two restricted to bodies up to ring 5.

    python scripts/shape_at_swap.py
"""
import sys, numpy as np, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from netresearch.tasks import make_task
from netresearch.train import load_checkpoint, run_sequence
for name in ["cnn+cmd", "vit+cmd", "layer_s+cell", "hier_s+cell", "cnn+cmd+rez3", "vit+cmd+rez3", "layer_s+cell+rez3", "hier_s+cell+rez3"]:
    tn = "robot_shape_at_f32" if "rez" in name else "robot_shape_at"
    t = make_task(tn); d = t._load("gazeshape_test"); n = len(d["obs"]); i = np.arange(n)
    c = d["cells"].astype(np.int64); ring = np.abs(c[:, :6].reshape(n, 3, 2)).max(2)
    res = []
    for s in range(3):
        m = load_checkpoint(name, tn, s)
        P = []
        for k in range(3):
            b = t.make(d, i, np.full(n, k))
            with torch.no_grad():
                lg, _ = run_sequence(m, torch.tensor(b["obs"]), cmd=torch.tensor(b["cmd"]))
            P.append(lg[0][:, t.spec.out_slice].argmax(-1).numpy())
        P = np.stack(P, 1); S = c[:, 9:12]
        own = (P == S).mean(); swapped = (np.roll(P, 1, 1) == S).mean(); change = (P != np.roll(P, 1, 1)).mean()
        inn = ring <= 5
        res.append([own, swapped, change, (P == S)[inn].mean(), (np.roll(P, 1, 1) == S)[inn].mean()])
    print(f"{name:<20}", np.round(np.mean(res, 0), 2))
