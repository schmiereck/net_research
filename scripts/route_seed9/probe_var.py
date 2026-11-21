"""How visible is the stored word in a cell? (1) share of a cell's variance explained linearly by the 8 bits (R^2);
(2) word bit accuracy from 16 values = the actual initial pcell map of the run, and from 20 random maps (mean)."""
import sys, numpy as np, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
exec(open(__file__.replace("probe_var.py", "probe.py")).read().split("for seed in")[0])
from netresearch.models.route import freeze_and_route
def r2(X, y):
    Y = np.concatenate([y, np.ones((len(y), 1))], 1)
    W, *_ = np.linalg.lstsq(Y, X, rcond=None)
    res = X - Y @ W
    return 1 - res.var(0).sum() / X.var(0).sum()
for seed in map(int, sys.argv[2:]):
    net = build_model("layer_s", 100_000, seed=seed); net.load_state_dict(torch.load(f"{D}/s{seed}.pt")); net.eval()
    m = freeze_and_route(net, "layer_s", 100_000, seed, opt="pcell")
    Wl = m.lat.weight.detach().numpy(); bl = m.lat.bias.detach().numpy()
    st = net.init_state(4000); rows = []
    with torch.no_grad():
        for t in range(4):
            _, st = net(obs[t], st)
            if t == 0: continue
            s = st[0].numpy()
            R, C = s.shape[1:3]
            cells = [s[:, r, c] for r in range(R) for c in range(C)]
            rr = np.mean([r2(x, bits) for x in cells])
            act = np.mean([probe(x @ Wl.T + bl, bits) for x in cells[::4]])
            rnd = np.mean([probe(x @ np.random.default_rng(k).standard_normal((x.shape[1], 16)), bits)
                           for k in range(5) for x in cells[::8]])
            rows.append((round(rr, 3), round(act, 3), round(rnd, 3)))
    print(seed, "t1..3 (R2 of word, acc. from initial map, acc. from random 16)", rows, flush=True)
