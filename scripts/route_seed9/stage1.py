"""Stage 1 (keep_shift:3000) of layer_s exactly as netresearch.curriculum.job, saves the net; prints its scores."""
import sys, time, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from netresearch.models import build_model
from netresearch.tasks import make_task
from netresearch.train import final_metrics, make_learner, train_loop
torch.set_num_threads(1)
OUT = sys.argv[1]
for seed in map(int, sys.argv[2:]):
    t0 = time.time()
    torch.manual_seed(seed)
    model = build_model("layer_s", 100_000, seed=seed)
    L = make_learner(model, make_task("keep_shift"), 3000, 64, seed)
    train_loop(model, [L], 3000, 2e-3, 10 ** 9)
    torch.save(model.state_dict(), f"{OUT}/s{seed}.pt")
    fm = {t: round(final_metrics(model, make_task(t))["score"], 4) for t in ("keep_shift", "match_shift")}
    print(seed, fm, round(time.time() - t0), flush=True)
