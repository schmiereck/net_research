"""Watch trained models side by side.

    python -m netresearch.gui

Pick a task and a model group; every model gets its own copy of the same scenario (same seed) and runs live.
Games: each panel shows the frame, the chosen action, the running episode return and the mean of finished
episodes. Expert and random policies are shown as reference panels.
Supervised tasks: all models see the same test sample; the panels show input, prediction and running accuracy.
Models are loaded from results/checkpoints (written by netresearch.bench / train.run).
"""
import math
import tkinter as tk
from tkinter import ttk

import numpy as np
import torch
from PIL import Image, ImageTk

from .models import MODEL_ORDER
from .spec import ACTION_NAMES
from .tasks import TASKS, make_task
from .train import load_checkpoint, policy_actions, reset_state

GROUPS = {
    "Alle": MODEL_ORDER,
    "Baselines": ["mlp", "cnn", "cvnn", "vit", "gru", "attnmem"],
    "Bus": [m for m in MODEL_ORDER if "bus" in m],
    "Gitter": ["layer_s", "layer_i", "hier_s", "hier_i"],
    "Gedächtnis": ["gru", "attnmem", "layer_s", "layer_i", "hier_s", "hier_i"],
}
SCALE = 8
BG, FG, MUTED, GOOD, BAD = "#1e1e1e", "#e8e8e8", "#9a9a9a", "#7fd18b", "#ef7b7b"


def frame_to_photo(obs):
    arr = (np.transpose(obs, (1, 2, 0)) * 255).astype(np.uint8)
    img = Image.fromarray(arr).resize((16 * SCALE, 16 * SCALE), Image.NEAREST)
    return ImageTk.PhotoImage(img)


def label_text(task_name, idx):
    if task_name == "shapes":
        from .tasks.images import SHAPE_NAMES
        return SHAPE_NAMES[idx]
    if task_name == "charnext":
        from .tasks.text import VOCAB
        c = VOCAB[idx]
        return repr(c)
    return str(idx)


class Panel:
    def __init__(self, parent, name, model):
        self.name, self.model = name, model
        self.frame = tk.Frame(parent, bg=BG, highlightthickness=1, highlightbackground="#3a3a3a")
        sub = "" if model is None else f"  ({model.score:.2f})" if hasattr(model, "score") else ""
        tk.Label(self.frame, text=name + sub, bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=4)
        self.canvas = tk.Label(self.frame, bg="black")
        self.canvas.pack(padx=4)
        self.info = tk.Label(self.frame, text="", bg=BG, fg=MUTED, font=("Consolas", 9), justify="left",
                             anchor="w", width=20)
        self.info.pack(anchor="w", padx=4, pady=(2, 4))
        self.photo = None

    def show(self, obs, text, color=MUTED):
        self.photo = frame_to_photo(obs)
        self.canvas.configure(image=self.photo)
        self.info.configure(text=text, fg=color)


class GamePanel(Panel):
    def __init__(self, parent, name, model, task, seed, policy="model"):
        super().__init__(parent, name, model)
        self.task, self.policy = task, policy
        self.env = task.make_env(1, seed)
        self.rng = np.random.default_rng(seed)
        self.state = model.init_state(1) if model is not None else ()
        self.ret, self.returns, self.action = 0.0, [], 0
        self.show(self.env.obs()[0], "")

    @torch.no_grad()
    def step(self):
        valid = self.task.spec.valid_actions
        o = self.env.obs()
        if self.policy == "expert":
            a = self.env.expert()
        elif self.policy == "random":
            a = self.rng.choice(valid, size=1)
        else:
            logits, self.state = self.model(torch.from_numpy(o), self.state)
            a = policy_actions(logits, valid)
        self.action = int(a[0])
        r, done, finished = self.env.step(a)
        self.ret += float(r[0])
        if done[0]:
            self.returns.append(self.ret)
            self.ret = 0.0
            if self.model is not None and self.model.stateful:
                self.state = reset_state(self.state, torch.zeros(1))
        mean = f"{np.mean(self.returns):6.1f} ({len(self.returns)})" if self.returns else "   –"
        self.show(self.env.obs()[0], f"Aktion : {ACTION_NAMES[self.action]}\nReturn : {self.ret:6.1f}\n"
                                      f"Ø Ep.  : {mean}")


