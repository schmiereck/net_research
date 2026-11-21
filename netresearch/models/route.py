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
"""
import torch
import torch.nn as nn

from . import N_CMD, build_model


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
    takes_cmd = False                                  # the task's command port is not wired through (not needed yet)

    def __init__(self, frozen, new, lateral_dim, new_dim):
        super().__init__()
        self.frozen, self.new = frozen, new
        for p in self.frozen.parameters():
            p.requires_grad_(False)
        self.lat = nn.Linear(lateral_dim, N_CMD)
        self.gate = nn.Linear(new_dim, 1)
        nn.init.zeros_(self.gate.weight)
        nn.init.zeros_(self.gate.bias)                 # starts at g = 0.5
        self.tap_old, self.tap_new = _Tap(frozen.head), _Tap(new.head)
        self.n_old = None
        self.width_used = getattr(new, "width_used", None)
        self.cmd = None

    def init_state(self, batch, device="cpu"):
        so = self.frozen.init_state(batch, device) if self.frozen.stateful else ()
        sn = self.new.init_state(batch, device) if self.new.stateful else ()
        self.n_old = len(so)
        return tuple(so) + tuple(sn)

    def forward(self, x, state):
        so, sn = state[:self.n_old], state[self.n_old:]
        self.frozen.eval()                             # no dropout / no running statistics in the frozen net
        with torch.no_grad():
            out_old, so = self.frozen(x, so)
            lat = self.tap_old.value
        self.new.cmd = self.lat(lat.detach())
        try:
            out_new, sn = self.new(x, sn)
        finally:
            self.new.cmd = None
        g = torch.sigmoid(self.gate(self.tap_new.value))
        return g * out_old.detach() + (1 - g) * out_new, tuple(so) + tuple(sn)


def _top_dim(model):
    """Size of the head's input (the lateral signal)."""
    h = model.head
    first = h[0] if isinstance(h, nn.Sequential) else h
    return first.in_features


def freeze_and_route(frozen, name, target_params=100_000, seed=0):
    """Wrap a trained (or, as a control, untrained) net: frozen + a new module of the same kind with a port."""
    new = build_model(port_name(name), target_params, seed=seed + 7919)
    return FrozenRoute(frozen, new, _top_dim(frozen), _top_dim(new))
