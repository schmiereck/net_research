"""Checks for the "+rv" suffix (no command on steps without a picture): python scripts/check_ref_valid.py"""
import sys
import numpy as np
import torch

sys.path.insert(0, ".")
from netresearch.models import build_model
from netresearch.tasks.registry import make_task
from netresearch.train import load_checkpoint, run_sequence, to_t

torch.manual_seed(0)
task = make_task("robot_loop_three_f32")
b = to_t(task.sample(16, np.random.default_rng(1), split="test"))
obs, ref, rm = b["obs"].float(), b["ref"], b["ref_mask"]
print("batch", tuple(obs.shape), "ref_mask per step", rm[:, 0].tolist())

# 1. ref_mask of the task = 'picture not all zero'
derived = (ref.float().flatten(2).abs().amax(-1) > 0).float()
assert torch.equal(derived, rm), "task ref_mask differs from all-zero rule"
print("1 ok: task ref_mask equals the all-zero rule")

for name in ["attnmem+refl+rez3", "vitmem+refl+rez3", "layer_s_sp4+cell+refl+rez3", "layer_s+cell+refl+rez3"]:
    # 2. old nets: unchanged (stored checkpoint, same output with and without passing ref_mask)
    old = load_checkpoint(name, "robot_loop_three_f32", 0)
    old.eval()
    with torch.no_grad():
        a, _ = run_sequence(old, obs, ref=ref)
        c, _ = run_sequence(old, obs, ref=ref, ref_mask=rm)
    assert torch.equal(a, c), name
    # 3. same seed: +rv has the same parameters as without
    rvn = name.replace("+refl", "+refl+rv")
    m0, m1 = build_model(name, seed=3), build_model(rvn, seed=3)
    s0, s1 = m0.state_dict(), m1.state_dict()
    assert s0.keys() == s1.keys() and all(torch.equal(s0[k], s1[k]) for k in s0), "init differs"
    assert getattr(m1, "ref_valid", False) and not getattr(m0, "ref_valid", False)
    # 4. +rv: steps without a picture behave exactly like a net that gets no command at all
    m1.eval()
    with torch.no_grad():
        full, st = run_sequence(m1, obs[:3], ref=ref[:3], ref_mask=rm[:3])        # cue steps
        r1, _ = run_sequence(m1, obs[3:], state=st, ref=ref[3:], ref_mask=rm[3:])
        r2, _ = run_sequence(m1, obs[3:], state=st)                                # no ref, no cmd
        r3, _ = run_sequence(m1, obs[3:], state=st, ref=ref[3:])                   # mask from the all-zero rule
        # without +rv the blank picture still sends a command
        m0.eval()
        f0, st0 = run_sequence(m0, obs[:3], ref=ref[:3])
        q1, _ = run_sequence(m0, obs[3:], state=st0, ref=ref[3:])
        q2, _ = run_sequence(m0, obs[3:], state=st0)
    assert torch.allclose(r1, r2, atol=0) and torch.equal(r1, r3), name
    assert torch.allclose(full, f0), "cue steps must equal the old net (same init, picture shown)"
    print(f"{name:<30} old unchanged; +rv same init; run steps = no command (max diff {float((r1 - r2).abs().max()):.1e}); "
          f"without +rv the blank picture moves the output by {float((q1 - q2).abs().max()):.3f}")

# 5. gradients: the address encoder gets no gradient from steps without a picture
m = build_model("attnmem+refl+rv+rez3", seed=0)
lg, _ = run_sequence(m, obs[3:], ref=ref[3:], ref_mask=rm[3:])
lg.sum().backward()
g = sum(float(p.grad.abs().sum()) for p in m.ref_enc.parameters() if p.grad is not None)
gc = sum(float(p.grad.abs().sum()) for p in m.cmd_in.parameters() if p.grad is not None)
assert g == 0 and gc == 0, (g, gc)
print("5 ok: no gradient into the address path from steps without a picture")

# 6. '+rvt': steps without a picture send a learned token instead (model.no_ref, starts at zero)
from netresearch.models import split_size
for name in ["vitmem+refl+rez3", "layer_s_sp4+cell+refl+rez3"]:
    tn = name.replace("+refl", "+refl+rvt")
    assert split_size(tn)[0] == split_size(name)[0], tn
    m0, mt = build_model(name.replace("+refl", "+refl+rv"), seed=3), build_model(tn, seed=3)
    s0, st_ = m0.state_dict(), mt.state_dict()
    assert set(st_) - set(s0) == {"no_ref"} and all(torch.equal(s0[k], st_[k]) for k in s0), "init differs"
    assert torch.equal(mt.no_ref.detach(), torch.zeros_like(mt.no_ref))
    # a fresh grid ignores its command (zero read-out at the start), so the rest uses a trained '+rv' net
    m0 = load_checkpoint(name.replace("+refl", "+refl+rv"), "robot_loop_three_f32", 0)
    mt.load_state_dict({**m0.state_dict(), "no_ref": mt.no_ref.detach()})
    with torch.no_grad():
        mt.no_ref.copy_(torch.randn_like(mt.no_ref))                                # a token that is not zero
    mt.eval(); m0.eval()
    with torch.no_grad():
        f0, s_0 = run_sequence(m0, obs[:3], ref=ref[:3], ref_mask=rm[:3])
        ft, s_t = run_sequence(mt, obs[:3], ref=ref[:3], ref_mask=rm[:3])
        r1, _ = run_sequence(mt, obs[3:], state=s_t, ref=ref[3:], ref_mask=rm[3:])
        tok = mt.no_ref.expand(obs.shape[0] - 3, obs.shape[1], -1)
        r2, _ = run_sequence(mt, obs[3:], state=s_t, cmd=tok)                       # the token as a plain command
        r0, _ = run_sequence(m0, obs[3:], state=s_0, ref=ref[3:], ref_mask=rm[3:])
    assert torch.equal(f0, ft), "cue steps must equal '+rv' (same init, picture shown)"
    assert torch.allclose(r1, r2, atol=1e-6), name
    print(f"{tn:<34} same init as +rv plus a zero token; cue steps = +rv; run steps = token as command "
          f"(diff {float((r1 - r2).abs().max()):.1e}); the token moves the output by {float((r1 - r0).abs().max()):.3f}")
    # gradients from steps without a picture: into the token, not into the address encoder
    mt.train(); mt.zero_grad()
    lg, _ = run_sequence(mt, obs[3:], ref=ref[3:], ref_mask=rm[3:])
    lg.sum().backward()
    g = sum(float(p.grad.abs().sum()) for p in mt.ref_enc.parameters() if p.grad is not None)
    assert g == 0 and float(mt.no_ref.grad.abs().sum()) > 0, (g, mt.no_ref.grad)
print("6 ok: '+rvt' token reaches the port, the address encoder gets no gradient from steps without a picture")
