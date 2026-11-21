"""Checks for Freeze & Route (netresearch/models/route.py, curriculum word "freeze").

    .venv/Scripts/python.exe scripts/check_route.py

1. The frozen net does not change and gets no gradient; the new parts do.
2. At the start the gate is 0.5: output = (frozen output + new output) / 2.
3. The frozen part computes exactly what the net alone computes (same state handling, resets included).
4. The lateral signal reaches the new module (changing it changes the output).
5. A tiny curriculum run with "freeze" for layer_s, hier_s and gru.
"""
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.curriculum import job  # noqa: E402
from netresearch.models import build_model  # noqa: E402
from netresearch.models.route import freeze_and_route  # noqa: E402
from netresearch.tasks import make_task  # noqa: E402
from netresearch.train import make_learner, run_sequence, train_loop  # noqa: E402

torch.set_num_threads(2)
ok = True


def check(cond, msg):
    global ok
    print(("ok   " if cond else "FAIL ") + msg)
    ok &= bool(cond)


task = make_task("match_shift")
b = task.sample(16, np.random.default_rng(0))
obs = torch.tensor(b["obs"])
resets = torch.zeros(obs.shape[:2])
resets[2, :8] = 1.0                                             # a reset in the middle for half the batch
for name in ("layer_s", "hier_s", "gru"):
    base = build_model(name, seed=3)
    with torch.no_grad():
        alone, _ = run_sequence(base, obs, resets=resets)
    snap = {k: v.clone() for k, v in base.state_dict().items()}
    m = freeze_and_route(base, name, seed=3)
    with torch.no_grad():
        both, _ = run_sequence(m, obs, resets=resets)
        new_alone = both * 2 - alone                            # if the gate is 0.5
        m.new.cmd = None
    # 3. frozen part = the net alone; 2. gate 0.5
    outs_old = []
    m.frozen.register_forward_hook(lambda mod, a, o: outs_old.append(o[0]))
    with torch.no_grad():
        both2, _ = run_sequence(m, obs, resets=resets)
    check(torch.allclose(torch.stack(outs_old), alone, atol=1e-6), f"{name}: frozen part = net alone (with resets)")
    check(torch.allclose(both, both2), f"{name}: deterministic")
    g = torch.sigmoid(m.gate.bias).item()
    check(abs(g - 0.5) < 1e-6, f"{name}: gate starts at 0.5")
    # 4. lateral reaches the new module (on a copy whose zero-started weights are nudged: a fresh layer_s
    #    starts its cells' second layer at zero and ignores every input but the residual path)
    import copy
    m2 = copy.deepcopy(m)
    with torch.no_grad():
        for p in m2.new.parameters():
            if p.abs().sum() == 0:
                p.normal_(0, 0.05)
        ref, _ = run_sequence(m2, obs, resets=resets)
        m2.lat.bias.add_(1.0)
        moved, _ = run_sequence(m2, obs, resets=resets)
    check((moved - ref).abs().max().item() > 1e-4, f"{name}: lateral signal changes the output")
    # 1. training changes only the new parts
    L = make_learner(m, task, 20, 16, 0)
    train_loop(m, [L], 20, 2e-3, 10 ** 9)
    same = all(torch.equal(v, m.frozen.state_dict()[k]) for k, v in snap.items())
    check(same, f"{name}: frozen weights unchanged after 20 updates")
    check(all(p.grad is None for p in m.frozen.parameters()), f"{name}: no gradient in the frozen net")
    moved_new = any(p.grad is not None and p.grad.abs().sum() > 0 for p in m.new.parameters())
    check(moved_new and m.lat.weight.grad is not None and m.gate.weight.grad is not None,
          f"{name}: gradient in new module, lateral map and gate")
    n_new = sum(p.numel() for p in m.parameters() if p.requires_grad)
    n_old = sum(p.numel() for p in m.frozen.parameters())
    print(f"     {name}: frozen {n_old} parameters, trainable {n_new}")

# 5. curriculum with "freeze"
for name in ("layer_s", "hier_s", "gru"):
    r = job(("keep_shift:60 freeze match_shift:60", name, 0, ["keep_shift", "match_shift"], None))
    check("error" not in r, f"{name}: curriculum 'keep_shift:60 freeze match_shift:60' runs "
          + str(r.get("final", r.get("error", "")[-300:])))
    r = job(("freeze match_shift:60", name, 0, None, None))
    check("error" not in r, f"{name}: control 'freeze match_shift:60' runs " + str(r.get("final", r.get("error", "")[-300:])))
print("ALL OK" if ok else "SOME CHECKS FAILED")
