"""Freeze & Route (PLAN_TRAINER Phase C, T3 as a skill library on a bus).

A net that has learned a stage is frozen and becomes the first entry of a library. A new stage is learned by a
NEW module only:
    - the frozen net runs on the same input; what it hands its own head (its top representation: the last row
      of a grid, [e, h] of the gru) is the LATERAL signal;
    - a trainable linear map turns that signal into a command of N_CMD values, which enters the new module at
      its ordinary command port ('+cell' for grids, '+cmd' for other nets), the same interface every module has;
    - a trainable gate (one value per step, from the new module's own top representation) mixes the two outputs:
      out = g * out_frozen + (1 - g) * out_new.
Nothing flows back into the frozen net (requires_grad off, its outputs detached), so what it knew is kept exactly.

The lateral signal is only the top representation, not every layer (as in Progressive Networks): the same tap
exists for every architecture, and it is the place a module would publish to a bus.

The task's own input reaches both nets, each through its OWN front (decided with the user 2026-11-22, for the
gaze ladder): every net has its own retina ("+retN" / "+rezN") and its own address encoder ("+ref" / "+refl"), the
frozen one frozen, the new one trained (train.front per net). The frozen net gets its own command as before. The
new module's port carries the SUM of the lateral command and its own task command (from its address encoder or
the task's cmd): with "+refl" the encoder ends in a linear map, so the sum is a linear map of both side by side,
without a wider port. A net without a command port of its own takes no task command (as in run_sequence).
'+rv' in the new module: the task command is zeroed on steps without a picture (as usual), but the port's
pattern is not switched off there, since the lateral signal still flows.

Probes (curriculum word "freeze:<opt>", LOGBUCH 2026-11-21), each changes one thing:
    p64     the port carries 64 values instead of 16 (grids only)
    pfull   the port carries the whole top representation (as many values as it has; grids only)
    fc2     the new grid's second cell layer starts random (as in hier_s) instead of at zero (layer_s starts it at
            zero, so a fresh layer_s at first passes the encoder through and ignores every command)
    nogate  no gate: the output is the new module's alone
    pcell   every cell of the new grid reads the SAME cell of the frozen grid (16 values per cell, one shared
            linear map), not only the top representation: layer_s cell (r, c) its output, hier_s module (r, c) its
            ORP output (the part of a module's output the grid keeps in its state). Grids only.
Probes combine with '+' (e.g. "freeze:pcell+fc2"); only pcell+fc2 is allowed so far (the others change the port or
the gate and do not combine with pcell).

Selection by task ("freeze:sel", combines with every probe above; PLAN_TRAINER Phase C, user 2026-11-23): the
compound recognises from its input whether an episode belongs to the frozen entry's own task and then hands on the
frozen net's output alone. Without it the gate mixes both outputs on the old task too, and the compound forgets
it. No old data are kept: when the net is frozen, the entry publishes a STATISTIC of its own task, the mean and
covariance of its top representation over episodes of the task it has learned (fit_familiar, called by the
curriculum with the tasks of the phase before the freeze), and per step count n the 99% quantile of an episode's
mean Mahalanobis distance after n steps. In use the compound keeps that running mean per episode (two more state
values, reset with the episode): while it stays at or below the quantile, the episode counts as familiar and the
output is the frozen net's alone (s = 1); above it, it is the compound's (s = 0). The decision is hard, has no
gradient and is fixed after the freeze (familiarity, as the `novel` gate of 2026-11-09). A library of several
entries would route to the entry that finds the input familiar, else to the newest.
"""
import torch
import torch.nn as nn

import math

from . import MODELS, N_CMD, build_model, matched_width, split_size


def port_name(name):
    """The new module's name: the base net with a command port ('+cell' for grids, '+cmd' for the others)."""
    base, _, size = name.partition("@")
    grid = base.split("_")[0] in ("layer", "hier")
    suf = "+cell" if grid else "+cmd"
    return base + ("" if suf in base else suf) + (f"@{size}" if size else "")


class _Tap:
    """Catches the input of a module's head (its top representation) at every forward call."""

    def __init__(self, head):
        self.value = None
        head.register_forward_hook(self._hook)

    def _hook(self, mod, args, out):
        self.value = args[0]


