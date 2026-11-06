"""Training and evaluation loops.

Supervised tasks: sequences [T, B], truncated BPTT, loss on masked steps.
Control tasks   : imitation learning with DAgger (expert labels the states the learner visits).
"""
import json
import math
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
    lg = logits[..., :spec.n_out]
    if spec.head == "class":
        l = F.cross_entropy(lg.reshape(-1, spec.n_out), target.reshape(-1), reduction="none").view(mask.shape)
    else:
        l = F.binary_cross_entropy_with_logits(lg, target, reduction="none").mean(-1)
    return (l * mask).sum() / mask.sum().clamp_min(1)


def to_t(batch):
    return {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in batch.items()}


# ------------------------------------------------------------------------------------------- supervised
_eval_cache = {}


def eval_set(task, n=2048, seed=12345):
    key = task.spec.name
    if key not in _eval_cache:
        rng = np.random.default_rng(seed)
        _eval_cache[key] = [to_t(task.sample(256, rng, split="test")) for _ in range(n // 256)]
    return _eval_cache[key]


@torch.no_grad()
def evaluate_supervised(model, task):
    spec = task.spec
    model.eval()
    correct = total = loss_sum = bit_correct = 0.0
    for b in eval_set(task):
        logits, _ = run_sequence(model, b["obs"])
        lg, m = logits[..., :spec.n_out], b["mask"]
        loss_sum += supervised_loss(spec, logits, b["target"], m).item() * m.sum().item()
        if spec.head == "class":
            correct += ((lg.argmax(-1) == b["target"]).float() * m).sum().item()
        else:
            pred = (lg > 0).float()
            eq = (pred == b["target"]).float()
            correct += (eq.min(-1).values * m).sum().item()
            bit_correct += (eq.mean(-1) * m).sum().item()
        total += m.sum().item()
    model.train()
    acc = correct / total
    res = {"acc": acc, "loss": loss_sum / total}
    if spec.head == "class":
        res["score"] = (acc - spec.chance) / (1 - spec.chance)
    else:
        res["score"] = acc
        res["bit_acc"] = bit_correct / total
    if spec.name == "charnext":
        res["bpc"] = res["loss"] / math.log(2)
    return res


def train_supervised(model, task, updates, batch, lr, seed, log_every):
    spec = task.spec
    rng = np.random.default_rng(seed)
    opt, sched = make_opt(model, updates, lr)
    curve = []
    run_loss = 0.0
    for i in range(updates):
        b = to_t(task.sample(batch, rng))
        logits, _ = run_sequence(model, b["obs"])
        loss = supervised_loss(spec, logits, b["target"], b["mask"])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        run_loss += loss.item()
        if (i + 1) % log_every == 0:
            curve.append([i + 1, run_loss / log_every])
            run_loss = 0.0
    return curve


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


def train_control(model, task, updates, batch, lr, seed, log_every, n_envs=16, upd_per_chunk=4,
                  buffer_chunks=96):
    spec = task.spec
    T, valid = spec.seq_len, spec.valid_actions
    label_map = torch.full((8,), -1, dtype=torch.long)
    label_map[valid] = torch.arange(len(valid))
    env = task.make_env(n_envs, seed)
    rng = np.random.default_rng(seed)
    opt, sched = make_opt(model, updates, lr)
    buf = deque(maxlen=buffer_chunks)
    state = model.init_state(n_envs)
    keep = np.ones(n_envs, dtype=np.float32)
    n_chunks = math.ceil(updates / upd_per_chunk)
    curve, run_loss, i, agree, agree_n = [], 0.0, 0, 0.0, 0
    chunks_per_batch = max(1, batch // n_envs)
    for c in range(n_chunks):
        beta = max(0.0, 1.0 - c / (0.5 * n_chunks))           # expert-mixing probability, 1 -> 0
        obs_l, lab_l, res_l = [], [], []
        with torch.no_grad():
            for t in range(T):
                o = env.obs()
                ex = env.expert()
                res_l.append(1.0 - keep)
                if model.stateful:
                    state = reset_state(state, torch.from_numpy(keep))
                logits, state = model(torch.from_numpy(o), state)
                a_model = policy_actions(logits, valid)
                agree += (a_model == ex).sum()
                agree_n += n_envs
                a = np.where(rng.random(n_envs) < beta, ex, a_model)
                _, done, _ = env.step(a)
                keep = (~done).astype(np.float32)
                obs_l.append(o)
                lab_l.append(ex)
        buf.append((np.stack(obs_l), np.stack(lab_l), np.stack(res_l).astype(np.float32)))
        for _ in range(upd_per_chunk):
            if i >= updates:
                break
            idx = rng.integers(len(buf), size=chunks_per_batch)
            obs = torch.from_numpy(np.concatenate([buf[j][0] for j in idx], 1))
            lab = torch.from_numpy(np.concatenate([buf[j][1] for j in idx], 1))
            res = torch.from_numpy(np.concatenate([buf[j][2] for j in idx], 1))
            res[0] = 1.0                                       # every chunk starts from a zero state
            logits, _ = run_sequence(model, obs, resets=res)
            loss = F.cross_entropy(logits[..., valid].reshape(-1, len(valid)), label_map[lab].reshape(-1))
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            run_loss += loss.item()
            i += 1
            if i % log_every == 0:
                curve.append([i, run_loss / log_every, agree / max(1, agree_n)])
                run_loss, agree, agree_n = 0.0, 0.0, 0
    return curve


# ------------------------------------------------------------------------------------------------- run
def run(model_name, task_name, seed=0, updates=1500, batch=64, lr=2e-3, target_params=100_000, log_every=100):
    torch.manual_seed(seed)
    task = make_task(task_name)
    model = build_model(model_name, target_params, seed=seed)
    t0 = time.time()
    if task.spec.kind == "supervised":
        curve = train_supervised(model, task, updates, batch, lr, seed, log_every)
        train_time = time.time() - t0
        metrics = evaluate_supervised(model, task)
    else:
        curve = train_control(model, task, updates, batch, lr, seed, log_every)
        train_time = time.time() - t0
        ret, ln = evaluate_control(model, task)
        base = game_baselines(task)
        score = (ret - base["random"]) / max(1e-6, base["expert"] - base["random"])
        metrics = {"return": ret, "ep_len": ln, "score": score, "random": base["random"], "expert": base["expert"]}
    return {"model": model_name, "task": task_name, "seed": seed, "group": task.spec.group,
            "params": count_params(model), "width": model.width_used, "updates": updates,
            "train_time": round(train_time, 1), "eval_time": round(time.time() - t0 - train_time, 1),
            **{k: (round(v, 5) if isinstance(v, float) else v) for k, v in metrics.items()}, "curve": curve}
