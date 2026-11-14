"""Offset between the body origin (the point whose cell the gaze tasks ask for) and the visible centre of each
shape. Runs in the ROBOT project: cd rdf_thalamus_sml/src; PYTHONPATH=. python <this file>"""
import numpy as np, mujoco
from pc_cvnn.export_netresearch import Scene, SHAPES, K
sc = Scene(); m = sc.sim.m
mujoco.mj_forward(m, sc.sim.d)
p0 = sc.sim.obj_pos("obj_red")
px_per_m = np.linalg.norm(sc.project(p0 + np.array([0.01, 0, 0])) - sc.project(p0)) / 0.01
print(f"scale at the cube: {px_per_m:.0f} px per m; one cell = {K} px = {1000 * K / px_per_m:.1f} mm")
for o in SHAPES:
    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, o)
    gs = [g for g in range(m.ngeom) if m.geom_bodyid[g] == bid]
    lo = np.min([m.geom_pos[g][:2] - m.geom_size[g][:2] for g in gs], 0)
    hi = np.max([m.geom_pos[g][:2] + m.geom_size[g][:2] for g in gs], 0)
    area = np.array([m.geom_size[g][0] * m.geom_size[g][1] for g in gs])
    cen = (np.array([m.geom_pos[g][:2] for g in gs]) * area[:, None]).sum(0) / area.sum()
    box = (lo + hi) / 2
    print(f"{o:8s} geoms {len(gs)}  size {1000 * (hi - lo)} mm  origin -> box centre {np.linalg.norm(box) * px_per_m:.2f} px"
          f"  origin -> area centroid {np.linalg.norm(cen) * px_per_m:.2f} px  (types {set(int(m.geom_type[g]) for g in gs)})")