class FrozenRoute(nn.Module):
    stateful = True
    own_front = True                                   # train.run_sequence hands the raw step input (step_in)

    def __init__(self, frozen, new, lateral_dim, new_dim, n_port=N_CMD, gate=True):
        super().__init__()
        self.frozen, self.new = frozen, new
        for p in self.frozen.parameters():
            p.requires_grad_(False)
        self.lat = nn.Linear(lateral_dim, n_port)
        self.use_gate = gate
        self.per_cell = False
        self.gate = nn.Linear(new_dim, 1)
        nn.init.zeros_(self.gate.weight)
        nn.init.zeros_(self.gate.bias)                 # starts at g = 0.5
        self.tap_old, self.tap_new = _Tap(frozen.head), _Tap(new.head)
        self.n_old = None
        self.width_used = getattr(new, "width_used", None)
        self.cmd = None
        self.step_in = None                            # (cmd, ref, ref_mask) of this step, each [1, B, ...] or None
        self.select = False                            # "sel": selection by task (fit_familiar sets the statistic)
        self.wants_select = False
        self.record = None                             # a list: forward appends s [B] of every step (diagnostics)

    def init_state(self, batch, device="cpu"):
        so = self.frozen.init_state(batch, device) if self.frozen.stateful else ()
        sn = self.new.init_state(batch, device) if self.new.stateful else ()
        self.n_old, self.n_new = len(so), len(sn)
        sel = (torch.zeros(batch, 1, device=device),) * 2 if self.select else ()   # sum of distances, step count
        return tuple(so) + tuple(sn) + sel

    def forward(self, x, state):
        from ..train import front                      # here, not at the top: train imports the models package
        so, sn = state[:self.n_old], state[self.n_old:self.n_old + self.n_new]
        sel = state[self.n_old + self.n_new:]
        cmd, ref, mask = self.step_in or (None, None, None)
        self.frozen.eval()                             # no dropout / no running statistics in the frozen net
        with torch.no_grad():
            xo, co, vo = front(self.frozen, x[None], cmd, ref, mask)
            self.frozen.cmd = None if co is None else co[0]
            self.frozen.cmd_valid = None if vo is None else vo[0]
            try:
                out_old, so = self.frozen(xo[0], so)
            finally:
                self.frozen.cmd, self.frozen.cmd_valid = None, None
            lat = cell_view(self.frozen, so) if self.per_cell else self.tap_old.value
        xn, cn, _ = front(self.new, x[None], cmd, ref, mask)
        c = self.lat(lat.detach())
        if cn is not None:                             # the sum in the port: lateral + the new module's own command
            cn = cn[0]
            c = c + (cn[:, None, None] if c.dim() == 4 else cn)
        self.new.cmd = c
        try:
            out_new, sn = self.new(xn[0], sn)
        finally:
            self.new.cmd = None
        if self.use_gate:
            g = torch.sigmoid(self.gate(self.tap_new.value))
            out = g * out_old.detach() + (1 - g) * out_new
        else:
            out = out_new
        if not self.select:
            return out, tuple(so) + tuple(sn)
        zsum, n = sel[0] + self.distance(self.tap_old.value.detach()), sel[1] + 1
        idx = n[:, 0].long().clamp(max=len(self.fam_thr)) - 1            # beyond the old task's length: the last
        s = ((zsum / n) <= self.fam_thr[idx]).float()                     # [B, 1], 1 = familiar -> frozen alone
        if self.record is not None:
            self.record.append(s[:, 0])
        return s * out_old.detach() + (1 - s) * out, tuple(so) + tuple(sn) + (zsum, n)

    def distance(self, h):
        """Squared Mahalanobis distance of top representations h [B, ...] to the frozen task's statistic, / D."""
        d = h.flatten(1) - self.fam_mean
        return ((d @ self.fam_prec) * d).sum(-1, keepdim=True) / d.shape[-1]


