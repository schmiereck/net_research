"""match / match_shift: which candidates do the nets get wrong?

    python scripts/match_breakdown.py [--task match_shift] [--models gru attnmem ...] [--seeds 0 1 2]

Per net: share of right answers for the equal candidate ("same"), for distractors that differ in 1-2 bits
("near") and for the other distractors ("far"). -> results/<task>_breakdown.jsonl
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", default="match_shift")
    ap.add_argument("--models", nargs="+", default=["gru", "attnmem", "layer_i", "layer_s", "layer_s_am4"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    a = ap.parse_args()
    task = make_task(a.task)
    words, _ = task.draw(3000, np.random.default_rng(0), "test")        # sample() draws the same words first
    b = to_t(task.sample(3000, np.random.default_rng(0), "test"))
    diff = np.array([[bin(int(x)).count("1") for x in r] for r in words[:, 1:] ^ words[:, :1]]).T   # [3, B]
    kinds = {"same": diff == 0, "near": (diff > 0) & (diff <= 2), "far": diff > 2}
    rows = []
    for m in a.models:
        for s in a.seeds:
            model = load_checkpoint(m, a.task, s)
            if model is None:
                continue
            with torch.no_grad():
                lg, _ = run_sequence(model, b["obs"])
            ok = (lg[1:, :, task.spec.out_slice].argmax(-1) == b["target"][1:]).numpy()
            rows.append({"model": m, "seed": s, **{k: round(float(ok[v].mean()), 4) for k, v in kinds.items()},
                         "seq": round(float(ok.all(0).mean()), 4)})
    with open(f"results/{a.task}_breakdown.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    import pandas as pd
    print(pd.DataFrame(rows).groupby("model")[["same", "near", "far", "seq"]].mean().round(2).to_string())


if __name__ == "__main__":
    main()
