"""Grid-structured modular networks: Layer grid and Hierarchical (checkerboard) grid.

Both take the input as C vertical image strips (one per column) entering at the top, and read the output
from the bottom row(s). Lateral / upward connections use the previous tick's values -> built-in recurrence.

shared=True  : one module (same weights) at every grid position
shared=False : individual weights per position

Optional scratchpad (models/scratchpad.py): n_mem values per module (read as input, written with
m <- mult*m + add) and one global scratchpad of n_global values that every module reads and all modules
write together (their raw write proposals are averaged), so its size does not grow with the grid.

Key/value scratchpad (slots > 0, KVMemory): every module owns a small table of `slots` rows x n values.
A global key network looks at the encoded input and chooses per write head WHICH row is written (soft
key = strength * softmax) and per read head which row is read (query = softmax); every module reads the
addressed rows of its own table and writes WHAT goes there (its local part of the value) with the same
mult/add rule, applied only at the addressed row. So content (the key seen in the input) addresses memory,
and the value stays distributed over the modules ("global key, local value").
Finding: this softmax row choice collapses (all keys end up on one row), see AGENDA.md.

Allocating key/value scratchpad (alloc=True, AllocMemory): rows are not chosen by the key; a write goes to
the least-used row (usage count, like a free list) with a learned write strength, and the row also stores
a global key vector. Reading compares a query vector with the stored keys (dot-product attention over the
used rows). The values are still distributed over the modules and written with the mult/add rule.
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


# fixed neighbourhood (row offset, column offset) whose scratchpads a module may read in "neigh" mode
NEIGH = {"layer": [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)],
         "hier": [(-2, 0), (-1, -1), (-1, 1), (0, -2), (0, 2), (1, -1), (1, 1), (2, 0)]}


class MemoryReader(nn.Module):
    """How a module reads the scratchpads of other modules (previous tick), in addition to its own.
    Every module still writes only its own scratchpad, so there are no write conflicts.
      neigh: the scratchpads of its 8 nearest modules (fixed offsets, zeros at the borders) -> 8n values
      addr : every scratchpad has a learned address; the module emits `heads` query vectors from its input and
             reads per query the best-matching scratchpad (softmax over the top-k matches only) -> heads*n values
    Memory M is dense over the grid [B,R,C,n] (unused checkerboard positions of the hier grid stay zero)."""

    def __init__(self, mode, grid, R, C, K, n, in_dim, shared, heads=4, a=8, topk=3):
        super().__init__()
        self.mode, self.n = mode, n
        self.extra = 0
        if mode == "neigh":
            self.offsets = NEIGH[grid]
            self.extra = len(self.offsets) * n
        elif mode == "addr":
            self.heads, self.a, self.topk = heads, a, topk
            pos = [r * C + c for r in range(R) for c in range(C) if grid == "layer" or (r + c) % 2 == 0]
            self.register_buffer("slots", torch.tensor(pos), persistent=False)
            self.addr = nn.Parameter(torch.randn(len(pos), a))
            self.q = CellLinear(R, K, in_dim, heads * a, shared)
            self.extra = heads * n
        elif mode:
            raise ValueError(mode)

    def prepare(self, M):
        if self.mode == "neigh":
            return F.pad(M, (0, 0, 2, 2, 2, 2))
        if self.mode == "addr":
            return M.flatten(1, 2)[:, self.slots]                    # B,P,n
        return None

    def read(self, ctx, r, cols, inp):
        if self.mode == "neigh":
            return torch.cat([ctx[:, r + 2 + dr, cols + 2 + dc] for dr, dc in self.offsets], -1)
        B, K = inp.shape[:2]
        q = self.q(inp, r).view(B, K, self.heads, self.a)
        s = torch.einsum("bkha,pa->bkhp", q, self.addr) / math.sqrt(self.a)
        top = s.topk(self.topk, -1)
        w = torch.full_like(s, float("-inf")).scatter(-1, top.indices, top.values).softmax(-1)
        return torch.einsum("bkhp,bpn->bkhn", w, ctx).reshape(B, K, -1)


class KVMemory(nn.Module):
    """Content-addressed scratchpad: per module a table A [slots, n]; `heads` write and read heads.

    keys(e)        : e = flattened encoder output -> write keys kw [B,H,a] (= sigmoid strength * softmax)
                     and read queries qr [B,H,a] (softmax), shared by all modules of the grid
    read(A, qr)    : A [B,K,a,n] -> [B,K,H*n]      (row mix A^T q per head)
    write(A,kw,raw): raw [B,K,2*H*n] = [mult | add] -> new A; per head h with key k:
                     A <- A + k (x) ((sigmoid(mult) - 1) * A^T k + tanh(add))
                     for a one-hot key this is exactly row <- sigmoid(mult)*row + tanh(add), other rows kept
    """

    def __init__(self, enc_dim, n, slots, heads):
        super().__init__()
        self.n, self.a, self.h = n, slots, heads
        self.key = nn.Linear(enc_dim, heads * (2 * slots + 1))

    n_state = 0                                                      # extra global state tensors

    def init_extra(self, batch, device):
        return ()

    def address(self, e, extra):
        """-> write keys kw [B,H,a], read weights qr [B,H,a], new extra state."""
        z = self.key(e).view(e.shape[0], self.h, 2 * self.a + 1)
        kw = torch.sigmoid(z[..., :1]) * z[..., 1:self.a + 1].softmax(-1)
        return kw, z[..., self.a + 1:].softmax(-1), ()

    def read(self, A, qr):
        B, K = A.shape[:2]
        return torch.einsum("bkan,bha->bkhn", A, qr).reshape(B, K, -1)

    def write(self, A, kw, raw):
        B, K = A.shape[:2]
        mult, add = raw.reshape(B, K, 2, self.h, self.n).unbind(2)
        for h in range(self.h):
            k = kw[:, h]                                             # B,a
            old = torch.einsum("bkan,ba->bkn", A, k)
            upd = (torch.sigmoid(mult[:, :, h]) - 1) * old + torch.tanh(add[:, :, h])
            A = A + k[:, None, :, None] * upd[:, :, None]
        return A


class AllocMemory(KVMemory):
    """Rows are allocated, not chosen: write head h writes to the h-th least-used row with strength beta_h and
    stores its key vector there; read head h attends over the used rows by query . key (+ log usage, so empty
    rows are ignored and weakly written rows count less). Extra state: keys Km [B,a,dk], usage U [B,a]."""
    n_state = 2

    def __init__(self, enc_dim, n, slots, heads, dk=16):
        nn.Module.__init__(self)
        self.n, self.a, self.h, self.dk = n, slots, heads, dk
        self.key = nn.Linear(enc_dim, heads * (1 + 2 * dk))
        self.register_buffer("tie", torch.arange(slots) * 1e-4, persistent=False)   # ties -> lowest row

    def init_extra(self, batch, device):
        return (torch.zeros(batch, self.a, self.dk, device=device), torch.zeros(batch, self.a, device=device))

    def address(self, e, extra):
        Km, U = extra
        z = self.key(e).view(e.shape[0], self.h, 1 + 2 * self.dk)
        beta = torch.sigmoid(z[..., :1])                             # B,H,1
        kappa, q = z[..., 1:1 + self.dk], z[..., 1 + self.dk:]
        s = torch.einsum("bhd,bad->bha", q, Km) / math.sqrt(self.dk) + torch.log(U + 1e-6)[:, None]
        qr = s.softmax(-1) * (U.sum(-1) > 1e-3).float()[:, None, None]    # nothing stored -> read zeros
        free = (U + self.tie).topk(self.h, -1, largest=False).indices      # B,H least-used rows
        kw = beta * F.one_hot(free, self.a).float()                  # B,H,a
        w = kw.sum(1)                                                # B,a (rows of different heads differ)
        Km = Km * (1 - w)[..., None] + torch.einsum("bha,bhd->bad", kw, kappa)
        U = U * (1 - w) + w
        return kw, qr, (Km, U)


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

    def __init__(self, width=16, shared=False, R=4, C=8, n_mem=0, n_global=0, read="", slots=0, heads=1,
                 alloc=False):
        super().__init__()
        assert not (slots and read), "key/value scratchpad and neighbour/address reading are separate variants"
        self.R, self.C, self.d = R, C, width
        self.n, self.g, self.slots = n_mem, n_global, slots
        self.nl = nl = n_mem * heads if slots else n_mem             # own-memory values read / written
        h = 2 * width
        self.enc = StripEncoder(C, width, 1)
        self.kv = (AllocMemory if alloc else KVMemory)(C * width, n_mem, slots, heads) if slots else None
        self.reader = MemoryReader(read, "layer", R, C, C, n_mem, 5 * width, shared)
        self.register_buffer("cols", torch.arange(C), persistent=False)
        self.fc1 = CellLinear(R, C, 5 * width + nl + n_global + self.reader.extra, h, shared)
        self.fc2 = CellLinear(R, C, h, width + 2 * (nl + n_global), shared, zero=True)
        init_write_bias(self.fc2, width, nl, n_global)
        self.ln = nn.LayerNorm(C * width)
        self.head = nn.Linear(C * width, N_OUT)

    def init_state(self, batch, device="cpu"):
        st = (torch.zeros(batch, self.R, self.C, self.d, device=device),)
        if self.n or self.g:
            cell = (self.slots, self.n) if self.slots else (self.n,)
            st += (torch.zeros(batch, self.R, self.C, *cell, device=device),
                   torch.zeros(batch, self.g, device=device))
            if self.kv:
                st += self.kv.init_extra(batch, device)
        return st

    def forward(self, x, state):
        prev = state[0]
        mem = len(state) > 1
        if mem:
            M, G = state[1], state[2]
            Gx = G[:, None].expand(-1, self.C, -1)
            ctx = self.reader.prepare(M)
        e = self.enc(x)
        if mem and self.kv:
            kw, qr, ext = self.kv.address(e.flatten(1), state[3:])
        above = e[:, 0]                                              # B,C,d
        rows, new_m, graw = [], [], []
        for r in range(self.R):
            pa = F.pad(above, (0, 0, 1, 1))                          # pad columns
            lat = F.pad(prev[:, r], (0, 0, 1, 1))
            inp = torch.cat([pa[:, :-2], pa[:, 1:-1], pa[:, 2:], lat[:, :-2], lat[:, 2:]], -1)  # LP,P,RP,L,R
            inp = F.layer_norm(inp, inp.shape[-1:])
            if mem:
                parts = [inp, self.kv.read(M[:, r], qr) if self.kv else M[:, r], Gx]
                if self.reader.extra:
                    parts.append(self.reader.read(ctx, r, self.cols, inp))
                inp = torch.cat(parts, -1)
            o = self.fc2(F.gelu(self.fc1(inp, r)), r)
            if mem:
                o, wl, wg = split_writes(o, self.d, self.nl)
                new_m.append(self.kv.write(M[:, r], kw, wl) if self.kv else write_memory(M[:, r], wl))
                graw.append(wg)
            out = above + o                                          # vertical residual from P
            rows.append(out)
            above = out
        st = (torch.stack(rows, 1),)
        if mem:
            st += (torch.stack(new_m, 1), global_write(G, graw) if self.g else G)
            if self.kv:
                st += ext
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

    def __init__(self, width=12, shared=False, R=6, C=8, ticks=1, zero_init=False, n_mem=0, n_global=0, read="",
                 slots=0, heads=1, alloc=False):
        super().__init__()
        assert C % 2 == 0
        assert not (slots and read), "key/value scratchpad and neighbour/address reading are separate variants"
        self.R, self.C, self.d, self.ticks = R, C, width, ticks
        self.n, self.g, self.slots = n_mem, n_global, slots
        self.nl = nl = n_mem * heads if slots else n_mem
        self.K = C // 2
        h = 2 * width
        self.enc = StripEncoder(C, width, 2)
        self.kv = (AllocMemory if alloc else KVMemory)(2 * C * width, n_mem, slots, heads) if slots else None
        self.reader = MemoryReader(read, "hier", R, C, self.K, n_mem, 4 * width, shared)
        self.fc1 = CellLinear(R, self.K, 4 * width + nl + n_global + self.reader.extra, h, shared)
        self.fc2 = CellLinear(R, self.K, h, 4 * width + 2 * (nl + n_global), shared, zero=zero_init)
        init_write_bias(self.fc2, 4 * width, nl, n_global)
        self.ln = nn.LayerNorm(C * width)
        self.head = nn.Linear(C * width, N_OUT)
        for r in range(R):
            self.register_buffer(f"cols{r}", torch.arange(r % 2, C, 2), persistent=False)

    def init_state(self, batch, device="cpu"):
        # ORP outputs of every row from the previous tick, dense over padded columns
        st = (torch.zeros(batch, self.R, self.C + 2, self.d, device=device),)
        if self.n or self.g:
            cell = (self.slots, self.n) if self.slots else (self.n,)
            st += (torch.zeros(batch, self.R, self.C, *cell, device=device),    # dense, unused positions = 0
                   torch.zeros(batch, self.g, device=device))
            if self.kv:
                st += self.kv.init_extra(batch, device)
        return st

    def _tick(self, virt, prev_orp, M=None, G=None, keys=None):
        B = virt.shape[0]
        # dense padded rows: index c+1 holds column c; slot dim = 4 outputs
        vrows = [F.pad(virt[:, i], (0, 0, 1, 1))[:, :, None].expand(-1, -1, 4, -1) for i in range(2)]
        rows = []                                                    # computed rows, dense [B, C+2, 4, d]
        mem = M is not None
        new_m, graw = [], []
        if mem:
            Gx = G[:, None].expand(-1, self.K, -1)
            ctx = self.reader.prepare(M)

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
                own = M[:, r, cols]                                  # B,K,n  (kv: B,K,a,n)
                parts = [inp, self.kv.read(own, keys[1]) if self.kv else own, Gx]
                if self.reader.extra:
                    parts.append(self.reader.read(ctx, r, cols, inp))
                inp = torch.cat(parts, -1)
            out = self.fc2(F.gelu(self.fc1(inp, r)), r)
            if mem:
                out, wl, wg = split_writes(out, 4 * self.d, self.nl)
                w = self.kv.write(own, keys[0], wl) if self.kv else write_memory(own, wl)
                new_m.append(torch.zeros_like(M[:, r]).index_copy(1, cols, w))
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
        keys, ext = None, ()
        if self.kv and M is not None:
            *keys, ext = self.kv.address(virt.flatten(1), state[3:])
        for _ in range(self.ticks):
            bottom, orp, M, G = self._tick(virt, orp, M, G, keys)
        st = (orp,) if M is None else (orp, M, G, *ext)
        return self.head(self.ln(bottom.flatten(1))), st
