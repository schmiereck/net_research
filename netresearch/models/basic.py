"""Baseline architectures: MLP, CNN, complex-valued MLP, patch-attention, GRU, attention memory.

Model API:  init_state(B) -> tuple of tensors (batch first) or ();  forward(x[B,3,16,16], state) -> (logits[B,64], state)
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..spec import N_OUT, OBS_DIM


class Model(nn.Module):
    stateful = False

    def init_state(self, batch, device="cpu"):
        return ()


class MLP(Model):
    def __init__(self, width=110):
        super().__init__()
        self.net = nn.Sequential(nn.Flatten(), nn.Linear(OBS_DIM, width), nn.GELU(),
                                 nn.Linear(width, width), nn.GELU(), nn.Linear(width, N_OUT))

    def forward(self, x, state=()):
        return self.net(x), state


class CNN(Model):
    """coord=True: two extra input channels with the pixel x / y coordinate in [-1, 1] (CoordConv)."""

    def __init__(self, width=32, coord=False):
        super().__init__()
        c1, c2 = width // 2, width
        self.coord = coord
        if coord:
            ys, xs = torch.meshgrid(torch.linspace(-1, 1, 16), torch.linspace(-1, 1, 16), indexing="ij")
            self.register_buffer("xy", torch.stack([xs, ys])[None], persistent=False)
        self.net = nn.Sequential(
            nn.Conv2d(5 if coord else 3, c1, 3, padding=1), nn.GELU(),
            nn.Conv2d(c1, c2, 3, padding=1, stride=2), nn.GELU(),       # 8x8
            nn.Conv2d(c2, c2, 3, padding=1, stride=2), nn.GELU(),       # 4x4
            nn.Flatten(), nn.Linear(c2 * 16, 2 * width), nn.GELU(), nn.Linear(2 * width, N_OUT))

    def forward(self, x, state=()):
        if self.coord:
            x = torch.cat([x, self.xy.expand(x.shape[0], -1, -1, -1)], 1)
        return self.net(x), state


class ComplexLinear(nn.Module):
    def __init__(self, n_in, n_out):
        super().__init__()
        s = 1 / math.sqrt(n_in)
        self.w = nn.Parameter(torch.complex(torch.randn(n_out, n_in) * s / math.sqrt(2),
                                            torch.randn(n_out, n_in) * s / math.sqrt(2)))
        self.b = nn.Parameter(torch.zeros(n_out, dtype=torch.cfloat))

    def forward(self, z):
        return z @ self.w.T + self.b


class ModReLU(nn.Module):
    """modReLU(z) = relu(|z| + b) * z / |z| : keeps the phase, thresholds the magnitude."""
    def __init__(self, n):
        super().__init__()
        self.b = nn.Parameter(torch.zeros(n))

    def forward(self, z):
        mag = z.abs()
        return F.relu(mag + self.b) * z / (mag + 1e-6)


class CVNN(Model):
    """Complex-valued MLP: pixels enter as z = x + 0j, complex weights + modReLU,
    output = real linear head on [Re(z), Im(z)] of the last hidden layer."""
    def __init__(self, width=56):
        super().__init__()
        self.l1, self.a1 = ComplexLinear(OBS_DIM, width), ModReLU(width)
        self.l2, self.a2 = ComplexLinear(width, width), ModReLU(width)
        self.out = nn.Linear(2 * width, N_OUT)

    def forward(self, x, state=()):
        z = torch.complex(x.flatten(1), torch.zeros_like(x.flatten(1)))
        z = self.a2(self.l2(self.a1(self.l1(z))))
        return self.out(torch.cat([z.real, z.imag], dim=-1)), state


class TBlock(nn.Module):
    def __init__(self, d, heads=4):
        super().__init__()
        self.heads = heads
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.q, self.kv, self.o = nn.Linear(d, d), nn.Linear(d, 2 * d), nn.Linear(d, d)
        self.mlp = nn.Sequential(nn.Linear(d, 2 * d), nn.GELU(), nn.Linear(2 * d, d))

    def forward(self, x, key_padding_mask=None, query=None):
        """x [B,N,d] keys/values; query [B,M,d] (default: x); key_padding_mask [B,N] True = ignore."""
        q_in = x if query is None else query
        B, N, d = x.shape
        M, H = q_in.shape[1], self.heads
        h = self.ln1(x)
        q = self.q(self.ln1(q_in)).view(B, M, H, d // H).transpose(1, 2)
        k, v = self.kv(h).view(B, N, 2, H, d // H).permute(2, 0, 3, 1, 4)
        mask = None
        if key_padding_mask is not None:
            mask = torch.zeros(B, 1, 1, N, dtype=x.dtype, device=x.device)
            mask = mask.masked_fill(key_padding_mask[:, None, None, :], float("-inf"))
        a = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)
        out = q_in + self.o(a.transpose(1, 2).reshape(B, M, d))
        return out + self.mlp(self.ln2(out))


class ViT(Model):
    """Attention over 16 patches of 4x4 pixels (+ CLS token)."""
    def __init__(self, width=48, depth=3):
        super().__init__()
        self.embed = nn.Linear(3 * 16, width)
        self.pos = nn.Parameter(torch.randn(1, 17, width) * 0.02)
        self.cls = nn.Parameter(torch.zeros(1, 1, width))
        self.blocks = nn.ModuleList([TBlock(width) for _ in range(depth)])
        self.ln = nn.LayerNorm(width)
        self.head = nn.Linear(width, N_OUT)

    def forward(self, x, state=()):
        B = x.shape[0]
        p = x.unfold(2, 4, 4).unfold(3, 4, 4)                      # B,3,4,4,4,4
        p = p.permute(0, 2, 3, 1, 4, 5).reshape(B, 16, 48)
        h = torch.cat([self.cls.expand(B, -1, -1), self.embed(p)], 1) + self.pos
        for blk in self.blocks:
            h = blk(h)
        return self.head(self.ln(h[:, 0])), state


class GRUNet(Model):
    stateful = True

    def __init__(self, width=64):
        super().__init__()
        self.enc = nn.Sequential(nn.Flatten(), nn.Linear(OBS_DIM, width), nn.GELU())
        self.cell = nn.GRUCell(width, width)
        self.head = nn.Sequential(nn.Linear(2 * width, width), nn.GELU(), nn.Linear(width, N_OUT))
        self.width = width

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.width, device=device),)

    def forward(self, x, state):
        e = self.enc(x)
        h = self.cell(e, state[0])
        return self.head(torch.cat([e, h], -1)), (h,)


class AttnMem(Model):
    """Frame encoder + attention of the current frame over the embeddings of the last K frames."""
    stateful = True

    def __init__(self, width=48, K=16, depth=2):
        super().__init__()
        self.K, self.width = K, width
        self.enc = nn.Sequential(nn.Flatten(), nn.Linear(OBS_DIM, width), nn.GELU(), nn.Linear(width, width))
        self.age = nn.Parameter(torch.randn(1, K + 1, width) * 0.02)   # position = age of the memory slot
        self.blocks = nn.ModuleList([TBlock(width) for _ in range(depth)])
        self.ln = nn.LayerNorm(width)
        self.head = nn.Linear(width, N_OUT)

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.K, self.width, device=device),
                torch.zeros(batch, self.K, device=device))           # validity mask (1 = filled)

    def forward(self, x, state):
        mem, valid = state
        e = self.enc(x)[:, None]                                     # B,1,d
        seq = torch.cat([mem, e], 1) + self.age                      # oldest .. newest(current)
        pad = torch.cat([valid, torch.ones_like(valid[:, :1])], 1) < 0.5
        q = seq[:, -1:]
        for blk in self.blocks:
            q = blk(seq, key_padding_mask=pad, query=q)
        out = self.head(self.ln(q[:, 0]))
        new_mem = torch.cat([mem[:, 1:], e], 1)
        new_valid = torch.cat([valid[:, 1:], torch.ones_like(valid[:, :1])], 1)
        return out, (new_mem, new_valid)


class LSTMNet(Model):
    """As GRUNet, with an LSTM cell (separate cell state)."""
    stateful = True

    def __init__(self, width=64):
        super().__init__()
        self.enc = nn.Sequential(nn.Flatten(), nn.Linear(OBS_DIM, width), nn.GELU())
        self.cell = nn.LSTMCell(width, width)
        self.head = nn.Sequential(nn.Linear(2 * width, width), nn.GELU(), nn.Linear(width, N_OUT))
        self.width = width

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.width, device=device), torch.zeros(batch, self.width, device=device))

    def forward(self, x, state):
        e = self.enc(x)
        h, c = self.cell(e, state)
        return self.head(torch.cat([e, h], -1)), (h, c)


class ViTMem(Model):
    """Transformer over space and time: every frame is encoded by attention over its 16 patches (as ViT, 2
    blocks), then the current frame attends over the embeddings of the last K frames (as AttnMem, 2 blocks)."""
    stateful = True

    def __init__(self, width=48, K=16, depth=2):
        super().__init__()
        self.K, self.width = K, width
        self.embed = nn.Linear(3 * 16, width)
        self.pos = nn.Parameter(torch.randn(1, 17, width) * 0.02)
        self.cls = nn.Parameter(torch.zeros(1, 1, width))
        self.space = nn.ModuleList([TBlock(width) for _ in range(depth)])
        self.age = nn.Parameter(torch.randn(1, K + 1, width) * 0.02)
        self.time = nn.ModuleList([TBlock(width) for _ in range(depth)])
        self.ln = nn.LayerNorm(width)
        self.head = nn.Linear(width, N_OUT)

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.K, self.width, device=device), torch.zeros(batch, self.K, device=device))

    def forward(self, x, state):
        mem, valid = state
        B = x.shape[0]
        p = x.unfold(2, 4, 4).unfold(3, 4, 4).permute(0, 2, 3, 1, 4, 5).reshape(B, 16, 48)
        h = torch.cat([self.cls.expand(B, -1, -1), self.embed(p)], 1) + self.pos
        for blk in self.space:
            h = blk(h)
        e = h[:, :1]                                                 # B,1,d: the frame's embedding
        seq = torch.cat([mem, e], 1) + self.age
        pad = torch.cat([valid, torch.ones_like(valid[:, :1])], 1) < 0.5
        q = seq[:, -1:]
        for blk in self.time:
            q = blk(seq, key_padding_mask=pad, query=q)
        new_mem = torch.cat([mem[:, 1:], e], 1)
        new_valid = torch.cat([valid[:, 1:], torch.ones_like(valid[:, :1])], 1)
        return self.head(self.ln(q[:, 0])), (new_mem, new_valid)


class Reservoir(Model):
    """Echo-state network: a FIXED random recurrent net (width units, never trained), only the linear read-out
    learns. h <- (1 - leak) h + leak tanh(W_in x + W h); W sparse (10 inputs per unit), spectral radius 0.9.
    The fixed weights are buffers, so the parameter count is the read-out alone (about 100k = 1500 units;
    the reservoir itself holds width x 10 + width x 768 fixed random numbers)."""
    stateful = True

    def __init__(self, width=1500, leak=0.5, radius=0.9, fan=10):
        super().__init__()
        g = torch.Generator().manual_seed(1234)
        w = torch.zeros(width, width)
        idx = torch.stack([torch.randperm(width, generator=g)[:fan] for _ in range(width)])
        w.scatter_(1, idx, torch.randn(width, fan, generator=g))
        v = torch.ones(width)
        for _ in range(50):                                          # spectral radius by power iteration
            v = w @ v
            n = v.norm()
            v = v / n
        self.register_buffer("w", (w * radius / n).t().contiguous())
        self.register_buffer("w_in", torch.randn(OBS_DIM, width, generator=g) * (2.0 / OBS_DIM ** 0.5))
        self.register_buffer("b", torch.randn(width, generator=g) * 0.5)
        self.head = nn.Linear(width, N_OUT)
        self.width, self.leak = width, leak

    def init_state(self, batch, device="cpu"):
        return (torch.zeros(batch, self.width, device=device),)

    def forward(self, x, state):
        with torch.no_grad():
            h = state[0]
            h = (1 - self.leak) * h + self.leak * torch.tanh(x.flatten(1) @ self.w_in + h @ self.w + self.b)
        return self.head(h), (h,)
