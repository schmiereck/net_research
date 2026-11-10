"""Watch trained models side by side.

    python -m netresearch.gui [--task grid_follow]

Pick a task and a model group; every model gets its own copy of the same scenario (same seed) and runs live.
Games: each panel shows the frame, the chosen action, the running episode return and the outcomes of the
finished episodes. Expert and random policies are shown as reference panels.
Grid worlds (grid*, push*): the path of the current episode is drawn into the view, the shortest-path distance
to the goal is shown, and episodes are counted by outcome (goal / pit / time out). The scrolling worlds
(grid_follow, grid_scroll: 32x32, the model sees a 16x16 window) also get a map of the whole world: the area
the model has seen so far is bright, the rest dark, the current window is outlined.
"Bewerten" plays 50 fresh episodes per panel without drawing (the same worlds for every panel) and shows the
outcome rates: a quick look at how a model fails, not only how often.
Supervised tasks: all models see the same test sample; the panels show input, prediction and running accuracy.
Models are loaded from results/checkpoints (written by netresearch.bench / train.run; worker checkpoints with
jobs fetch --checkpoints). "Mit Checkpoint" lists every model trained on the task. With "Multi-Task" the models
trained on all tasks at once (bench --multitask) are shown instead of the single-task models.
"""
import argparse
import copy
import math
import tkinter as tk
from tkinter import ttk

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageTk

from .models import MODEL_ORDER, MODELS
from .spec import ACTION_NAMES, BLUE, GREEN, MAGENTA, RED, YELLOW
from .tasks import TASKS, make_task
from .train import checkpoint_path, load_checkpoint, policy_actions, reset_state

AVAILABLE = "Mit Checkpoint"
GROUPS = {
    AVAILABLE: None,                                     # every model with a checkpoint for the task
    "Alle": MODEL_ORDER,
    "Baselines": ["mlp", "cnn", "cvnn", "vit", "gru", "attnmem"],
    "Bus": [m for m in MODEL_ORDER if "bus" in m],
    "Gitter": ["layer_s", "layer_i", "layer_iw", "hier_s", "hier_i", "hier_iw"],
    "Geteilt vs. individuell": [m for m in MODEL_ORDER if m.endswith(("_s", "_i", "_iw")) and m != "subbus_i"],
    "Gedächtnis": ["gru", "attnmem", "layer_s", "layer_i", "hier_s", "hier_i"],
    "Notizblock / Speicher": [m for m in MODELS if m.endswith(("_sp4", "_kv", "_am", "_am4", "_ar", "_ar4"))],
}
SCALE = 10
MAP_PX = 4                                               # pixels per world cell on the map
BG, FG, MUTED, GOOD, BAD, TRAIL = "#1e1e1e", "#e8e8e8", "#9a9a9a", "#7fd18b", "#ef7b7b", "#ffa040"
N_EVAL = 50


def frame_image(obs, scale=SCALE):
    arr = (np.transpose(obs, (1, 2, 0)) * 255).astype(np.uint8)
    return Image.fromarray(arr).resize((16 * scale, 16 * scale), Image.NEAREST)


def label_text(task_name, idx):
    if task_name == "shapes":
        from .tasks.images import SHAPE_NAMES
        return SHAPE_NAMES[idx]
    if task_name == "charnext":
        from .tasks.text import VOCAB
        c = VOCAB[idx]
        return repr(c)
    return str(idx)


def models_for(task_name, group, multi):
    """(models with a checkpoint, models of the group without one)."""
    ck = "multi" if multi else task_name
    names = list(MODELS) if GROUPS[group] is None else GROUPS[group]
    have = [m for m in names if checkpoint_path(m, ck, 0).exists()]
    if GROUPS[group] is None:                            # also variants by name suffix (+cmd, @size)
        d = checkpoint_path("x", ck, 0).parent
        have += sorted(p.name[:-len("_s0.pt")] for p in d.glob("*_s0.pt")
                       if ("+" in p.name or "@" in p.name))
    missing = [] if GROUPS[group] is None else [m for m in names if m not in have]
    return have, missing


