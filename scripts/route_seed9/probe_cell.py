"""Per-cell probe: the stored word (8 bits) from ONE frozen cell (r, c) (d values), t = 1..3; and from one cell with a
probe shared by all cells of a row (as pcell's shared map, but with full d -> 8)."""
import sys, numpy as np, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
exec(open(__file__.replace("probe_cell.py", "probe.py")).read().split("for seed in")[0])   # data, bits, probe()
for seed in map(int, sys.argv[2:]):
    net = build_model("layer_s", 100_000, seed=seed); net.load_state_dict(torch.load(f"{D}/s{seed}.pt")); net.eval()
    st = net.init_state(4000); out = []
    with torch.no_grad():
        for t in range(4):
            _, st = net(obs[t], st)
            if t == 0: continue
            s = st[0].numpy()                      # B, R, C, d
            R, C = s.shape[1:3]
            acc = np.array([[probe(s[:, r, c], bits) for c in range(C)] for r in range(R)])
            out.append(acc)
    print(seed, "R x C =", out[0].shape, flush=True)
    for t, a in enumerate(out, 1):
        print(f"   t{t} per row: best cell {[round(x,3) for x in a.max(1)]}  mean {[round(x,3) for x in a.mean(1)]}", flush=True)
