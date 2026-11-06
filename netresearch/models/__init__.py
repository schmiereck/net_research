"""Model registry with automatic parameter matching (width search towards a target parameter count)."""
from functools import partial

import torch

from .basic import CNN, CVNN, MLP, AttnMem, GRUNet, ViT
from .bus import BusNet
from .grid import HierGrid, LayerGrid


def _bus(mode, shared, width, sub=False):
    return BusNet(width=width, mode=mode, shared=shared, sub=sub)


# name -> (constructor(width), (min_width, max_width), width multiple)
MODELS = {
    "mlp": (MLP, (8, 1024), 1),
    "cnn": (CNN, (4, 256), 2),
    "cvnn": (CVNN, (4, 512), 1),
    "vit": (ViT, (8, 256), 4),
    "gru": (GRUNet, (8, 512), 1),
    "attnmem": (AttnMem, (8, 256), 4),
    "subbus_i": (partial(_bus, "add", False, sub=True), (8, 512), 2),
    "layer_s": (partial(LayerGrid, shared=True), (4, 256), 1),
    "layer_i": (partial(LayerGrid, shared=False), (4, 256), 1),
    "hier_s": (partial(HierGrid, shared=True), (4, 256), 1),
    "hier_i": (partial(HierGrid, shared=False), (4, 256), 1),
}
for _mode in ("add", "mul", "gate", "film"):
    MODELS[f"bus_{_mode}_s"] = (partial(_bus, _mode, True), (8, 512), 1)
    MODELS[f"bus_{_mode}_i"] = (partial(_bus, _mode, False), (8, 512), 1)

MODEL_ORDER = ["mlp", "cnn", "cvnn", "vit", "gru", "attnmem",
               "bus_add_s", "bus_add_i", "bus_mul_s", "bus_mul_i", "bus_gate_s", "bus_gate_i",
               "bus_film_s", "bus_film_i", "subbus_i", "layer_s", "layer_i", "hier_s", "hier_i"]


def count_params(model):
    """Real-valued parameter count (complex parameters count twice)."""
    return sum(p.numel() * (2 if p.is_complex() else 1) for p in model.parameters())


def build_model(name, target_params=100_000, seed=0):
    ctor, (lo, hi), mult = MODELS[name]

    def n(w):
        return count_params(ctor(width=w * mult))

    lo, hi = max(1, lo // mult), hi // mult
    while hi - lo > 1:                     # binary search: params grow monotonically with width
        mid = (lo + hi) // 2
        if n(mid) <= target_params:
            lo = mid
        else:
            hi = mid
    w = lo if abs(n(lo) - target_params) <= abs(n(hi) - target_params) else hi
    torch.manual_seed(seed)
    model = ctor(width=w * mult)
    model.width_used = w * mult
    return model
