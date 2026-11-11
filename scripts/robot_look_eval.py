"""Look and compare (robot_look, robot_lookmem): accuracy on the test scenes and on scenes with the Y.

    python scripts/robot_look_eval.py --task robot_look    [--models vit+ref cnn+ref ...] [--seeds 0 1 2]
    python scripts/robot_look_eval.py --task robot_lookmem [--models layer_s_sp4 gru ...]

    test    trained shapes
    y       scenes with the Y (never trained), the Y looked at (robot_look) / wanted (robot_lookmem)
    other   the same scenes, another object looked at / wanted
Per set: acc = share of right yes/no answers; yes / no = accuracy on the cases whose answer is yes / no;
robot_lookmem also seq = share of sequences with all three answers right (= the right object picked).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import make_task  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence, to_t  # noqa: E402


def score(model, b, spec):
    with torch.no_grad():
        lg, _ = run_sequence(model, b["obs"], ref=b.get("ref"))
    p = lg[..., spec.out_slice].argmax(-1)
    t, m = b["target"], b["mask"] > 0
    ok = (p == t)
    r = {"acc": float(ok[m].float().mean()), "yes": float(ok[m & (t == 1)].float().mean()),
         "no": float(ok[m & (t == 0)].float().mean())}
    if t.shape[0] > 1:
        r["seq"] = float((ok | ~m).all(0).float().mean())
    return {k: round(v, 4) for k, v in r.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", default="robot_look", choices=["robot_look", "robot_lookmem"])
    ap.add_argument("--models", nargs="+", default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--ckpt", default=None, help="checkpoint name in place of the task name (curriculum runs)")
    a = ap.parse_args()
    models = a.models or (["vit+ref", "cnn+ref", "layer_s_sp4+cell+ref"] if a.task == "robot_look" else
                          ["layer_s_sp4", "layer_s", "hier_s", "layer_s_am4", "gru", "attnmem", "vit"])
    task = make_task(a.task)
    rng = np.random.default_rng(0)
    sets = {"test": to_t(task.sample(3000, rng, "test")), "y": to_t(task.held_out(rng, True)),
            "other": to_t(task.held_out(rng, False))}
    rows = []
    for m in models:
        for s in a.seeds:
            model = load_checkpoint(m, a.ckpt or a.task, s)
            if model is None:
                continue
            for name, b in sets.items():
                rows.append({"model": m, "seed": s, "set": name, **score(model, b, task.spec)})
    with open(f"results/{a.ckpt or a.task}_eval.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    import pandas as pd
    df = pd.DataFrame(rows)
    with pd.option_context("display.width", 220):
        print(df.pivot_table(index="model", columns="set", values=[c for c in ("acc", "yes", "no", "seq") if c in df])
              .round(2).to_string())


if __name__ == "__main__":
    main()
