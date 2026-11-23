"""Checks for Freeze & Route (netresearch/models/route.py, curriculum word "freeze").

    .venv/Scripts/python.exe scripts/check_route.py

1. The frozen net does not change and gets no gradient; the new parts do.
2. At the start the gate is 0.5: output = (frozen output + new output) / 2.
3. The frozen part computes exactly what the net alone computes (same state handling, resets included).
4. The lateral signal reaches the new module (changing it changes the output).
5. A tiny curriculum run with "freeze" for layer_s, hier_s and gru.
7. Gaze ladder (own fronts, sum in the port): each net has its own retina and address encoder, the frozen part
   computes what the frozen net alone computes, the new port gets lateral + its own encoder's command, the new
   front learns and the frozen one does not; tiny curriculum runs cue -> freeze -> blind.
8. Selection by task ("freeze:sel"): the statistic of the old task, output = the frozen net alone on familiar
   episodes and the compound's elsewhere, the step count resets with the episode, the frozen net stays unchanged;
   tiny curriculum runs blind -> freeze:sel -> two.
"""
import json
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
# 6. probes "freeze:<opt>": they run, change what they say, and stage 1 is the same in every one (paired runs)
from netresearch.models.route import FrozenRoute  # noqa: E402
for name in ("layer_s", "hier_s"):
    base = build_model(name, seed=3)
    m = freeze_and_route(base, name, seed=3, opt="pfull")
    check(m.lat.out_features == base.head.in_features and m.new.n_cmd == base.head.in_features,
          f"{name}: pfull port carries the whole top representation ({m.lat.out_features} values)")
    m = freeze_and_route(base, name, seed=3, opt="p64")
    check(m.new.n_cmd == 64, f"{name}: p64 port has 64 values")
    m = freeze_and_route(base, name, seed=3, opt="nogate")
    with torch.no_grad():
        out, _ = run_sequence(m, obs)
        m.new.cmd = None
    check(not m.use_gate, f"{name}: nogate has no gate")
for name in ("layer_s", "hier_s"):                     # pcell: cell (r, k) of the new grid gets the frozen cell (r, k)
    base = build_model(name, seed=3)
    m = freeze_and_route(base, name, seed=3, opt="pcell")
    for p in m.new.parameters():
        with torch.no_grad():
            if p.abs().sum() == 0:
                p.normal_(0, 0.05)
    seen = []
    m.new.register_forward_pre_hook(lambda mod, a: seen.append(mod.cmd.clone()))
    st = m.init_state(4)
    with torch.no_grad():
        m(obs[0, :4], st)
        so_after = base(obs[0, :4], base.init_state(4))[1]
    from netresearch.models.route import cell_view  # noqa: E402
    cv = cell_view(base, so_after)
    R_, K_ = (base.R, base.K) if hasattr(base, "K") else (base.R, base.C)
    check(seen[0].shape == (4, R_, K_, 16), f"{name}: pcell gives one command per cell {tuple(seen[0].shape)}")
    check(torch.allclose(seen[0], m.lat(cv)), f"{name}: pcell command of cell (r, k) comes from frozen cell (r, k)")
    with torch.no_grad():
        ref, _ = m(obs[0, :4], m.init_state(4))
        m.lat.bias[3] += 1.0
        moved, _ = m(obs[0, :4], m.init_state(4))
    check((moved - ref).abs().max() > 1e-4, f"{name}: pcell signal changes the output")
m = freeze_and_route(build_model("layer_s", seed=3), "layer_s", seed=3, opt="fc2")
check(m.new.fc2.w.abs().sum() > 0, "layer_s: fc2 probe starts the second cell layer random")
check(freeze_and_route(build_model("layer_s", seed=3), "layer_s", seed=3).new.fc2.w.abs().sum() == 0,
      "layer_s: default new module starts it at zero")
m = freeze_and_route(build_model("layer_s", seed=3), "layer_s", seed=3, opt="pcell+fc2")
m1 = freeze_and_route(build_model("layer_s", seed=3), "layer_s", seed=3, opt="fc2")
m2 = freeze_and_route(build_model("layer_s", seed=3), "layer_s", seed=3, opt="pcell")
check(m.per_cell and torch.equal(m.new.fc2.w, m1.new.fc2.w), "layer_s: pcell+fc2 is per cell and has fc2's random start")
check(all(torch.equal(v, m2.state_dict()[k]) for k, v in m.state_dict().items() if "fc2" not in k),
      "layer_s: pcell+fc2 differs from pcell only in fc2")
