"""Scratchpad memory: every module owns n memory values that it reads as extra input and writes explicitly.

Write rule per value (two outputs per value, applied in this order):
    m <- mult * m + add,   mult = sigmoid(.) in (0,1),   add = tanh(.) in (-1,1)
mult ~ 1, add ~ 0 : keep          mult ~ 0, add = a : set to a
mult ~ 1, add = a : accumulate    mult = s          : scale (decay)
mult is limited to <= 1 so values cannot explode (|m| <= 1/(1-mult)); the mult bias starts at +3 (keep),
which gives a long memory at init and an "error carousel" for BPTT gradients like an LSTM cell.

Global scratchpad (optional): the first g values of every module's scratchpad are concatenated and fed to
every module (state of the previous time step), so modules can read each other's notes.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..spec import N_OUT, OBS_DIM
from .basic import Model

MULT_BIAS = 3.0


def write_memory(m, raw):
    """m [B,n], raw [B,2n] -> new m."""
    mult, add = raw.chunk(2, -1)
    return torch.sigmoid(mult) * m + torch.tanh(add)


def init_write_head(lin, n):
    """Small write weights, mult bias -> keep, add bias 0."""
    with torch.no_grad():
        lin.weight[-2 * n:] *= 0.1
        lin.bias[-2 * n:-n] = MULT_BIAS
        lin.bias[-n:] = 0.0


class MLPScratch(Model):
    """MLP (2 hidden layers) + one scratchpad of n values."""
    stateful = True

    def __init__(self, width=110, n_mem=16):
        super().__init__()
        self.n = n_mem
        self.net = nn.Sequential(nn.Linear(OBS_DIM + n_mem, width), nn.GELU(),
                                 nn.Linear(width, width), nn.GELU(), nn.Linear(width, N_OUT + 2 * n_mem))
        init_write_head(self.net[-1], n_mem)

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.n, device=device),)

    def forward(self, x, state):
        m = state[0]
        o = self.net(torch.cat([x.flatten(1), m], -1))
        return o[:, :N_OUT], (write_memory(m, o[:, N_OUT:]),)


class ScratchBusModule(nn.Module):
    """Additive bus module that also reads its own scratchpad (+ global notes) and writes its scratchpad."""

    def __init__(self, d, hidden, n_mem, n_global_in):
        super().__init__()
        self.n = n_mem
        self.ln = nn.LayerNorm(d)
        self.fc1 = nn.Linear(d + n_mem + n_global_in, hidden)
        self.fc2 = nn.Linear(hidden, d + 2 * n_mem)
        with torch.no_grad():
            self.fc2.weight[:d].zero_()
            self.fc2.bias[:d].zero_()
        init_write_head(self.fc2, n_mem)

    def forward(self, B, m, g):
        h = F.gelu(self.fc1(torch.cat([self.ln(B), m, g], -1)))
        o = self.fc2(h)
        d = B.shape[-1]
        return B + o[:, :d], write_memory(m, o[:, d:])


class BusScratch(Model):
    """Additive bus (depth positions) where every position has its own scratchpad of n values.
    shared=True: one module (same weights) at every position; the scratchpads stay per position.
    n_global: values per position that are published to all positions (0 = no global scratchpad)."""
    stateful = True

    def __init__(self, width=64, shared=True, depth=6, n_mem=16, n_global=0):
        super().__init__()
        self.depth, self.n, self.g = depth, n_mem, n_global
        self.enc = nn.Sequential(nn.Flatten(), nn.Linear(OBS_DIM, width))
        make = lambda: ScratchBusModule(width, 2 * width, n_mem, depth * n_global)
        self.mods = nn.ModuleList([make()] if shared else [make() for _ in range(depth)])
        self.ln = nn.LayerNorm(width)
        self.head = nn.Linear(width, N_OUT)

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.depth, self.n, device=device),)

    def forward(self, x, state):
        M = state[0]                                       # [B, depth, n]
        G = M[:, :, :self.g].flatten(1)                    # notes of all positions from the previous step
        B = self.enc(x)
        new = []
        for i in range(self.depth):
            B, m = self.mods[0 if len(self.mods) == 1 else i](B, M[:, i], G)
            new.append(m)
        return self.head(self.ln(B)), (torch.stack(new, 1),)
