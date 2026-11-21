"""Size of what pcell hands the new module, per seed: frozen cell states, the pcell command, the top tap."""
import sys, numpy as np, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from netresearch.models import build_model
from netresearch.models.route import freeze_and_route, cell_view
from netresearch.tasks import make_task
from netresearch.train import run_sequence
torch.set_num_threads(4)
D = sys.argv[1]
task = make_task("match_shift")
b = task.sample(256, np.random.default_rng(0), split="test")
obs = torch.tensor(b["obs"])
print("seed | cell |x| per row (mean over steps) | cell max |x| | pcell cmd rms | top tap rms | fc1-input rms (normed part)")
for seed in map(int, sys.argv[2:]):
    net = build_model("layer_s", 100_000, seed=seed)
    net.load_state_dict(torch.load(f"{D}/s{seed}.pt"))
    m = freeze_and_route(net, "layer_s", 100_000, seed, opt="pcell")
    cells, cmds, tops = [], [], []
    st = m.frozen.init_state(obs.shape[1])
    with torch.no_grad():
        for t in range(obs.shape[0]):
            _, st = m.frozen(obs[t], st)
            cv = cell_view(m.frozen, st)
            cells.append(cv); cmds.append(m.lat(cv)); tops.append(m.tap_old.value)
    c = torch.stack(cells)            # T,B,R,C,d
    rows = c.abs().mean((0, 1, 3, 4))
    print(seed, [round(x, 2) for x in rows.tolist()], round(c.abs().max().item(), 1),
          round(torch.stack(cmds).pow(2).mean().sqrt().item(), 2), round(torch.stack(tops).pow(2).mean().sqrt().item(), 2), 1.0, flush=True)
