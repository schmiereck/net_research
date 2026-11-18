"""Policy server: stored NetResearch nets answer gaze steps for a program in another Python (e.g. the MuJoCo
simulator of the robot project, which has no torch). Used by rdf_thalamus_sml/src/pc_cvnn/netresearch_live_loop.py.

    python scripts/policy_server.py --port 6071

Protocol (multiprocessing.connection, bytes only, so the two sides need not share numpy versions): every message
is a JSON header followed by one raw byte block per array named in the header ("arrays": [[name, dtype, shape]]).
Requests:
    {"op": "load", "task": ..., "model": ..., "ckpt": ..., "seed": ...}       -> {"ok": true}
    {"op": "cue", "arrays": [["refs", "uint8", [G, n, 3, 16, 16]]]}        G cue steps with the goal pictures
    {"op": "step", "arrays": [["views", "uint8", [n, 3, 32, 32]]]}         -> arrays [["steps", "int64", [n, 2]]]
    {"op": "quit"}
The steps follow scripts/finds_loop_eval.py exactly: cue steps with a blank image and the picture of goal k, then
every view with a blank picture and the kept state; the answer is decode_step of the step output.
"""
import argparse
import json
import sys
from multiprocessing.connection import Listener
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks.registry import TASKS  # noqa: E402
from netresearch.tasks.servo import decode_step  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402


def recv(conn):
    head = json.loads(conn.recv_bytes().decode())
    arrays = {}
    for name, dtype, shape in head.get("arrays", []):
        arrays[name] = np.frombuffer(conn.recv_bytes(), dtype=dtype).reshape(shape)
    return head, arrays


def send(conn, head, arrays=None):
    arrays = arrays or {}
    head = dict(head, arrays=[[k, str(v.dtype), list(v.shape)] for k, v in arrays.items()])
    conn.send_bytes(json.dumps(head).encode())
    for v in arrays.values():
        conn.send_bytes(np.ascontiguousarray(v).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=6071)
    a = ap.parse_args()
    torch.set_num_threads(2)
    model, task, state = None, None, None
    with Listener(("127.0.0.1", a.port), authkey=b"netresearch-live") as lst:
        print(f"policy server on port {a.port}", flush=True)
        with lst.accept() as conn:
            while True:
                head, arr = recv(conn)
                op = head["op"]
                if op == "quit":
                    send(conn, {"ok": True})
                    break
                if op == "load":
                    task = TASKS[head["task"]]()
                    model = load_checkpoint(head["model"], head.get("ckpt") or head["task"], int(head["seed"]))
                    if model is None:
                        send(conn, {"ok": False, "error": "no checkpoint"})
                        continue
                    model.eval()
                    state = None
                    send(conn, {"ok": True, "stateful": bool(model.stateful)})
                elif op == "cue":
                    refs = torch.tensor(arr["refs"].astype(np.float32) / 255.0)          # [G, n, 3, 16, 16]
                    n = refs.shape[1]
                    blank = torch.zeros(1, n, 3, 32, 32)
                    st = None
                    with torch.no_grad():
                        for k in range(refs.shape[0]):
                            _, st = run_sequence(model, blank, state=st if model.stateful else None, ref=refs[k:k + 1])
                    state = st if model.stateful else None
                    send(conn, {"ok": True})
                elif op == "step":
                    x = torch.tensor(arr["views"].astype(np.float32) / 255.0)[None]       # [1, n, 3, 32, 32]
                    with torch.no_grad():
                        lg, st = run_sequence(model, x, state=state, ref=torch.zeros(1, x.shape[1], 3, 16, 16))
                    state = st if model.stateful else None
                    steps = np.asarray(decode_step(lg[0][:, task.spec.out_slice].numpy(), task.spec), np.int64)
                    send(conn, {"ok": True}, {"steps": steps})
                else:
                    send(conn, {"ok": False, "error": f"unknown op {op}"})


if __name__ == "__main__":
    sys.exit(main())
