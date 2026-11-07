"""Grid-structured modular networks: Layer grid and Hierarchical (checkerboard) grid.

Both take the input as C vertical image strips (one per column) entering at the top, and read the output
from the bottom row(s). Lateral / upward connections use the previous tick's values -> built-in recurrence.

shared=True  : one module (same weights) at every grid position
shared=False : individual weights per position

Optional scratchpad (models/scratchpad.py): n_mem values per module (read as input, written with
m <- mult*m + add) and one global scratchpad of n_global values that every module reads and all modules
write together (their raw write proposals are averaged), so its size does not grow with the grid.
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..spec import N_OUT
from .basic import Model
from .scratchpad import MULT_BIAS, write_memory


class CellLinear(nn.Module):
    """Linear layer for a row of K cells, either shared or with per-(row, cell) weights."""

    def __init__(self, rows, cells, n_in, n_out, shared, zero=False):
        super().__init__()
        self.shared = shared
        shape = (n_in, n_out) if shared else (rows, cells, n_in, n_out)
        w = torch.randn(*shape) / math.sqrt(n_in)
        self.w = nn.Parameter(torch.zeros(*shape) if zero else w)
        self.b = nn.Parameter(torch.zeros(n_out if shared else (rows, cells, n_out)))

    def forward(self, x, r):          # x [B, K, n_in]
        if self.shared:
            return x @ self.w + self.b
        return torch.einsum("bki,kio->bko", x, self.w[r]) + self.b[r]


def init_write_bias(lin, d_out, n_mem, n_global):
    """The outputs after d_out are scratchpad writes [mult|add] (local n_mem, then global n_global):
    mult bias -> keep, small weights."""
    with torch.no_grad():
        for start, n in ((d_out, n_mem), (d_out + 2 * n_mem, n_global)):
            if n:
                lin.b[..., start:start + n] = MULT_BIAS
                lin.w[..., start:start + 2 * n] *= 0.1


def split_writes(o, d_out, n_mem):
    """o [B,K,d_out + 2n + 2g] -> main output, local write raw [B,K,2n], global write raw [B,K,2g]."""
    return o[..., :d_out], o[..., d_out:d_out + 2 * n_mem], o[..., d_out + 2 * n_mem:]


def global_write(G, raws):
    """Every module proposes a write for the global scratchpad; the raw proposals are averaged."""
    return write_memory(G, torch.cat(raws, 1).mean(1))


class StripEncoder(nn.Module):
    """16x16 image -> C column strips -> n_rows virtual input rows of d-vectors per column."""

    def __init__(self, C, d, n_rows):
        super().__init__()
        assert 16 % C == 0
        self.C, self.d, self.n_rows = C, d, n_rows
        self.sw = 16 // C
        self.lin = nn.Linear(3 * 16 * self.sw, n_rows * d)
        self.pos = nn.Parameter(torch.randn(1, C, n_rows * d) * 0.1)

    def forward(self, x):
        B = x.shape[0]
        s = x.reshape(B, 3, 16, self.C, self.sw).permute(0, 3, 1, 2, 4).reshape(B, self.C, -1)
        e = torch.tanh(self.lin(s) + self.pos)                       # B,C,n_rows*d
        return e.reshape(B, self.C, self.n_rows, self.d).permute(0, 2, 1, 3)   # B,n_rows,C,d


class LayerGrid(Model):
    """R rows x C columns. Cell X(r,c) reads LP, P, RP from row r-1 (current tick) and L, R from its own
    row (previous tick); output d-vector. Row -1 is the strip encoder. Head reads the last row."""
    stateful = True

    def __init__(self, width=16, shared=False, R=4, C=8, n_mem=0, n_global=0):
        super().__init__()
        self.R, self.C, self.d = R, C, width
        self.n, self.g = n_mem, n_global
        h = 2 * width
        self.enc = StripEncoder(C, width, 1)
        self.fc1 = CellLinear(R, C, 5 * width + n_mem + n_global, h, shared)
        self.fc2 = CellLinear(R, C, h, width + 2 * (n_mem + n_global), shared, zero=True)
        init_write_bias(self.fc2, width, n_mem, n_global)
        self.ln = nn.LayerNorm(C * width)
        self.head = nn.Linear(C * width, N_OUT)

    def init_state(self, batch, device="cpu"):
        st = (torch.zeros(batch, self.R, self.C, self.d, device=device),)
        if self.n or self.g:
            st += (torch.zeros(batch, self.R, self.C, self.n, device=device),
                   torch.zeros(batch, self.g, device=device))
        return st

    def forward(self, x, state):
        prev = state[0]
        mem = len(state) > 1
        if mem:
            M, G = state[1], state[2]
            Gx = G[:, None].expand(-1, self.C, -1)
        above = self.enc(x)[:, 0]                                    # B,C,d
        rows, new_m, graw = [], [], []
        for r in range(self.R):
            pa = F.pad(above, (0, 0, 1, 1))                          # pad columns
            lat = F.pad(prev[:, r], (0, 0, 1, 1))
            inp = torch.cat([pa[:, :-2], pa[:, 1:-1], pa[:, 2:], lat[:, :-2], lat[:, 2:]], -1)  # LP,P,RP,L,R
            inp = F.layer_norm(inp, inp.shape[-1:])
            if mem:
                inp = torch.cat([inp, M[:, r], Gx], -1)
            o = self.fc2(F.gelu(self.fc1(inp, r)), r)
            if mem:
                o, wl, wg = split_writes(o, self.d, self.n)
                new_m.append(write_memory(M[:, r], wl))
                graw.append(wg)
            out = above + o                                          # vertical residual from P
            rows.append(out)
            above = out
        st = (torch.stack(rows, 1),)
        if mem:
            st += (torch.stack(new_m, 1), global_write(G, graw) if self.g else G)
        return self.head(self.ln(above.flatten(1))), st


# output slot order of a hierarchical module
OLS, OS, ORS, ORP = range(4)


class HierGrid(Model):
    """Hierarchical checkerboard grid (see NetResearch.md). Modules at (r, c) with (r + c) even.

    Inputs of X(r,c):  IP  <- P(r-2,c).OS        ILP <- LP(r-1,c-1).ORS
                       IRP <- RP(r-1,c+1).OLS    ILS <- LS(r+1,c-1).ORP  (previous tick: upward/recurrent)
    Outputs: OLS, OS, ORS, ORP.  Rows are computed top-down within a tick.
    Two virtual rows (-2, -1) above the grid carry the encoded input; the OS outputs of the last two rows
    (one module per column) form the network output. Missing neighbours at the borders are zeros.
    """
    stateful = True

    def __init__(self, width=12, shared=False, R=6, C=8, ticks=1, zero_init=False, n_mem=0, n_global=0):
        super().__init__()
        assert C % 2 == 0
        self.R, self.C, self.d, self.ticks = R, C, width, ticks
        self.n, self.g = n_mem, n_global
        self.K = C // 2
        h = 2 * width
        self.enc = StripEncoder(C, width, 2)
        self.fc1 = CellLinear(R, self.K, 4 * width + n_mem + n_global, h, shared)
        self.fc2 = CellLinear(R, self.K, h, 4 * width + 2 * (n_mem + n_global), shared, zero=zero_init)
        init_write_bias(self.fc2, 4 * width, n_mem, n_global)
        self.ln = nn.LayerNorm(C * width)
        self.head = nn.Linear(C * width, N_OUT)
        for r in range(R):
            self.register_buffer(f"cols{r}", torch.arange(r % 2, C, 2), persistent=False)

    def init_state(self, batch, device="cpu"):
        # ORP outputs of every row from the previous tick, dense over padded columns
        st = (torch.zeros(batch, self.R, self.C + 2, self.d, device=device),)
        if self.n or self.g:
            st += (torch.zeros(batch, self.R, self.K, self.n, device=device),
                   torch.zeros(batch, self.g, device=device))
        return st

    def _tick(self, virt, prev_orp, M=None, G=None):
        B = virt.shape[0]
        # dense padded rows: index c+1 holds column c; slot dim = 4 outputs
        vrows = [F.pad(virt[:, i], (0, 0, 1, 1))[:, :, None].expand(-1, -1, 4, -1) for i in range(2)]
        rows = []                                                    # computed rows, dense [B, C+2, 4, d]
        mem = M is not None
        new_m, graw = [], []
        if mem:
            Gx = G[:, None].expand(-1, self.K, -1)

        def row(i):
            return vrows[i + 2] if i < 0 else rows[i]

        for r in range(self.R):
            cols = getattr(self, f"cols{r}")
            ip = row(r - 2)[:, cols + 1, OS]
            ilp = row(r - 1)[:, cols, ORS]
            irp = row(r - 1)[:, cols + 2, OLS]
            if r + 1 < self.R:
                ils = prev_orp[:, r + 1, cols]                       # column c-1 -> padded index c
            else:
                ils = torch.zeros_like(ip)
            inp = torch.cat([ils, ilp, ip, irp], -1)                 # B,K,4d  (ILS, ILP, IP, IRP)
            inp = F.layer_norm(inp, inp.shape[-1:])
            if mem:
                inp = torch.cat([inp, M[:, r], Gx], -1)
            out = self.fc2(F.gelu(self.fc1(inp, r)), r)
            if mem:
                out, wl, wg = split_writes(out, 4 * self.d, self.n)
                new_m.append(write_memory(M[:, r], wl))
                graw.append(wg)
            out = out.reshape(B, self.K, 4, self.d)
            out = out + torch.stack([torch.zeros_like(ip), ip, torch.zeros_like(ip), torch.zeros_like(ip)], 2)
            dense = torch.zeros(B, self.C + 2, 4, self.d, device=out.device, dtype=out.dtype)
            dense = dense.index_copy(1, cols + 1, out)
            rows.append(dense)
        orp = torch.stack([rw[:, :, ORP] for rw in rows], 1)         # B,R,C+2,d
        bottom = rows[-1][:, 1:-1, OS] + rows[-2][:, 1:-1, OS]       # one module per column
        if mem:
            M = torch.stack(new_m, 1)
            G = global_write(G, graw) if self.g else G
        return bottom, orp, M, G

    def forward(self, x, state):
        virt = self.enc(x)                                           # B,2,C,d
        orp = state[0]
        M, G = (state[1], state[2]) if len(state) > 1 else (None, None)
        for _ in range(self.ticks):
            bottom, orp, M, G = self._tick(virt, orp, M, G)
        st = (orp,) if M is None else (orp, M, G)
        return self.head(self.ln(bottom.flatten(1))), st
