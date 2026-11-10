"""Training and evaluation loops.

Supervised tasks: sequences [T, B], truncated BPTT, loss on masked steps.
Control tasks   : imitation learning with DAgger (expert labels the states the learner visits).
Both are wrapped in "learners" so that one training loop serves single-task and multi-task runs.
"""
import json
import math
import os
import time
from collections import deque
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from .models import build_model, count_params
from .tasks import make_task

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "results" / "game_baselines.json"


# ----------------------------------------------------------------------------------------------- helpers
def reset_state(state, keep):
    """keep: float tensor [B] (0 = episode starts here -> zero the state)."""
    return tuple(s * keep.view(-1, *([1] * (s.dim() - 1))) for s in state)


def run_sequence(model, obs, state=None, resets=None):
    """obs [T,B,3,16,16] -> logits [T,B,64]. resets [T,B] (1 = new episode at t) for stateful models."""
    T, B = obs.shape[:2]
    if not model.stateful:
        out, _ = model(obs.reshape(T * B, *obs.shape[2:]), ())
        return out.view(T, B, -1), ()
    if state is None:
        state = model.init_state(B)
    outs = []
    for t in range(T):
        if resets is not None:
            state = reset_state(state, 1.0 - resets[t])
        o, state = model(obs[t], state)
        outs.append(o)
    return torch.stack(outs), state


