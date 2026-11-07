"""Gradient diagnostics for weight sharing.

position_grad_stats: for a shared model ("_s"), the gradient of the shared module is the sum of the gradients
    contributed by every position (injection point / grid cell) that uses it. We split it: the shared model is
    copied into its individual counterpart ("_i", same width) with every position initialised to the shared
    weights; one backward pass then yields each position's gradient separately (the forward is identical).
    Pairwise cosine similarity between positions shows whether the positions pull the module in the same
    direction (cos > 0) or against each other (cos < 0 = conflict).

task_grad_cosine: cosine similarity between the full-model gradients of different tasks (multi-task runs).
"""
import re

import numpy as np
import torch

from .models import MODELS, SHARED_TO_INDIVIDUAL


def expand_shared(model, name):
    """Shared model -> (individual-weights copy with identical function, list of position-param groups)."""
    ind_name = SHARED_TO_INDIVIDUAL[name]
    ind = MODELS[ind_name][0](width=model.width_used)
    s_sd, i_sd = model.state_dict(), ind.state_dict()
    new = {}
    for k, v in i_sd.items():
        sk = re.sub(r"^mods\.\d+\.", "mods.0.", k)
        sv = s_sd[sk]
        if sv.shape == v.shape:
            new[k] = sv.clone()
        else:                                            # grid: [R, K, ...] individual vs [...] shared
            new[k] = sv.expand(*v.shape[:2], *sv.shape).clone()
    ind.load_state_dict(new)
    return ind


def _position_grads(ind):
    """Per-position flattened gradient vectors [P, D] of the (expanded) module parameters."""
    if hasattr(ind, "mods"):                              # bus: position = injection point
        return torch.stack([torch.cat([p.grad.flatten() for p in m.parameters()]) for m in ind.mods])
    parts = []                                           # grid: position = (row, cell)
    for lin in (ind.fc1, ind.fc2):
        for p in (lin.w, lin.b):
            parts.append(p.grad.reshape(p.shape[0] * p.shape[1], -1))
    return torch.cat(parts, 1)


def _cos_stats(G):
    n = G.norm(dim=1)
    Gn = G / n.clamp_min(1e-12)[:, None]
    C = Gn @ Gn.T
    P = len(G)
    off = C[~torch.eye(P, dtype=torch.bool)]
    total = G.sum(0)
    align = (Gn @ (total / total.norm().clamp_min(1e-12)))
    return {"mean_cos": round(off.mean().item(), 4), "frac_neg": round((off < 0).float().mean().item(), 4),
            "align": [round(a, 3) for a in align.tolist()], "norm": [round(x, 5) for x in n.tolist()]}


def position_grad_stats(model, name, loss_fn):
    """loss_fn(model) -> scalar loss on a fixed batch. Returns cosine statistics between positions."""
    ind = expand_shared(model, name)
    ind.train()
    ind.zero_grad()
    loss_fn(ind).backward()
    G = _position_grads(ind)
    stats = _cos_stats(G)
    if not hasattr(ind, "mods"):
        stats["grid"] = [ind.fc1.w.shape[0], ind.fc1.w.shape[1]]       # positions are row-major (R, K)
    return stats


def _real(g):
    return (torch.view_as_real(g) if g.is_complex() else g).flatten()


def task_grad_cosine(model, loss_fns):
    """loss_fns: list of loss_fn(model). Returns the [T, T] cosine matrix of the full-model gradients."""
    gs = []
    for fn in loss_fns:
        model.zero_grad()
        fn(model).backward()
        gs.append(torch.cat([_real(p.grad if p.grad is not None else torch.zeros_like(p))
                             for p in model.parameters()]))
    model.zero_grad()
    G = torch.stack(gs)
    Gn = G / G.norm(dim=1).clamp_min(1e-12)[:, None]
    return [[round(float(x), 3) for x in row] for row in (Gn @ Gn.T).tolist()]