class SupervisedPanel(Panel):
    def __init__(self, parent, name, model, task):
        super().__init__(parent, name, model)
        self.task = task
        self.state = model.init_state(1) if model is not None else ()
        self.correct = self.total = 0

    def reset_seq(self):
        if self.model is not None and self.model.stateful:
            self.state = self.model.init_state(1)

    @torch.no_grad()
    def step(self, obs, target, counted):
        spec = self.task.spec
        logits, self.state = self.model(torch.from_numpy(obs[None]), self.state)
        lg = logits[0, :spec.n_out]
        if spec.head == "class":
            pred, tgt = int(lg.argmax()), int(target)
            ok = pred == tgt
            ptxt, ttxt = label_text(spec.name, pred), label_text(spec.name, tgt)
        else:
            pb = (lg > 0).int().numpy()
            ok = bool((pb == target).all())
            ptxt = "".join("#" if b else "." for b in pb)
            ttxt = "".join("#" if b else "." for b in target)
        if counted:
            self.correct += ok
            self.total += 1
        acc = f"{self.correct / self.total:5.1%} ({self.total})" if self.total else "   –"
        mark = "" if counted else "  (Warm-up)"
        self.show(obs, f"Ziel   : {ttxt}{mark}\nVorhers: {ptxt}\nGenauig: {acc}",
                  (GOOD if ok else BAD) if counted else MUTED)


class App:
    def __init__(self, root):
        self.root = root
        root.title("NetResearch – Modelle beobachten")
        root.configure(bg=BG)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", padx=8, pady=6)
        self.task_var = tk.StringVar(value="paddle")
        self.group_var = tk.StringVar(value="Alle")
        self.seed_var = tk.IntVar(value=0)
        self.speed_var = tk.IntVar(value=10)
        self.running = False

        def lab(t):
            tk.Label(bar, text=t, bg=BG, fg=FG).pack(side="left", padx=(8, 2))
        lab("Task")
        ttk.Combobox(bar, textvariable=self.task_var, values=list(TASKS), width=12, state="readonly").pack(side="left")
        lab("Gruppe")
        ttk.Combobox(bar, textvariable=self.group_var, values=list(GROUPS), width=11, state="readonly").pack(side="left")
        lab("Seed")
        tk.Spinbox(bar, from_=0, to=9999, textvariable=self.seed_var, width=6).pack(side="left")
        ttk.Button(bar, text="Laden", command=self.load).pack(side="left", padx=8)
        self.run_btn = ttk.Button(bar, text="▶ Start", command=self.toggle)
        self.run_btn.pack(side="left")
        ttk.Button(bar, text="Schritt", command=self.step).pack(side="left", padx=4)
        lab("Schritte/s")
        tk.Scale(bar, from_=1, to=60, orient="horizontal", variable=self.speed_var, bg=BG, fg=FG,
                 highlightthickness=0, length=140).pack(side="left")
        self.status = tk.Label(root, text="", bg=BG, fg=MUTED, anchor="w")
        self.status.pack(fill="x", padx=12)
        self.grid = tk.Frame(root, bg=BG)
        self.grid.pack(fill="both", expand=True, padx=8, pady=8)
        self.panels = []
        self.load()

    def load(self):
        self.running = False
        self.run_btn.configure(text="▶ Start")
        for w in self.grid.winfo_children():
            w.destroy()
        task = make_task(self.task_var.get())
        self.task, seed = task, int(self.seed_var.get())
        self.rng = np.random.default_rng(seed)
        self.panels, missing = [], []
        is_game = task.spec.kind == "control"
        if is_game:
            self.panels.append(GamePanel(self.grid, "Experte", None, task, seed, "expert"))
            self.panels.append(GamePanel(self.grid, "Zufall", None, task, seed, "random"))
        for m in GROUPS[self.group_var.get()]:
            model = load_checkpoint(m, task.spec.name, 0)
            if model is None:
                missing.append(m)
                continue
            self.panels.append(GamePanel(self.grid, m, model, task, seed) if is_game
                               else SupervisedPanel(self.grid, m, model, task))
        cols = max(1, math.ceil(math.sqrt(len(self.panels) * 1.8)))
        for i, p in enumerate(self.panels):
            p.frame.grid(row=i // cols, column=i % cols, padx=4, pady=4, sticky="n")
        self.seq, self.t = None, 0
        msg = f"{task.spec.name}: {task.spec.description}"
        if missing:
            msg += f"   |  ohne Checkpoint: {', '.join(missing)}"
        self.status.configure(text=msg)
        if not is_game:
            self.step()

    def step(self):
        if self.task.spec.kind == "control":
            for p in self.panels:
                p.step()
            return
        spec = self.task.spec
        if self.seq is None or self.t >= spec.seq_len:
            self.seq = self.task.sample(1, self.rng, split="test")
            self.t = 0
            for p in self.panels:
                p.reset_seq()
        obs = self.seq["obs"][self.t, 0]
        target = self.seq["target"][self.t, 0]
        counted = self.seq["mask"][self.t, 0] > 0
        for p in self.panels:
            p.step(obs, target, counted)
        self.t += 1

    def toggle(self):
        self.running = not self.running
        self.run_btn.configure(text="⏸ Pause" if self.running else "▶ Start")
        if self.running:
            self.loop()

    def loop(self):
        if not self.running:
            return
        self.step()
        self.root.after(max(1, int(1000 / self.speed_var.get())), self.loop)


def main():
    torch.set_num_threads(2)
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