# ---------------------------------------------------------------------------------- grid-world helpers
def is_grid(game):
    from .tasks.games.gridworld import GridWorld, Push
    return isinstance(game, (GridWorld, Push))


def player_pos(game):
    return game.x, game.y


def goal_dist(game):
    """Shortest-path distance to the goal (grid worlds) or remaining solution length (push), None if unknown."""
    if hasattr(game, "to_goal"):
        d = int(game.to_goal[game.y, game.x])
        return d if d >= 0 else None
    if hasattr(game, "dist") and hasattr(game, "bx"):
        d = int(game.dist[game.y * 16 + game.x, game.by * 16 + game.bx])
        return d if d >= 0 else None
    return None


def draw_trail(img, trail, origin, scale, color=TRAIL):
    """Polyline through the cell centres of trail (world coordinates), shifted by the view origin."""
    if len(trail) < 2:
        return
    ox, oy = origin
    pts = [((x - ox + 0.5) * scale, (y - oy + 0.5) * scale) for x, y in trail]
    ImageDraw.Draw(img).line(pts, fill=color, width=max(2, scale // 4))


def world_map(game, trail):
    """Whole world of a scrolling grid game: unseen cells dark, the current 16x16 window outlined."""
    S = game.size
    rgb = np.zeros((S, S, 3), np.float32)
    rgb[game.cell == 1] = BLUE
    rgb[game.cell == 2] = RED
    gx, gy = game.goal
    rgb[gy, gx] = GREEN
    rgb[game.y, game.x] = YELLOW
    if hasattr(game, "seen"):
        rgb[~game.seen] *= 0.3
        rgb[~game.seen] += 0.08
    img = Image.fromarray((rgb * 255).astype(np.uint8)).resize((S * MAP_PX, S * MAP_PX), Image.NEAREST)
    draw_trail(img, trail, (0, 0), MAP_PX)
    ox, oy = game.view_origin()
    ImageDraw.Draw(img).rectangle([ox * MAP_PX, oy * MAP_PX, (ox + 16) * MAP_PX - 1, (oy + 16) * MAP_PX - 1],
                                  outline="#ffffff")
    return img


@torch.no_grad()
def outcome_stats(model, task, games, seed, policy="model"):
    """One episode in each of the given fresh worlds (played on copies, no auto-reset): fractions goal / pit /
    time out, mean length of the successes."""
    games = copy.deepcopy(games)
    n = len(games)
    valid = task.spec.valid_actions
    rng = np.random.default_rng(seed)
    state = model.init_state(n) if model is not None else ()
    alive, length, res = np.ones(n, bool), np.zeros(n, int), {}
    while alive.any():
        if policy == "expert":
            a = [g.expert() if alive[i] else 0 for i, g in enumerate(games)]
        elif policy == "random":
            a = rng.choice(valid, size=n)
        else:                                                # finished worlds keep their last frame
            logits, state = model(torch.from_numpy(np.stack([g.render() for g in games])), state)
            a = policy_actions(logits, valid)
        for i in np.flatnonzero(alive):
            r, d = games[i].step(int(a[i]))
            length[i] += 1
            if d or length[i] >= games[i].max_steps:
                res[i] = ("goal" if r > 0 else "pit" if r < 0 else "time", int(length[i]))
                alive[i] = False
    out = [o for o, _ in res.values()]
    succ = [ln for o, ln in res.values() if o == "goal"]
    return {k: out.count(k) / n for k in ("goal", "pit", "time")}, (np.mean(succ) if succ else None)


# --------------------------------------------------------------------------------------------- panels
class Panel:
    def __init__(self, parent, name, model):
        self.name, self.model = name, model
        self.frame = tk.Frame(parent, bg=BG, highlightthickness=1, highlightbackground="#3a3a3a")
        sub = "" if model is None else f"  ({model.score:.2f})" if hasattr(model, "score") else ""
        tk.Label(self.frame, text=name + sub, bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=4)
        pics = tk.Frame(self.frame, bg=BG)
        pics.pack(anchor="w", padx=4)
        self.canvas = tk.Label(pics, bg="black")
        self.canvas.pack(side="left")
        self.map = tk.Label(pics, bg=BG)
        self.map.pack(side="left", padx=(4, 0))
        self.info = tk.Label(self.frame, text="", bg=BG, fg=MUTED, font=("Consolas", 9), justify="left",
                             anchor="w", width=26)
        self.info.pack(anchor="w", padx=4, pady=(2, 4))
        self.photo = self.map_photo = None

    def show(self, obs, text, color=MUTED, trail=None, origin=(0, 0), map_img=None):
        img = frame_image(obs)
        if trail:
            draw_trail(img, trail, origin, SCALE)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.configure(image=self.photo)
        if map_img is not None:
            self.map_photo = ImageTk.PhotoImage(map_img)
            self.map.configure(image=self.map_photo)
        self.info.configure(text=text, fg=color)


class GamePanel(Panel):
    def __init__(self, parent, name, model, task, seed, policy="model", show_trail=None, show_map=None):
        super().__init__(parent, name, model)
        self.task, self.policy, self.seed = task, policy, seed
        self.show_trail, self.show_map = show_trail, show_map
        self.env = task.make_env(1, seed)
        self.game = self.env.games[0]
        self.grid = is_grid(self.game)
        self.rng = np.random.default_rng(seed)
        self.state = model.init_state(1) if model is not None else ()
        self.ret, self.returns, self.action, self.t = 0.0, [], 0, 0
        self.outcomes = {"goal": 0, "pit": 0, "time": 0}
        self.succ_len, self.eval_text = [], ""
        self.new_episode()
        self.render()

    def new_episode(self):
        self.trail = [player_pos(self.game)] if self.grid else []
        self.start_dist = goal_dist(self.game) if self.grid else None

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
        r, done, finished = self.env.step(a)               # auto-reset: on done the game is already new
        self.ret += float(r[0])
        self.t += 1
        if done[0]:
            self.returns.append(self.ret)
            self.outcomes["goal" if r[0] > 0 else "pit" if r[0] < 0 else "time"] += 1
            if r[0] > 0:
                self.succ_len.append(self.t)
            self.ret, self.t = 0.0, 0
            if self.model is not None and self.model.stateful:
                self.state = reset_state(self.state, torch.zeros(1))
            self.new_episode()
        elif self.grid:
            self.trail.append(player_pos(self.game))
        self.render()

    def render(self):
        lines = [f"Aktion : {ACTION_NAMES[self.action]}", f"Return : {self.ret:6.1f}  Schritt {self.t}"]
        n = len(self.returns)
        if self.grid:
            d = goal_dist(self.game)
            lines.append(f"Abstand: {'–' if d is None else d}  (Start {self.start_dist})")
            if n:
                o = self.outcomes
                sl = f"{np.mean(self.succ_len):.0f}" if self.succ_len else "–"
                lines.append(f"Ziel {o['goal']}  Grube {o['pit']}  Zeit {o['time']}")
                lines.append(f"Erfolg {o['goal'] / n:4.0%}  Ø Schritte {sl}")
        elif n:
            lines.append(f"Ø Ep.  : {np.mean(self.returns):6.1f} ({n})")
        if self.eval_text:
            lines.append(self.eval_text)
        trail = self.trail if self.grid and self.show_trail.get() else None
        map_img = None
        if self.grid and hasattr(self.game, "seen") and self.show_map.get():
            map_img = world_map(self.game, self.trail if self.show_trail.get() else [])
        elif self.map_photo is not None:
            self.map.configure(image="")
            self.map_photo = None
        origin = self.game.view_origin() if hasattr(self.game, "view_origin") else (0, 0)
        self.show(self.env.obs()[0], "\n".join(lines), trail=trail, origin=origin, map_img=map_img)

    def evaluate(self, games):
        rates, sl = outcome_stats(self.model, self.task, games, self.seed, self.policy)
        self.eval_text = (f"{N_EVAL} Ep.: Ziel {rates['goal']:.0%} Grube {rates['pit']:.0%} "
                          f"Zeit {rates['time']:.0%}" + (f"\n        Ø Schritte bis Ziel {sl:.0f}" if sl else ""))
        self.render()


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
    def step(self, obs, target, counted, cmd=None):
        spec = self.task.spec
        if cmd is not None and getattr(self.model, "takes_cmd", False):       # command port (models.attach_cmd)
            self.model.cmd = torch.from_numpy(cmd[None])
        logits, self.state = self.model(torch.from_numpy(obs[None]), self.state)
        if getattr(self.model, "takes_cmd", False):
            self.model.cmd = None
        lg = logits[0, spec.out_slice]
        if spec.head == "class":
            pred, tgt = int(lg.argmax()), int(target)
            ok = pred == tgt
            ptxt, ttxt = label_text(spec.name, pred), label_text(spec.name, tgt)
        else:
            pb = (lg > 0).int().numpy()
            ok = bool((pb == target).all())
            ptxt = "".join("#" if b else "." for b in pb)
            ttxt = "".join("#" if b else "." for b in target)
        trail = None
        if spec.group == "robot" and spec.name != "robot_reach":    # gaze shift as a line from the centre
            def steps(bits):
                v = [int("".join(str(int(x)) for x in bits[i:i + 4]), 2) for i in (0, 4)]
                return [x - 16 if x > 7 else x for x in v]
            pc, tc = steps(pb), steps(target)
            trail = [(7.5, 7.5), (7.5 + pc[0], 7.5 + pc[1])]
            ptxt, ttxt = f"({pc[0]:+d}, {pc[1]:+d})", f"({tc[0]:+d}, {tc[1]:+d})"
        if spec.name == "servo":                 # show the commanded step as a line from the pointer
            def steps(bits):
                v = [int("".join(str(int(x)) for x in bits[i:i + 4]), 2) for i in (0, 4)]
                return [x - 16 if x > 7 else x for x in v]
            (py, px), (pc, tc) = np.argwhere(obs[1] > 0)[0], (steps(pb), steps(target))
            trail = [(px, py), (px + pc[0], py + pc[1])]
            ptxt, ttxt = f"({pc[0]:+d}, {pc[1]:+d})", f"({tc[0]:+d}, {tc[1]:+d})"
        if counted:
            self.correct += ok
            self.total += 1
        acc = f"{self.correct / self.total:5.1%} ({self.total})" if self.total else "   –"
        mark = "" if counted else "  (Warm-up)"
        if cmd is not None:                      # robot_find: the command is the colour of the wanted object
            ttxt += "  Kmd " + " ".join(f"{v:.1f}" for v in cmd[:3]) + ("" if getattr(self.model, "takes_cmd", False) else " (ohne Eingang)")
        self.show(obs, f"Ziel   : {ttxt}{mark}\nVorhers: {ptxt}\nGenauig: {acc}",
                  (GOOD if ok else BAD) if counted else MUTED, trail=trail)


class App:
    def __init__(self, root, task="grid_easy"):
        self.root = root
        root.title("NetResearch – Modelle beobachten")
        root.configure(bg=BG)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", padx=8, pady=6)
        self.task_var = tk.StringVar(value=task)
        self.group_var = tk.StringVar(value=AVAILABLE)
        self.seed_var = tk.IntVar(value=0)
        self.speed_var = tk.IntVar(value=10)
        self.multi_var = tk.BooleanVar(value=False)
        self.trail_var = tk.BooleanVar(value=True)
        self.map_var = tk.BooleanVar(value=True)
        self.running = False

        def lab(t):
            tk.Label(bar, text=t, bg=BG, fg=FG).pack(side="left", padx=(8, 2))

        def check(text, var, cmd=None):
            tk.Checkbutton(bar, text=text, variable=var, bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
                           activeforeground=FG, command=cmd).pack(side="left", padx=(8, 0))
        lab("Task")
        ttk.Combobox(bar, textvariable=self.task_var, values=list(TASKS), width=16, state="readonly").pack(side="left")
        lab("Gruppe")
        ttk.Combobox(bar, textvariable=self.group_var, values=list(GROUPS), width=22, state="readonly").pack(side="left")
        check("Multi-Task", self.multi_var)
        lab("Seed")
        tk.Spinbox(bar, from_=0, to=9999, textvariable=self.seed_var, width=6).pack(side="left")
        ttk.Button(bar, text="Laden", command=self.load).pack(side="left", padx=8)
        self.run_btn = ttk.Button(bar, text="▶ Start", command=self.toggle)
        self.run_btn.pack(side="left")
        ttk.Button(bar, text="Schritt", command=self.step).pack(side="left", padx=4)
        ttk.Button(bar, text=f"Bewerten ({N_EVAL} Ep.)", command=self.evaluate).pack(side="left", padx=4)
        lab("Schritte/s")
        tk.Scale(bar, from_=1, to=60, orient="horizontal", variable=self.speed_var, bg=BG, fg=FG,
                 highlightthickness=0, length=120).pack(side="left")
        check("Spur", self.trail_var, self.redraw)
        check("Karte", self.map_var, self.redraw)
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
        self.panels = []
        is_game = task.spec.kind == "control"
        kw = {"show_trail": self.trail_var, "show_map": self.map_var}
        if is_game:
            self.panels.append(GamePanel(self.grid, "Experte", None, task, seed, "expert", **kw))
            self.panels.append(GamePanel(self.grid, "Zufall", None, task, seed, "random", **kw))
        have, missing = models_for(task.spec.name, self.group_var.get(), self.multi_var.get())
        for m in have:
            model = load_checkpoint(m, "multi" if self.multi_var.get() else task.spec.name, 0)
            self.panels.append(GamePanel(self.grid, m, model, task, seed, **kw) if is_game
                               else SupervisedPanel(self.grid, m, model, task))
        wide = is_game and hasattr(self.panels[0].game, "seen")      # view + map side by side
        cols = max(1, math.ceil(math.sqrt(len(self.panels) * (1.0 if wide else 1.8))))
        for i, p in enumerate(self.panels):
            p.frame.grid(row=i // cols, column=i % cols, padx=4, pady=4, sticky="n")
        self.seq, self.t = None, 0
        msg = f"{task.spec.name}: {task.spec.description}   |  {len(have)} Modelle"
        if missing:
            msg += f"   |  ohne Checkpoint: {', '.join(missing)}"
        self.status.configure(text=msg)
        if not is_game:
            self.step()

    def redraw(self):
        for p in self.panels:
            if isinstance(p, GamePanel):
                p.render()

    def evaluate(self):
        if self.task.spec.kind != "control":
            return
        was = self.running
        self.running = False
        self.status.configure(text=f"erzeuge {N_EVAL} Welten …")
        self.root.update()
        games = self.task.make_env(N_EVAL, int(self.seed_var.get()) + 12345).games   # the same for all panels
        for k, p in enumerate(self.panels, 1):
            self.status.configure(text=f"bewerte {p.name} ({k}/{len(self.panels)}) …")
            self.root.update()
            p.evaluate(games)
        self.status.configure(text=f"{self.task.spec.name}: {N_EVAL} neue Episoden je Panel bewertet "
                                   f"(für alle dieselben Welten)")
        if was:
            self.toggle()

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
        cmd = self.seq["cmd"][self.t, 0] if "cmd" in self.seq else None
        for p in self.panels:
            p.step(obs, target, counted, cmd)
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", default="grid_easy", choices=list(TASKS))
    a = ap.parse_args()
    torch.set_num_threads(2)
    root = tk.Tk()
    App(root, a.task)
    root.mainloop()


if __name__ == "__main__":
    main()