finals = {}
for opt in ("", ":p64", ":pfull", ":fc2", ":nogate", ":pcell", ":pcell+fc2"):
    r = job((f"keep_shift:60 freeze{opt} match_shift:30", "layer_s", 0, ["keep_shift", "match_shift"], None))
    check("error" not in r, f"layer_s: 'freeze{opt}' runs " + str(r.get("final", r.get("error", "")[-300:])))
    finals[opt] = r.get("frozen_final")
check(len({json.dumps(v, sort_keys=True) for v in finals.values()}) == 1,
      f"stage 1 identical in all probes (frozen net alone: {finals['']})")
# 7. gaze ladder: own retina and address encoder per net, the new port carries lateral + own command
task = make_task("robot_loop_cue_f32")
b = {k: torch.tensor(v) for k, v in task.sample(6, np.random.default_rng(1)).items()}
for name in ("layer_s_sp4+cell+refl+rez3", "vitmem+refl+rez3", "layer_s_sp4+cell+refl+rv+rez3"):
    for opt in ("", "pcell") if "layer" in name else ("",):
        base = build_model(name, seed=3)
        with torch.no_grad():                           # nudge the zero-started retina correction, so it matters
            base.retina.body[-1].weight.normal_(0, 0.05)
            alone, _ = run_sequence(base, b["obs"], cmd=b.get("cmd"), ref=b["ref"], ref_mask=b["ref_mask"])
        m = freeze_and_route(base, name, seed=3, opt=opt)
        tag = f"{name}{':' + opt if opt else ''}"
        check(m.new.retina is not m.frozen.retina and m.new.ref_enc is not m.frozen.ref_enc,
              f"{tag}: each net has its own retina and address encoder")
        outs_old, seen, lat_only = [], [], []
        h1 = m.frozen.register_forward_hook(lambda mod, a, o: outs_old.append(o[0]))
        h2 = m.new.register_forward_pre_hook(lambda mod, a: seen.append(mod.cmd.clone()))
        h3 = m.lat.register_forward_hook(lambda mod, a, o: lat_only.append(o.clone()))
        with torch.no_grad():
            run_sequence(m, b["obs"], cmd=b.get("cmd"), ref=b["ref"], ref_mask=b["ref_mask"])
        h1.remove(); h2.remove(); h3.remove()
        check(torch.allclose(torch.stack(outs_old), alone, atol=1e-5), f"{tag}: frozen part = frozen net alone "
              "(own retina, own encoder)")
        from netresearch.train import front  # noqa: E402
        with torch.no_grad():
            _, cn, _ = front(m.new, b["obs"], b.get("cmd"), b["ref"], b["ref_mask"])
        diff = torch.stack(seen) - torch.stack(lat_only)
        want = cn[:, :, None, None].expand_as(diff) if diff.dim() == 5 else cn
        check(torch.allclose(diff, want, atol=1e-5), f"{tag}: port = lateral + own encoder command")
        if "+rv" in name:
            blank = b["ref_mask"] == 0
            check(bool(blank.any()) and diff[blank].abs().max() < 1e-6,
                  f"{tag}: '+rv' steps without a picture add no own command (lateral only)")
        L = make_learner(m, task, 10, 8, 0)
        snap = {k: v.clone() for k, v in m.frozen.state_dict().items()}
        train_loop(m, [L], 10, 2e-3, 10 ** 9)
        check(all(torch.equal(v, m.frozen.state_dict()[k]) for k, v in snap.items()), f"{tag}: frozen net unchanged")
        g_new = [p.grad for p in list(m.new.retina.parameters()) + list(m.new.ref_enc.parameters())]
        check(all(g is not None and g.abs().sum() > 0 for g in g_new), f"{tag}: new retina and encoder learn")
for plan in ("robot_loop_cue_f32:40 freeze robot_loop_blind_f32:40",
             "robot_loop_cue_f32:40 freeze:pcell robot_loop_blind_f32:40"):
    r = job((plan, "layer_s_sp4+cell+refl+rez3", 0, ["robot_loop_cue_f32", "robot_loop_blind_f32"], None))
    check("error" not in r, f"layer_s_sp4: '{plan}' runs " + str(r.get("final", r.get("error", "")[-500:])))
