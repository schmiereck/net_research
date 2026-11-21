Diagnosis of seed 9 of layer_s with `freeze:pcell` (LOGBUCH 2026-11-21). DIR = a folder for the stage-1 nets.

    .venv/Scripts/python.exe scripts/route_seed9/stage1.py DIR 9 8 ...         # keep_shift:3000 as in curriculum.job -> DIR/s<seed>.pt
    .venv/Scripts/python.exe scripts/route_seed9/stats.py DIR 0 1 ... 9         # size of cell states / pcell command / top tap
    .venv/Scripts/python.exe scripts/route_seed9/stage2.py DIR 9 pcell 9000     # stage 2 with gate, command, gradients every 250
    .venv/Scripts/python.exe scripts/route_seed9/swap.py DIR 9 pcell 6000 8     # frozen net of seed 9, new module + batches of roll 8
    .venv/Scripts/python.exe scripts/route_seed9/probe.py DIR 9 8               # stored word from top / all cells / last row (ridge)
    .venv/Scripts/python.exe scripts/route_seed9/probe_var.py DIR 0 ... 9       # word R^2 per cell, from the initial 16-value map

Logs in results/route_seed9/. Stage 1 here is not bit-identical to the worker (small differences).
