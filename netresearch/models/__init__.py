"""Model registry with automatic parameter matching (width search towards a target parameter count)."""
from functools import partial

import torch

from .basic import CNN, CVNN, MLP, AttnMem, GRUNet, ViT
from .bus import BusNet
from .grid import HierGrid, LayerGrid
from .scratchpad import BusScratch, MLPScratch


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

# "_iw": individual modules with the module width of the shared "_s" partner (equal width, ~P x params)
WIDTH_FROM = {}
for _base in ("bus_add", "bus_mul", "bus_gate", "bus_film", "layer", "hier"):
    MODELS[f"{_base}_iw"] = MODELS[f"{_base}_i"]
    WIDTH_FROM[f"{_base}_iw"] = f"{_base}_s"

# Scratchpad memory (explicit per-module memory, models/scratchpad.py): "_sp<n>" = n values per module,
# "_spg" = additionally 4 values per position published to all positions (global scratchpad)
SCRATCH_ORDER = []
for _n in (4, 16, 64):
    MODELS[f"mlp_sp{_n}"] = (partial(MLPScratch, n_mem=_n), (8, 1024), 1)
    MODELS[f"bus_add_s_sp{_n}"] = (partial(BusScratch, shared=True, n_mem=_n), (8, 512), 1)
    SCRATCH_ORDER += [f"mlp_sp{_n}", f"bus_add_s_sp{_n}"]
MODELS["bus_add_s_spg"] = (partial(BusScratch, shared=True, n_mem=16, n_global=4), (8, 512), 1)
MODELS["bus_add_i_sp16"] = (partial(BusScratch, shared=False, n_mem=16), (8, 512), 1)
SCRATCH_ORDER += ["bus_add_s_spg", "bus_add_i_sp16"]
# grids: "_sp<n>" = n values per cell, "g<k>" = one global scratchpad of k values that all cells read and
# write together (averaged proposals), so its input size does not grow with the grid
for _grid, _cls in (("layer", LayerGrid), ("hier", HierGrid)):
    for _sh, _n, _k in (("s", 4, 0), ("s", 16, 0), ("s", 4, 16), ("i", 4, 0)):
        _name = f"{_grid}_{_sh}_sp{_n}" + (f"g{_k}" if _k else "")
        MODELS[_name] = (partial(_cls, shared=_sh == "s", n_mem=_n, n_global=_k), (4, 256), 1)
        SCRATCH_ORDER.append(_name)
    # reading other modules' scratchpads: "n" = 8 nearest neighbours, "a" = by learned address (4 queries)
    for _sh in ("s", "i"):
        for _read, _suf in (("neigh", "n"), ("addr", "a")):
            _name = f"{_grid}_{_sh}_sp4{_suf}"
            MODELS[_name] = (partial(_cls, shared=_sh == "s", n_mem=4, read=_read), (4, 256), 1)
            SCRATCH_ORDER.append(_name)
    # key/value scratchpad (content addressing): "_kv" = 16 rows x 4 values per cell, 1 write/read head;
    # "_kv4" = 4 heads (4 rows written and read per step)
    for _sh in ("s", "i"):
        for _h, _suf in ((1, "kv"), (4, "kv4")):
            _name = f"{_grid}_{_sh}_{_suf}"
            MODELS[_name] = (partial(_cls, shared=_sh == "s", n_mem=4, slots=16, heads=_h), (4, 256), 1)
            SCRATCH_ORDER.append(_name)
    # allocating key/value scratchpad: write to the least-used row, read by key similarity ("_am", "_am4")
    for _sh in ("s", "i"):
        for _h, _suf in ((1, "am"), (4, "am4")):
            _name = f"{_grid}_{_sh}_{_suf}"
            MODELS[_name] = (partial(_cls, shared=_sh == "s", n_mem=4, slots=16, heads=_h, alloc=True),
                             (4, 256), 1)
            SCRATCH_ORDER.append(_name)

MODEL_ORDER = ["mlp", "cnn", "cvnn", "vit", "gru", "attnmem",
               "bus_add_s", "bus_add_i", "bus_mul_s", "bus_mul_i", "bus_gate_s", "bus_gate_i",
               "bus_film_s", "bus_film_i", "subbus_i", "layer_s", "layer_i", "hier_s", "hier_i",
               "bus_add_iw", "bus_mul_iw", "bus_gate_iw", "bus_film_iw", "layer_iw", "hier_iw"]
# shared model -> its individual counterpart (used to split the shared gradient into per-position parts)
SHARED_TO_INDIVIDUAL = {f"{b}_s": f"{b}_i" for b in ("bus_add", "bus_mul", "bus_gate", "bus_film", "layer", "hier")}


def count_params(model):
    """Real-valued parameter count (complex parameters count twice)."""
    return sum(p.numel() * (2 if p.is_complex() else 1) for p in model.parameters())


def matched_width(name, target_params=100_000):
    """Width whose parameter count is closest to target_params (binary search)."""
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
    return w * mult


def build_model(name, target_params=100_000, seed=0):
    width = matched_width(WIDTH_FROM.get(name, name), target_params)
    torch.manual_seed(seed)
    model = MODELS[name][0](width=width)
    model.width_used = width
    return model
