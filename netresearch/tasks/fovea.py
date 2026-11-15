"""The robot's fovea, re-sampled here: what the eye sees after a gaze step.

The robot project (rdf_thalamus_sml, pc_act18.hex_sample / export_netresearch.fine_sample) samples the overview
camera image (240 x 240) on a 16 x 16 hex lattice around the gaze point: 4 px per cell, odd rows shifted by half
a cell, full resolution up to 5 cells from the centre and coarser, wider cells beyond. The exported tasks hold one
such view per scene. To CLOSE THE LOOP (the net's step moves the gaze, the next image comes from the new gaze) the
same sampling is needed here; the export stores the camera image for that ("--images": img 240 x 240, big
480 x 480). This module is a copy of that geometry (image in, cells out - nothing else of the robot); it
reproduces the exported views bit for bit, including what happens where cells fall off the image
(tests/test_smoke.py checks that when the data is there).

A step (dx, dy) in cells, -8..7, means "the wanted thing lies in cell (row 8 + dy, column 8 + dx)"; shift()
moves the gaze so that the sampling point of that cell lands on the sampling point of the centre cell (8, 8),
after which the right answer is (0, 0).
"""
import numpy as np

F, K, HEX_DY, D0, B, RES = 16, 4, 0.8660254, 5.0, 1.0, 240
CTR = (F - 1) / 2.0


def warp(t):
    """Cell offset from the centre -> offset in units of K: identity up to D0 cells, quadratic beyond."""
    a = np.abs(t)
    return np.sign(t) * (a + B * np.maximum(0.0, a - D0) ** 2)


def warp_spacing(t):
    return 1.0 + 2.0 * B * np.maximum(0.0, np.abs(t) - D0)


def _lattice(n):
    """Sampling points of the (n * F)^2 cells relative to the gaze, in units of K (x, y), and their pooling
    half-width in pixels of an image with n-fold... see _points()."""
    N = n * F
    ctr = (N - 1) / 2.0
    r = np.arange(N)
    ir = (r - ctr) / n                                                  # [N]
    ic = (np.arange(N)[None, :] + 0.5 * (r[:, None] & 1) - ctr) / n     # [N, N]
    return ir, ic


def cell_px(gaze):
    """Pixel positions [F, F, 2] (x, y) of the sampling points of the 16 x 16 fovea at this gaze."""
    ir, ic = _lattice(1)
    return np.stack([gaze[0] + warp(ic) * K, np.broadcast_to((gaze[1] + warp(ir) * K * HEX_DY)[:, None], ic.shape)], -1)


def centre_px(gaze):
    """Where the centre cell (8, 8) looks: the point a perfect step puts the wanted thing on."""
    return cell_px(gaze)[F // 2, F // 2]


def nearest_cell(gaze, px):
    """Step (dx, dy) to the cell whose sampling point is nearest to the pixel, and the distance in pixels."""
    d = np.linalg.norm(cell_px(gaze) - np.asarray(px), axis=-1)
    r, c = np.unravel_index(int(d.argmin()), d.shape)
    return c - F // 2, r - F // 2, float(d[r, c])


def shift(gaze, dx, dy):
    """Gaze after the step (dx, dy): the chosen cell's sampling point moves onto that of the centre cell."""
    cp = cell_px(np.zeros(2))
    return np.asarray(gaze, float) + cp[F // 2 + int(dy), F // 2 + int(dx)] - cp[F // 2, F // 2]


def integral(img):
    """Summed-area table [H + 1, W + 1, 3] of a camera image [H, W, 3] uint8."""
    s = np.zeros((img.shape[0] + 1, img.shape[1] + 1, 3), np.int64)
    s[1:, 1:] = img.astype(np.int64).cumsum(0).cumsum(1)
    return s


def _span(lo, half, n):
    """Start and end of the slice [max(0, lo):lo + 2 * half + 1] of an axis of length n, exactly as Python
    cuts it (an end below zero counts from the far side - the robot's sampler does that, so the views in the
    training data do too)."""
    s = np.minimum(np.maximum(0, lo), n)
    e = lo + 2 * half + 1
    e = np.where(e < 0, np.maximum(0, n + e), np.minimum(e, n))
    return s, np.maximum(e, s)


def _pool(sat, cx, cy, half):
    """Mean colour of the blocks of half-width `half` around (cx, cy) -> uint8 [3, rows, cols]."""
    h, w = sat.shape[0] - 1, sat.shape[1] - 1
    x0, x1 = _span(np.round(cx - half).astype(np.int64), half, w)
    y0, y1 = _span(np.round(cy - half).astype(np.int64), half, h)
    tot = sat[y1, x1] - sat[y0, x1] - sat[y1, x0] + sat[y0, x0]
    cnt = ((x1 - x0) * (y1 - y0))[..., None]
    mean = np.where(cnt > 0, tot / np.maximum(cnt, 1), 0.0) / 255.0
    return np.round(mean * 255).astype(np.uint8).transpose(2, 0, 1)


def sample(sat, gaze):
    """The 16 x 16 fovea at `gaze` (pixels of the 240 x 240 image). sat = integral(img). -> uint8 [3, 16, 16]"""
    ir, ic = _lattice(1)
    cy = gaze[1] + warp(ir) * K * HEX_DY
    sy = warp_spacing(ir) * K * HEX_DY
    half = np.maximum(1, np.round(0.25 * (warp_spacing(ic) * K + sy[:, None])).astype(np.int64))
    return _pool(sat, gaze[0] + warp(ic) * K, np.broadcast_to(cy[:, None], ic.shape), half)


def sample_fine(sat, gaze, n=2):
    """(n * 16)^2 cells over the SAME field of view, from the image of double resolution. sat = integral(big);
    gaze in pixels of the 240 x 240 image. -> uint8 [3, n * 16, n * 16]"""
    g, k = 2.0 * np.asarray(gaze, float), 2 * K
    ir, ic = _lattice(n)
    cy = g[1] + warp(ir) * k * HEX_DY
    sy = warp_spacing(ir) * k * HEX_DY / n
    half = np.maximum(1, np.round(0.25 * (warp_spacing(ic) * k / n + sy[:, None])).astype(np.int64))
    return _pool(sat, g[0] + warp(ic) * k, np.broadcast_to(cy[:, None], ic.shape), half)