def make_opt(model, updates, lr):
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    warm = max(1, updates // 20)

    def lr_fn(i):
        if i < warm:
            return (i + 1) / warm
        return 0.5 * (1 + math.cos(math.pi * (i - warm) / max(1, updates - warm)))
    return opt, torch.optim.lr_scheduler.LambdaLR(opt, lr_fn)


def supervised_loss(spec, logits, target, mask):
    lg = logits[..., spec.out_slice]
    if spec.head == "class":
        l = F.cross_entropy(lg.reshape(-1, spec.n_out), target.reshape(-1), reduction="none").view(mask.shape)
    else:
        l = F.binary_cross_entropy_with_logits(lg, target, reduction="none").mean(-1)
    return (l * mask).sum() / mask.sum().clamp_min(1)


def to_t(batch):
    return {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in batch.items()}


# ------------------------------------------------------------------------------------------- supervised
_eval_cache = {}


def _compact(batch):
    """Binary observations are kept as uint8 (4x less memory) and converted to float on use. Tasks with real
    valued images (robot fovea, tasks/robot.py) stay float: the cast would set every pixel below 1 to 0."""
    b = to_t(batch)
    if bool(((b["obs"] == 0) | (b["obs"] == 1)).all()):
        b["obs"] = b["obs"].to(torch.uint8)
    return b


def eval_set(task, n=2048, seed=12345):
    key = task.spec.name
    if key not in _eval_cache:
        rng = np.random.default_rng(seed)
        _eval_cache[key] = [_compact(task.sample(256, rng, split="test")) for _ in range(n // 256)]
    return _eval_cache[key]


@torch.no_grad()
def evaluate_supervised(model, task, n_batches=None):
    spec = task.spec
    was_training = model.training
    model.eval()
    correct = total = loss_sum = bit_correct = 0.0
    for b in eval_set(task)[:n_batches]:
        logits, _ = run_sequence(model, b["obs"].float())
        lg, m = logits[..., spec.out_slice], b["mask"]
        loss_sum += supervised_loss(spec, logits, b["target"], m).item() * m.sum().item()
        if spec.head == "class":
            correct += ((lg.argmax(-1) == b["target"]).float() * m).sum().item()
        else:
            pred = (lg > 0).float()
            eq = (pred == b["target"]).float()
            correct += (eq.min(-1).values * m).sum().item()
            bit_correct += (eq.mean(-1) * m).sum().item()
        total += m.sum().item()
    model.train(was_training)
    acc = correct / total
    res = {"acc": acc, "loss": loss_sum / total}
    res["score"] = (acc - spec.chance) / (1 - spec.chance)          # chance = 0 for multi-bit outputs
    if spec.head == "bits":
        res["bit_acc"] = bit_correct / total
    if spec.name == "charnext":
        res["bpc"] = res["loss"] / math.log(2)
    return res


class SupervisedLearner:
    """Training batches for a supervised task; loss_on(model, batch) -> scalar loss."""

    def __init__(self, task, batch, seed):
        self.task, self.spec, self.batch = task, task.spec, batch
        self.rng = np.random.default_rng(seed)
        self.probe_rng = np.random.default_rng(seed + 7777)

    def next_batch(self, model):
        return to_t(self.task.sample(self.batch, self.rng))

    def probe_batch(self, model):
        """Batch for diagnostics (does not advance the training stream)."""
        return to_t(self.task.sample(self.batch, self.probe_rng))

    def loss_on(self, model, b):
        logits, _ = run_sequence(model, b["obs"])
        return supervised_loss(self.spec, logits, b["target"], b["mask"])

    def log(self):
        return []


# ---------------------------------------------------------------------------------------------- control
def policy_actions(logits, valid):
    return np.asarray(valid)[logits[:, valid].argmax(-1).numpy()]


@torch.no_grad()
def evaluate_control(model, task, n_envs=32, seed=999, policy="model"):
    """Mean return of the first episode of each of n_envs environments (greedy policy)."""
    env = task.make_env(n_envs, seed)
    valid = task.spec.valid_actions
    rng = np.random.default_rng(seed)
    state = model.init_state(n_envs) if model is not None else ()
    returns = {}
    lengths = {}
    keep = torch.ones(n_envs)
    for _ in range(max(g.max_steps for g in env.games) + 5):
        if policy == "expert":
            a = env.expert()
        elif policy == "random":
            a = rng.choice(valid, size=n_envs)
        else:
            if model.stateful:
                state = reset_state(state, keep)
            logits, state = model(torch.from_numpy(env.obs()), state)
            a = policy_actions(logits, valid)
        _, done, finished = env.step(a)
        keep = torch.from_numpy((~done).astype(np.float32))
        for i, r, ln in finished:
            if i not in returns:
                returns[i], lengths[i] = float(r), int(ln)
        if len(returns) == n_envs:
            break
    return float(np.mean(list(returns.values()))), float(np.mean(list(lengths.values())))


def game_baselines(task):
    data = json.loads(BASELINES.read_text()) if BASELINES.exists() else {}
    name = task.spec.name
    if name not in data:
        r, _ = evaluate_control(None, task, policy="random")
        e, _ = evaluate_control(None, task, policy="expert")
        data[name] = {"random": r, "expert": e}
        BASELINES.parent.mkdir(parents=True, exist_ok=True)
        BASELINES.write_text(json.dumps(data, indent=1))
    return data[name]


class ControlLearner:
    """DAgger: the expert labels the states the learner visits; the expert-mixing probability beta goes
    1 -> 0 over the first half of the chunks. One chunk (T steps x n_envs) is collected every upd_per_chunk
    updates into a replay buffer of chunks."""

    def __init__(self, model, task, updates, batch, seed, n_envs=16, upd_per_chunk=4, buffer_chunks=96):
        self.task, self.spec = task, task.spec
        self.T, self.valid = self.spec.seq_len, self.spec.valid_actions
        self.label_map = torch.full((8,), -1, dtype=torch.long)
        self.label_map[self.valid] = torch.arange(len(self.valid))
        self.env = task.make_env(n_envs, seed)
        self.n_envs, self.upd_per_chunk = n_envs, upd_per_chunk
        self.rng = np.random.default_rng(seed)
        self.buf = deque(maxlen=buffer_chunks)
        self.state = model.init_state(n_envs)
        self.keep = np.ones(n_envs, dtype=np.float32)
        self.n_chunks = math.ceil(updates / upd_per_chunk)
        self.chunks_per_batch = max(1, batch // n_envs)
        self.c = self.k = 0
        self.agree = self.agree_n = 0.0

    @torch.no_grad()
    def collect(self, model):
        beta = max(0.0, 1.0 - self.c / (0.5 * self.n_chunks))
        env, n = self.env, self.n_envs
        obs_l, lab_l, res_l = [], [], []
        for _ in range(self.T):
            o = env.obs()
            ex = env.expert()
            res_l.append(1.0 - self.keep)
            if model.stateful:
                self.state = reset_state(self.state, torch.from_numpy(self.keep))
            logits, self.state = model(torch.from_numpy(o), self.state)
            a_model = policy_actions(logits, self.valid)
            self.agree += (a_model == ex).sum()
            self.agree_n += n
            a = np.where(self.rng.random(n) < beta, ex, a_model)
            _, done, _ = env.step(a)
            self.keep = (~done).astype(np.float32)
            obs_l.append(o)
            lab_l.append(ex)
        self.buf.append((np.stack(obs_l).astype(np.uint8), np.stack(lab_l), np.stack(res_l).astype(np.float32)))
        self.c += 1

    def _sample(self, rng):
        idx = rng.integers(len(self.buf), size=self.chunks_per_batch)
        obs = torch.from_numpy(np.concatenate([self.buf[j][0] for j in idx], 1)).float()
        lab = torch.from_numpy(np.concatenate([self.buf[j][1] for j in idx], 1))
        res = torch.from_numpy(np.concatenate([self.buf[j][2] for j in idx], 1))
        res[0] = 1.0                                       # every chunk starts from a zero state
        return {"obs": obs, "lab": lab, "res": res}

    def next_batch(self, model):
        if self.k % self.upd_per_chunk == 0:
            self.collect(model)
        self.k += 1
        return self._sample(self.rng)

    def probe_batch(self, model):
        if not self.buf:
            self.collect(model)
        return self._sample(np.random.default_rng(self.k + 7777))

    def loss_on(self, model, b):
        logits, _ = run_sequence(model, b["obs"], resets=b["res"])
        return F.cross_entropy(logits[..., self.valid].reshape(-1, len(self.valid)),
                               self.label_map[b["lab"]].reshape(-1))

    def log(self):
        a = self.agree / max(1, self.agree_n)
        self.agree = self.agree_n = 0.0
        return [round(float(a), 4)]


# ----------------------------------------------------------------------------------------- training
def make_learner(model, task, updates, batch, seed):
    if task.spec.kind == "supervised":
        return SupervisedLearner(task, batch, seed)
    return ControlLearner(model, task, updates, batch, seed)


def game_score(ret, base):
    return (ret - base["random"]) / max(1e-6, base["expert"] - base["random"])


def quick_score(model, task):
    """Cheaper evaluation for learning curves (512 test samples / 16 game episodes)."""
    if task.spec.kind == "supervised":
        return evaluate_supervised(model, task, n_batches=2)["score"]
    ret, _ = evaluate_control(model, task, n_envs=16)
    return game_score(ret, game_baselines(task))


def final_metrics(model, task):
    if task.spec.kind == "supervised":
        return evaluate_supervised(model, task)
    ret, ln = evaluate_control(model, task)
    base = game_baselines(task)
    return {"return": ret, "ep_len": ln, "score": game_score(ret, base), "random": base["random"],
            "expert": base["expert"]}


def train_loop(model, learners, updates, lr, log_every, on_eval=None, eval_every=None):
    """Round-robin over the learners (one per task; a single learner = single-task training).
    curve rows: [update, mean loss (list per task if several), DAgger agreement per control task...]."""
    opt, sched = make_opt(model, updates, lr)
    curve = []
    run_loss, run_n = np.zeros(len(learners)), np.zeros(len(learners))
    if on_eval is not None:
        on_eval(0)
    for i in range(updates):
        j = i % len(learners)
        L = learners[j]
        loss = L.loss_on(model, L.next_batch(model))
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        run_loss[j] += loss.item()
        run_n[j] += 1
        if (i + 1) % log_every == 0:
            ls = (run_loss / np.maximum(1, run_n)).round(5).tolist()
            extra = sum((L.log() for L in learners), [])
            curve.append([i + 1, ls[0] if len(learners) == 1 else ls, *extra])
            run_loss[:], run_n[:] = 0, 0
        if on_eval is not None and eval_every and (i + 1) % eval_every == 0 and i + 1 < updates:
            on_eval(i + 1)
    return curve


# ------------------------------------------------------------------------------------------------- run
CKPT_DIR = Path(os.environ.get("NETRESEARCH_CKPT_DIR", ROOT / "results" / "checkpoints"))   # worker: own dir


def checkpoint_path(model_name, task_name, seed):
    return CKPT_DIR / task_name / f"{model_name}_s{seed}.pt"


def save_checkpoint(model, model_name, task_name, seed, score):
    p = checkpoint_path(model_name, task_name, seed)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")   # atomic: parallel processes may train and load the
    torch.save({"model": model_name, "task": task_name, "seed": seed, "width": model.width_used,
                "score": score, "state_dict": model.state_dict()}, tmp)   # same base net (fresh worker)
    for i in range(20):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:                         # Windows: target open by a reader
            time.sleep(0.5 * (i + 1))
    os.replace(tmp, p)


def load_checkpoint(model_name, task_name, seed=0, path=None):
    """Rebuild a trained model from its checkpoint (None if it does not exist)."""
    from .models import MODELS
    p = Path(path) if path is not None else checkpoint_path(model_name, task_name, seed)
    if not p.exists():
        return None
    ck = torch.load(p, map_location="cpu", weights_only=True)
    model = MODELS[model_name.partition("@")[0]][0](width=ck["width"])
    model.load_state_dict(ck["state_dict"])
    model.width_used, model.score = ck["width"], ck["score"]
    return model.eval()


def _round(d):
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in d.items()}


def run(model_name, task_name, seed=0, updates=1500, batch=64, lr=2e-3, target_params=100_000, log_every=100,
        save=True, eval_every=250):
    """Single-task run. Besides the final metrics it records a learning curve of test scores (score_curve)
    and, for shared-weight models, the gradient agreement between the positions that use the shared module
    (grad_curve, see analysis.position_grad_stats)."""
    from .analysis import position_grad_stats
    from .models import SHARED_TO_INDIVIDUAL
    torch.manual_seed(seed)
    task = make_task(task_name)
    model = build_model(model_name, target_params, seed=seed)
    learner = make_learner(model, task, updates, batch, seed)
    shared = model_name in SHARED_TO_INDIVIDUAL
    score_curve, grad_curve = [], []

    def grad_stats(i):
        b = learner.probe_batch(model)
        grad_curve.append([i, position_grad_stats(model, model_name, lambda m: learner.loss_on(m, b))])

    def on_eval(i):
        if i > 0:
            score_curve.append([i, round(quick_score(model, task), 4)])
        if shared:
            grad_stats(i)

    t0 = time.time()
    curve = train_loop(model, [learner], updates, lr, log_every, on_eval, eval_every)
    train_time = time.time() - t0
    metrics = final_metrics(model, task)
    score_curve.append([updates, round(metrics["score"], 4)])
    if shared:
        grad_stats(updates)
    if save:
        save_checkpoint(model, model_name, task_name, seed, metrics["score"])
    out = {"model": model_name, "task": task_name, "seed": seed, "group": task.spec.group,
           "params": count_params(model), "width": model.width_used, "updates": updates,
           "train_time": round(train_time, 1), "eval_time": round(time.time() - t0 - train_time, 1),
           **_round(metrics), "curve": curve, "score_curve": score_curve}
    if grad_curve:
        out["grad_curve"] = grad_curve
    return out


def run_multitask(model_name, task_names, seed=0, updates_per_task=1500, batch=64, lr=2e-3,
                  target_params=100_000, log_every=500, save=True, n_evals=4):
    """One model learns all tasks at once (round-robin, one task batch per update); each task gets
    updates_per_task gradient steps, as in its single-task run. There is no task id: the model has to infer
    the task from the input. Intermediate evaluations record per-task scores, the cosine matrix between the
    tasks' gradients and (shared models) the per-task agreement between module positions."""
    from .analysis import position_grad_stats, task_grad_cosine
    from .models import SHARED_TO_INDIVIDUAL
    torch.manual_seed(seed)
    tasks = [make_task(t) for t in task_names]
    model = build_model(model_name, target_params, seed=seed)
    updates = updates_per_task * len(tasks)
    learners = [make_learner(model, t, updates_per_task, batch, seed + k) for k, t in enumerate(tasks)]
    evals = []

    def diagnostics(i, scores):
        bs = [L.probe_batch(model) for L in learners]
        fns = [(lambda m, L=L, b=b: L.loss_on(m, b)) for L, b in zip(learners, bs)]
        e = {"update": i, "scores": scores, "task_cos": task_grad_cosine(model, fns)}
        if model_name in SHARED_TO_INDIVIDUAL:
            e["pos_mean_cos"] = {t.spec.name: position_grad_stats(model, model_name, fn)["mean_cos"]
                                 for t, fn in zip(tasks, fns)}
        evals.append(e)

    def on_eval(i):
        diagnostics(i, {t.spec.name: round(quick_score(model, t), 4) for t in tasks} if i > 0 else {})

    t0 = time.time()
    curve = train_loop(model, learners, updates, lr, log_every, on_eval, max(1, updates // n_evals))
    train_time = time.time() - t0
    metrics = {t.spec.name: _round(final_metrics(model, t)) for t in tasks}
    diagnostics(updates, {k: round(v["score"], 4) for k, v in metrics.items()})
    if save:
        save_checkpoint(model, model_name, "multi", seed, float(np.mean([v["score"] for v in metrics.values()])))
    return {"model": model_name, "seed": seed, "tasks": task_names, "params": count_params(model),
            "width": model.width_used, "updates": updates, "updates_per_task": updates_per_task,
            "train_time": round(train_time, 1), "eval_time": round(time.time() - t0 - train_time, 1),
            "metrics": metrics, "evals": evals, "curve": curve}
