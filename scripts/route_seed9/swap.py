"""Stage 2 (freeze:<opt> match_shift) from a saved stage-1 net, as curriculum.job, with a look inside every 250 updates:
score, gate (mean, share > 0.9), rms of the command, gradient norms (new fc1 / fc2 / lat / gate) on a separate batch."""
import sys, numpy as np, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from netresearch.models import build_model
from netresearch.models.route import freeze_and_route
from netresearch.tasks import make_task
from netresearch.train import make_learner, quick_score, train_loop, run_sequence
torch.set_num_threads(4)
D, seed, opt, updates, roll = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
net = build_model("layer_s", 100_000, seed=seed)
net.load_state_dict(torch.load(f"{D}/s{seed}.pt"))
torch.manual_seed(roll)
m = freeze_and_route(net, "layer_s", 100_000, roll, opt=opt)   # new module, lateral map, gate from roll
task = make_task("match_shift")
L = make_learner(m, task, updates, 64, roll + 200)   # batches from roll
P = make_learner(m, task, updates, 64, 999)                 # probe batches, separate rng
gs, cm = [], []
m.gate.register_forward_hook(lambda mod, a, o: gs.append(torch.sigmoid(o).detach()))
m.new.register_forward_pre_hook(lambda mod, a: cm.append(mod.cmd.detach()) if mod.cmd is not None else None)
def gn(ps): return round(sum(p.grad.pow(2).sum().item() for p in ps if p.grad is not None) ** 0.5, 4)
def on_eval(i):
    if i % 250: return
    gs.clear(); cm.clear()
    m.zero_grad()
    loss = P.loss_on(m, P.next_batch(m)); loss.backward()
    g = torch.cat([x.flatten() for x in gs]); c = torch.cat([x.flatten() for x in cm])
    print(i, "score", round(quick_score(m, task), 3), "loss", round(loss.item(), 4), "gate", round(g.mean().item(), 3),
          round((g > 0.9).float().mean().item(), 3), round((g < 0.1).float().mean().item(), 3),
          "cmd_rms", round(c.pow(2).mean().sqrt().item(), 2),
          "grad fc1", gn(m.new.fc1.parameters()), "fc2", gn(m.new.fc2.parameters()), "lat", gn(m.lat.parameters()),
          "gate", gn(m.gate.parameters()), "all_new", gn(p for n_, p in m.named_parameters() if not n_.startswith("frozen")), flush=True)
    m.zero_grad()
train_loop(m, [L], updates, 2e-3, 10 ** 9, on_eval, 250)
