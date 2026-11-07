"""Submit benchmark jobs to remote workers (netresearch.worker) via the shared folder, check status, fetch results.

    python -m netresearch.jobs submit seeds12 -- --models all --tasks all --seeds 1 2
    python -m netresearch.jobs status
    python -m netresearch.jobs fetch <job id> --into results/runs.jsonl [--checkpoints]
    python -m netresearch.jobs cancel <job id>          # only while still queued

A job runs the commit that is checked out here when submitting; it must be pushed to origin
(the worker fetches it from GitHub). Everything after "--" is passed to netresearch.bench
(without --out / --workers: the worker sets them; a job can fix the process count with --workers here).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .worker import DEFAULT_SHARE, DIRS, ROOT, read_json, write_json


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def submit(share, name, bench_args, workers, allow_dirty):
    if any(a in ("--out", "--workers") for a in bench_args):
        raise SystemExit("--out / --workers are set by the worker (use 'submit --workers N' for a fixed count)")
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no") and not allow_dirty:
        raise SystemExit("uncommitted changes: the worker would not run them. Commit and push first "
                         "(or --allow-dirty).")
    git("fetch", "--quiet", "origin")
    if "origin/" not in git("branch", "-r", "--contains", commit):
        raise SystemExit(f"commit {commit[:7]} is not pushed to origin yet: git push first.")
    jid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^A-Za-z0-9_-]", "_", name)
    job = {"id": jid, "name": name, "commit": commit, "args": bench_args, "workers": workers,
           "created": datetime.now().isoformat(timespec="seconds")}
    write_json(share / "jobs" / "queue" / f"{jid}.json", job)
    digits = ROOT / "data" / "digits.npz"
    if digits.exists() and not (share / "data" / "digits.npz").exists():
        shutil.copy2(digits, share / "data" / "digits.npz")
    print(f"queued {jid} ({commit[:7]}): {' '.join(bench_args)}")


def progress(share, jid):
    """'k/N' from the bench log of a job."""
    log = share / "results" / jid / "bench.log"
    if not log.exists():
        return ""
    text = log.read_text(encoding="utf-8", errors="replace")
    total = re.findall(r"^(\d+) jobs \(", text, re.M)
    done = re.findall(r"^\[(\d+)/(\d+) +([\d.]+)min\]", text, re.M)
    errors = text.count("ERROR ")
    if done:
        k, n, m = done[-1]
        return f"{k}/{n} runs, {float(m):.0f} min" + (f", {errors} errors" if errors else "")
    return f"0/{total[-1]} runs" if total else "starting"


def status(share):
    print("workers:")
    for p in sorted((share / "workers").glob("*.json")):
        w = read_json(p)
        print(f"  {w['host']:16s} {w['state']:8s} last seen {w['time']}  {w.get('job') or ''}")
    for state in ("queue", "running", "done", "failed"):
        files = sorted((share / "jobs" / state).glob("*.json"))
        if not files:
            continue
        print(f"{state}:")
        for p in files[-15:]:
            j = read_json(p)
            extra = progress(share, j["id"]) if state in ("running", "done", "failed") else ""
            if state in ("done", "failed"):
                extra += f"  ({j.get('minutes', '?')} min, exit {j.get('exit_code', '?')})"
                if j.get("error"):
                    extra += "  " + j["error"].splitlines()[0]
            print(f"  {j['id']:40s} {j.get('host', ''):14s} {' '.join(j['args'])[:60]:60s} {extra}")


def fetch(share, jid, into, checkpoints):
    """Append the job's result lines that are not yet in `into` (key: model, task, seed, updates)."""
    src = share / "results" / jid / "runs.jsonl"
    if not src.exists():
        raise SystemExit(f"no results for {jid}")
    into = Path(into)

    def key(r):
        return r["model"], r["task"], r["seed"], r.get("updates_per_task", r.get("updates"))
    have = set()
    if into.exists():
        have = {key(json.loads(ln)) for ln in into.read_text().splitlines() if ln.strip()}
    new = [ln for ln in src.read_text().splitlines()
           if ln.strip() and "error" not in json.loads(ln) and key(json.loads(ln)) not in have]
    into.parent.mkdir(parents=True, exist_ok=True)
    with into.open("a") as f:
        for ln in new:
            f.write(ln + "\n")
    print(f"{len(new)} new results appended to {into}")
    if checkpoints and (share / "results" / jid / "checkpoints").exists():
        shutil.copytree(share / "results" / jid / "checkpoints", ROOT / "results" / "checkpoints",
                        dirs_exist_ok=True)
        print("checkpoints copied to results/checkpoints")


def cancel(share, jid):
    p = share / "jobs" / "queue" / f"{jid}.json"
    if not p.exists():
        raise SystemExit(f"{jid} is not in the queue (running jobs: create workers/STOP_<host> and restart)")
    os.remove(p)
    print(f"removed {jid}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--share", default=DEFAULT_SHARE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("name")
    s.add_argument("--workers", type=int, default=None)
    s.add_argument("--allow-dirty", action="store_true")
    s.add_argument("bench_args", nargs=argparse.REMAINDER)
    sub.add_parser("status")
    f = sub.add_parser("fetch")
    f.add_argument("job")
    f.add_argument("--into", required=True)
    f.add_argument("--checkpoints", action="store_true")
    c = sub.add_parser("cancel")
    c.add_argument("job")
    a = ap.parse_args()
    share = Path(a.share)
    for d in DIRS:
        (share / d).mkdir(parents=True, exist_ok=True)
    if a.cmd == "submit":
        args = a.bench_args[1:] if a.bench_args[:1] == ["--"] else a.bench_args
        submit(share, a.name, args, a.workers, a.allow_dirty)
    elif a.cmd == "status":
        status(share)
    elif a.cmd == "fetch":
        fetch(share, a.job, a.into, a.checkpoints)
    else:
        cancel(share, a.job)


if __name__ == "__main__":
    main()
