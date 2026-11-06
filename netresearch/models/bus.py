"""Bus networks: a shared signal bus B; modules read from the bus and feed back at injection point A.

Injection modes (per module i, f_i = module MLP):
    add  : B <- B + f_i(B)                          (residual stream)
    mul  : B <- B * f_i(B),  f_i = 2*sigmoid(.)     (modulation / filter, initialised around 1)
    gate : B <- (1-G_i)*B + G_i*f_i(B)              (highway / GRU style)
    film : B <- gamma_i(B)*B + beta_i(B)            (FiLM)
shared=True: one module (same weights) at every injection point; otherwise individual modules.
"""
import torch
import torch.nn as nn

from ..spec import N_OUT, OBS_DIM
from .basic import Model


class BusModule(nn.Module):
    def __init__(self, d, hidden, mode):
        super().__init__()
        self.mode = mode
        self.ln = nn.LayerNorm(d)
        self.fc1 = nn.Linear(d, hidden)
        n_out = {"add": d, "mul": d, "gate": 2 * d, "film": 2 * d}[mode]
        self.fc2 = nn.Linear(hidden, n_out)
        if mode in ("add", "film", "gate"):
            nn.init.zeros_(self.fc2.weight)
            nn.init.zeros_(self.fc2.bias)
        if mode == "gate":
            with torch.no_grad():
                self.fc2.bias[d:] = -1.0       # gates start mostly closed

    def forward(self, B):
        h = torch.nn.functional.gelu(self.fc1(self.ln(B)))
        o = self.fc2(h)
        if self.mode == "add":
            return B + o
        if self.mode == "mul":
            return B * (2 * torch.sigmoid(o))
        if self.mode == "gate":
            f, g = o.chunk(2, -1)
            g = torch.sigmoid(g)
            return (1 - g) * B + g * f
        gamma, beta = o.chunk(2, -1)
        return (1 + gamma) * B + beta


class SubBusModule(nn.Module):
    """A module that internally is a small additive bus of sub-modules (Bus / Sub-Bus)."""
    def __init__(self, d, d_sub, n_sub=3):
        super().__init__()
        self.ln = nn.LayerNorm(d)
        self.down = nn.Linear(d, d_sub)
        self.subs = nn.ModuleList([BusModule(d_sub, 2 * d_sub, "add") for _ in range(n_sub)])
        self.up = nn.Linear(d_sub, d)
        nn.init.zeros_(self.up.weight)
        nn.init.zeros_(self.up.bias)

    def forward(self, B):
        s = self.down(self.ln(B))
        for m in self.subs:
            s = m(s)
        return B + self.up(s)


class BusNet(Model):
    def __init__(self, width=64, mode="add", shared=False, depth=6, sub=False):
        super().__init__()
        self.enc = nn.Sequential(nn.Flatten(), nn.Linear(OBS_DIM, width))
        self.depth = depth
        make = (lambda: SubBusModule(width, max(8, width // 2))) if sub else (lambda: BusModule(width, 2 * width, mode))
        self.mods = nn.ModuleList([make()] if shared else [make() for _ in range(depth)])
        self.ln = nn.LayerNorm(width)
        self.head = nn.Linear(width, N_OUT)

    def forward(self, x, state=()):
        B = self.enc(x)
        for i in range(self.depth):
            B = self.mods[0 if len(self.mods) == 1 else i](B)
        return self.head(self.ln(B)), state