r = job(("robot_loop_cue_f32:40 freeze robot_loop_blind_f32:40", "vitmem+refl+rez3", 0, None, None))
check("error" not in r, "vitmem: cue freeze blind runs " + str(r.get("final", r.get("error", "")[-500:])))

# 8. selection by task ("freeze:sel"): statistic of the old task, the frozen output alone on familiar episodes,
# the compound's output on the others, extra state reset with the episode, curriculum runs
from netresearch.models.route import fit_familiar, selection_share  # noqa: E402
old_t, new_t = make_task("robot_loop_blind_f32"), make_task("robot_loop_two_f32")
for name, opt in (("layer_s_sp4+cell+refl+rez3", "sel"), ("layer_s_sp4+cell+refl+rez3", "pcell+sel"),
                  ("vitmem+refl+rez3", "sel")):
    tag = f"{name}:{opt}"
    m = freeze_and_route(build_model(name, seed=3), name, seed=3, opt=opt)
    check(m.wants_select and not m.select and m.per_cell == ("pcell" in opt), f"{tag}: builds, selection after the fit")
    fit_familiar(m, [old_t], episodes=512)
    check(m.select and len(m.fam_thr) == old_t.T, f"{tag}: statistic fitted, one threshold per step of the old task")
    check(len(m.init_state(4)) == m.n_old + m.n_new + 2, f"{tag}: two more state values")
    for t in (old_t, new_t):
        bb = {k: torch.tensor(v) for k, v in t.sample(32, np.random.default_rng(5)).items()}
        args = dict(cmd=bb.get("cmd"), ref=bb["ref"], ref_mask=bb["ref_mask"])
        m.eval()
        with torch.no_grad():
            m.select = False
            mixed, _ = run_sequence(m, bb["obs"], **args)
            fro, _ = run_sequence(m.frozen, bb["obs"], **args)
            m.select, m.record = True, []
            out, st = run_sequence(m, bb["obs"], **args)
            s = torch.stack(m.record)[..., None]
            m.record = None
        want = s * fro + (1 - s) * mixed
        check(torch.allclose(out, want, atol=1e-5), f"{t.spec.name}: output = frozen alone where familiar "
              f"(share {s.mean().item():.2f}), compound elsewhere")
        check(torch.equal(st[-1][:, 0], torch.full((32,), float(t.T))), f"{t.spec.name}: step count per episode")
        rs = torch.zeros(bb["obs"].shape[:2]); rs[3] = 1.0
        with torch.no_grad():
            _, st2 = run_sequence(m, bb["obs"], resets=rs, **args)
        check(torch.equal(st2[-1][:, 0], torch.full((32,), float(t.T - 3))), f"{t.spec.name}: reset starts the count anew")
    m.train()
    snap = {k: v.clone() for k, v in m.frozen.state_dict().items()}
    train_loop(m, [make_learner(m, new_t, 5, 8, 0)], 5, 2e-3, 10 ** 9)
    check(all(torch.equal(v, m.frozen.state_dict()[k]) for k, v in snap.items()), f"{tag}: frozen net unchanged")
    sh = selection_share(m, old_t, n_batches=1)
    check(0.0 <= sh <= 1.0, f"{tag}: selection share on the old task {sh:.2f}")
for plan, name in (("robot_loop_blind_f32:40 freeze:sel robot_loop_two_f32:40", "layer_s_sp4+cell+refl+rez3"),
                   ("robot_loop_blind_f32:40 freeze:pcell+sel robot_loop_two_f32:40", "layer_s_sp4+cell+refl+rez3"),
                   ("robot_loop_blind_f32:40 freeze:sel robot_loop_two_f32:40", "vitmem+refl+rez3")):
    r = job((plan, name, 0, ["robot_loop_blind_f32", "robot_loop_two_f32"], None))
    check("error" not in r and set(r.get("selected", {})) == {"robot_loop_blind_f32", "robot_loop_two_f32"},
          f"{name}: '{plan}' runs, selected {r.get('selected', r.get('error', '')[-500:])}")
r = job(("robot_loop_blind_f32:40 freeze:pcell+sel robot_loop_two_f32:40", "vitmem+refl+rez3", 0, None, None))
check("error" in r and "pcell for grids only" in r["error"], "vitmem: 'freeze:pcell+sel' stops before stage 1")
print("ALL OK" if ok else "SOME CHECKS FAILED")