@torch.no_grad()
def fit_familiar(route, tasks, episodes=4096, quantile=0.99, shrink=0.1, seed=4243):
    """Selection by task ("freeze:sel"): the statistic of the frozen net's own task from `episodes` training
    episodes of `tasks` (the phase before the freeze) -> route.fam_mean, fam_prec, fam_thr; switches selection on.
    The covariance is shrunk towards its mean variance (share `shrink`). fam_thr[n - 1]: the quantile of an
    episode's mean distance after n steps (steps without a scored answer count too)."""
    import numpy as np
    from ..train import run_sequence, to_t
    was = route.training
    route.eval()
    route.select = False
    rng, runs, lats = np.random.default_rng(seed), [], []
    hook = route.frozen.head.register_forward_hook(lambda m, a, o: lats.append(a[0].flatten(1).double()))
    try:
        for t in tasks:
            for _ in range(max(1, episodes // len(tasks) // 256)):
                b = to_t(t.sample(256, rng))
                lats.clear()
                run_sequence(route, b["obs"].float(), cmd=b.get("cmd"), ref=b.get("ref"), ref_mask=b.get("ref_mask"))
                runs.append(torch.stack(lats))                              # [T, B, D] of this batch
    finally:
        hook.remove()
    x = torch.cat([r.reshape(-1, r.shape[-1]) for r in runs])
    mean = x.mean(0)
    cov = torch.cov((x - mean).T)
    cov = (1 - shrink) * cov + shrink * cov.diagonal().mean() * torch.eye(len(mean), dtype=cov.dtype)
    route.fam_mean, route.fam_prec = mean.float(), torch.linalg.inv(cov).float()
    zbar = [[] for _ in range(max(r.shape[0] for r in runs))]
    for r in runs:
        z = torch.stack([route.distance(r[t].float())[:, 0] for t in range(r.shape[0])])     # [T, B]
        zb = z.cumsum(0) / torch.arange(1, len(z) + 1)[:, None]
        for t in range(len(z)):
            zbar[t].append(zb[t])
    route.fam_thr = torch.stack([torch.quantile(torch.cat(v), quantile) for v in zbar])[:, None]
    route.select = True
    route.train(was)
    return route


@torch.no_grad()
def selection_share(route, task, n_batches=None):
    """Share of the scored steps of `task` (its test set) on which the compound hands on the frozen net alone."""
    from ..train import eval_set, run_sequence
    was = route.training
    route.eval()
    tot = frz = 0.0
    try:
        for b in eval_set(task)[:n_batches]:
            route.record = []
            run_sequence(route, b["obs"].float(), cmd=b.get("cmd"), ref=b.get("ref"), ref_mask=b.get("ref_mask"))
            s, m = torch.stack(route.record), b["mask"].float()
            frz += (s * m).sum().item()
            tot += m.sum().item()
    finally:
        route.record = None
        route.train(was)
    return frz / max(tot, 1.0)


def cell_view(grid, state):
    """What every cell of a grid hands on, from its state: [B, R, K, d] (layer: the row outputs; hier: the ORP
    output of the modules of each row, K = C / 2 modules per row)."""
    s = state[0]
    if hasattr(grid, "K"):                             # HierGrid: [B, R, C + 2, d], modules at cols{r} + 1
        return torch.stack([s[:, r, getattr(grid, f"cols{r}") + 1] for r in range(grid.R)], 1)
    return s


def _top_dim(model):
    """Size of the head's input (the lateral signal)."""
    h = model.head
    first = h[0] if isinstance(h, nn.Sequential) else h
    return first.in_features


def freeze_and_route(frozen, name, target_params=100_000, seed=0, opt=""):
    """Wrap a trained (or, as a control, untrained) net: frozen + a new module of the same kind with a port.
    opt: "" or one of the probes in the module docstring."""
    opts = set(opt.split("+")) - {""}
    sel = "sel" in opts                                # selection by task: combines with every probe
    opts -= {"sel"}
    opt = "+".join(sorted(opts))
    assert len(opts) <= 1 or opts == {"pcell", "fc2"}, f"unknown freeze option combination {opt}"
    assert opts <= {"p64", "pfull", "fc2", "nogate", "pcell"}, f"unknown freeze option {opt}"
    m = _build_route(frozen, name, target_params, seed, opt, opts)
    m.wants_select = sel                               # the curriculum then calls fit_familiar (it has the tasks)
    return m


def _build_route(frozen, name, target_params, seed, opt, opts):
    n_port = {"p64": 64, "pfull": _top_dim(frozen)}.get(opt, N_CMD)
    if n_port == N_CMD:
        new = build_model(port_name(name), target_params, seed=seed + 7919)
    else:                                              # a grid with a wider '+cell' port, same width as usual
        base = split_size(name)[0]
        assert base.split("_")[0] in ("layer", "hier"), "a wider port exists for grids only"
        assert base == name.partition("@")[0], "p64 / pfull build the bare grid, without the net's suffixes"
        width = matched_width(base, target_params)
        torch.manual_seed(seed + 7919)
        new = MODELS[base][0](width=width, n_cmd=n_port)
        new.width_used = width
    if "fc2" in opts:
        assert hasattr(new, "fc2"), "fc2 probe for grids only"
        with torch.no_grad():                          # the usual random start of CellLinear
            w = new.fc2.w
            w.copy_(torch.randn(w.shape, generator=torch.Generator().manual_seed(seed + 31)) / math.sqrt(w.shape[-2]))
    if "pcell" in opts:
        assert hasattr(frozen, "fc2"), "pcell for grids only"
        m = FrozenRoute(frozen, new, frozen.d, _top_dim(new), n_port=N_CMD)
        m.per_cell = True
        return m
    return FrozenRoute(frozen, new, _top_dim(frozen), _top_dim(new), n_port=n_port, gate=opt != "nogate")
