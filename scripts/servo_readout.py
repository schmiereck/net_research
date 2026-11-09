"""What limits the servo calibrations: the linear readout of the head input, or the learning rule?
Frozen base net; a correction of the 8 command logits is fitted on features of the head input h:
    lin      phi = h                                  (what delta_head can reach at best)
    rf<N>    phi = [h, gelu(R h)], R fixed random     (random expansion, still a local delta rule on top)
    pos      phi = one-hot (dx, dy)                   (reference: the wanted step itself as a table)
fit: 'adam' = full batch, 300 steps (ceiling); 'delta' = online delta rule, 100 batches of 16 (as the library).
    python scripts/servo_readout.py [--models layer_s hier_s] [--seeds 5 6]
"""
import argparse, json, math, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.adapt import start_net
from netresearch.tasks.servo import DEVICES, servo_batch
from netresearch.train import run_sequence, to_t

DEV = ["flipx", "swap", "rot90", "strong", "weak", "offx"]


def feats(model, obs):
    cap = []
    h = model.head.register_forward_hook(lambda m, i, o: cap.append(i[0].detach()))
    with torch.no_grad():
        logits, _ = run_sequence(model, obs)
    h.remove()
    return cap[-1], logits[0, :, 18:26]


def fit(phi, base, y, phit, baset, yt, how, eta=3.0):
    F = torch.zeros(phi.shape[1], 8, requires_grad=how == "adam")
    if how == "adam":
        opt = torch.optim.Adam([F], lr=1e-2)
        for _ in range(300):
            loss = torch.nn.functional.binary_cross_entropy_with_logits(base + phi @ F, y)
            opt.zero_grad(); loss.backward(); opt.step()
    else:
        with torch.no_grad():
            for i in range(0, len(phi), 16):
                x, e = phi[i:i + 16], torch.sigmoid(base[i:i + 16] + phi[i:i + 16] @ F) - y[i:i + 16]
                F -= eta * (x / (x * x).sum(1, keepdim=True)).T @ e / 16 * (16 / 6)
    with torch.no_grad():
        return float((((baset + phit @ F) > 0).float() == yt).all(1).float().mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["layer_s", "hier_s"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[5, 6])
    ap.add_argument("--out", default="results/servo_readout.jsonl")
    a = ap.parse_args()
    rows = []
    for m in a.models:
        for s in a.seeds:
            model = start_net(m, "servo", s)
            g = torch.Generator().manual_seed(s)
            for d in DEV:
                rng = np.random.default_rng(1000 * s + DEV.index(d))
                tr, te = to_t(servo_batch(d, 1600, rng, "train")), to_t(servo_batch(d, 1024, rng, "test"))
                h, b = feats(model, tr["obs"]); ht, bt = feats(model, te["obs"])
                y, yt = tr["target"][0], te["target"][0]
                sets = {"lin": (h, ht)}
                for n in (1024, 4096):
                    R = torch.randn(h.shape[1], n, generator=g) / math.sqrt(h.shape[1]) * 2
                    f = lambda x: torch.cat([x, torch.nn.functional.gelu(x @ R)], 1)
                    sets[f"rf{n}"] = (f(h), f(ht))
                for name, (p, pt) in sets.items():
                    for how in ("adam", "delta"):
                        r = {"model": m, "seed": s, "device": d, "feat": name, "fit": how,
                             "acc": round(fit(p, b, y, pt, bt, yt, how), 4)}
                        rows.append(r); print(r, flush=True)
    with open(a.out, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    import pandas as pd
    print(pd.DataFrame(rows).pivot_table(index=["feat", "fit"], columns="device", values="acc").round(2))


if __name__ == "__main__":
    main()
