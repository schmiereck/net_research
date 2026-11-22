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

    def init_state(self, batch, device="cpu"):
        so = self.frozen.init_state(batch, device) if self.frozen.stateful else ()
        sn = self.new.init_state(batch, device) if self.new.stateful else ()
        self.n_old = len(so)
        return tuple(so) + tuple(sn)

    def forward(self, x, state):
        from ..train import front                      # here, not at the top: train imports the models package
        so, sn = state[:self.n_old], state[self.n_old:]
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
        if not self.use_gate:
            return out_new, tuple(so) + tuple(sn)
        g = torch.sigmoid(self.gate(self.tap_new.value))
        return g * out_old.detach() + (1 - g) * out_new, tuple(so) + tuple(sn)


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
    assert len(opts) <= 1 or opts == {"pcell", "fc2"}, f"unknown freeze option combination {opt}"
    assert opts <= {"p64", "pfull", "fc2", "nogate", "pcell"}, f"unknown freeze option {opt}"
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
