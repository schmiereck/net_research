"""Remote worker: runs benchmark jobs from a shared folder (e.g. OneDrive), started once on the compute PC.

    python -m netresearch.worker --share "C:/Users/<user>/OneDrive/Dokumente/#Projekte/NetResearch" --workers 14

Loop: take the oldest job from <share>/jobs/queue, check out the job's git commit (fetched from origin; the
repo is public, so no credentials are needed), run `netresearch.bench` (or `netresearch.sieve run` for
sieve jobs) with the job's arguments and copy
results, log and checkpoints to <share>/results/<job id>/. Jobs are submitted with `netresearch.jobs`.

Share layout:
    jobs/queue/<id>.json      waiting               jobs/running/<id>.json   being run (with host)
    jobs/done/<id>.json       finished (exit 0)     jobs/failed/<id>.json    exit != 0 or git problem
    results/<id>/             runs.jsonl, bench.log, checkpoints/
    workers/<host>.json       heartbeat (time, job, last log line)
    workers/STOP              create this file to stop all workers after the current job
                              (workers/STOP_<host> stops one worker)
    data/digits.npz           copied into data/ before every job, so all PCs use the same digit images

Bench writes into a local folder (results/remote/<id>/) that is mirrored to the share every minute; this
avoids OneDrive locking a file that is open for writing. An interrupted job (Ctrl+C, reboot) goes back into
the queue and resumes: bench skips the runs already in runs.jsonl.

Use a clone that is only used by the worker: it is switched to the job's commit (detached HEAD).
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = socket.gethostname()
DEFAULT_SHARE = os.environ.get("NETRESEARCH_SHARE", r"C:\Users\thomas\OneDrive\Dokumente\#Projekte\NetResearch")
DIRS = ("jobs/queue", "jobs/running", "jobs/done", "jobs/failed", "results", "workers", "data")


def now():
    return datetime.now().isoformat(timespec="seconds")


def log(msg):
    print(f"[{now()}] {msg}", flush=True)


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def retry(fn, *args, tries=10, wait=3.0):
    """OneDrive briefly locks files while it syncs them (PermissionError / WinError 5): try again a few times."""
    for i in range(tries):
        try:
            return fn(*args)
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(wait)


def replace(src, dst):
    retry(os.replace, src, dst)


def write_json(p, obj):
    p = Path(p)
    tmp = p.with_suffix(".tmp")
    retry(tmp.write_text, json.dumps(obj, indent=1), "utf-8")
    replace(tmp, p)


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.rstrip()          # keep leading blanks: "git status --porcelain" columns


def checkout(commit):
    """Fetch origin and switch the worker clone to commit (default: origin/main)."""
    git("fetch", "--quiet", "origin")
    lines = git("status", "--porcelain", "--untracked-files=no").splitlines()
    generated = [ln[3:] for ln in lines if ln[3:].startswith("results/")]
    if generated:                                       # files written by bench runs (e.g. game baselines)
        git("checkout", "--", *generated)
    dirty = "\n".join(ln for ln in lines if not ln[3:].startswith("results/"))
    if dirty:
        raise RuntimeError("worker clone has local changes, refusing to switch commits:\n" + dirty)
    git("checkout", "--quiet", "--detach", commit or "origin/main")
    return git("rev-parse", "--short", "HEAD")


def mirror(local, remote):
    """Copy new or changed files from local to remote (one direction)."""
    for src in local.rglob("*"):
        if src.is_file():
            dst = remote / src.relative_to(local)
            st = src.stat()
            if dst.exists() and dst.stat().st_size == st.st_size and dst.stat().st_mtime >= st.st_mtime:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except OSError as e:                        # e.g. OneDrive holds the file; retry next time
                log(f"copy failed ({e}), retrying later")


def last_line(p):
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        return lines[-1] if lines else ""
    except OSError:
        return ""


class Worker:
    def __init__(self, share, workers, poll):
        self.share, self.workers, self.poll = Path(share), workers, poll
        for d in DIRS:
            (self.share / d).mkdir(parents=True, exist_ok=True)
        self.beat_file = self.share / "workers" / f"{HOST}.json"

    def beat(self, state, job=None, line=""):
        try:
            write_json(self.beat_file, {"host": HOST, "time": now(), "state": state, "job": job,
                                        "workers": self.workers, "last": line})
        except OSError as e:                               # a missed heartbeat must not stop the worker
            log(f"heartbeat failed ({e}), retrying later")

    def stop_requested(self):
        w = self.share / "workers"
        return (w / "STOP").exists() or (w / f"STOP_{HOST}").exists()

    def requeue_own(self):
        """Jobs left in running/ by this host (crash, reboot) go back to the queue."""
        for p in (self.share / "jobs" / "running").glob("*.json"):
            try:
                job = read_json(p)
            except (OSError, ValueError):
                continue
            if job.get("host") == HOST:
                log(f"requeue interrupted job {job['id']}")
                replace(p, self.share / "jobs" / "queue" / p.name)

    def claim(self):
        for p in sorted((self.share / "jobs" / "queue").glob("*.json")):
            dst = self.share / "jobs" / "running" / p.name
            try:
                os.replace(p, dst)
            except OSError:
                continue                                   # taken by another worker
            job = read_json(dst)
            job.update(host=HOST, started=now())
            write_json(dst, job)
            return job, dst
        return None, None

    def finish(self, job, path, ok, **info):
        job.update(finished=now(), **info)
        write_json(path, job)
        replace(path, self.share / "jobs" / ("done" if ok else "failed") / path.name)

    def run_job(self, job, path):
        jid = job["id"]
        remote = self.share / "results" / jid
        local = ROOT / "results" / "remote" / jid
        local.mkdir(parents=True, exist_ok=True)
        remote.mkdir(parents=True, exist_ok=True)
        try:
            commit = checkout(job.get("commit"))
        except RuntimeError as e:
            log(f"job {jid}: {e}")
            self.finish(job, path, False, error=str(e))
            return
        digits = self.share / "data" / "digits.npz"
        if digits.exists():
            (ROOT / "data").mkdir(exist_ok=True)
            shutil.copy2(digits, ROOT / "data" / "digits.npz")
        out = local / "runs.jsonl"
        if not out.exists() and (remote / "runs.jsonl").exists():
            shutil.copy2(remote / "runs.jsonl", out)        # resume a job started earlier
        logf = local / "bench.log"
        args = [sys.executable, "-m", job.get("module", "netresearch.bench"), *job["args"],
                "--workers", str(job.get("workers") or self.workers), "--out", str(out)]
        env = dict(os.environ, NETRESEARCH_CKPT_DIR=str(local / "checkpoints"), PYTHONUNBUFFERED="1")
        log(f"job {jid} at {commit}: {' '.join(job['args'])}")
        t0 = time.time()
        with logf.open("a", encoding="utf-8") as lf:
            lf.write(f"# job {jid} host {HOST} commit {commit} started {now()}\n")
            lf.flush()
            proc = subprocess.Popen(args, cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    time.sleep(self.poll)
                    try:
                        mirror(local, remote)
                    except OSError as e:
                        log(f"mirror failed ({e}), retrying later")
                    self.beat("running", jid, last_line(logf))
            except BaseException as e:                         # Ctrl+C or an unexpected error:
                log(f"stopping bench ({e!r}), job goes back to the queue")
                proc.terminate()                               # never leave bench running orphaned
                proc.wait()
                try:
                    mirror(local, remote)
                    job.pop("host", None)
                    write_json(path, job)
                    replace(path, self.share / "jobs" / "queue" / path.name)
                except OSError as e2:                          # requeue_own() fixes it at the next start
                    log(f"requeue failed ({e2})")
                raise
        mirror(local, remote)
        rc = proc.returncode
        log(f"job {jid} finished, exit {rc}, {(time.time() - t0) / 60:.1f} min")
        self.finish(job, path, rc == 0, exit_code=rc, commit_run=commit, minutes=round((time.time() - t0) / 60, 1))

    def loop(self, once=False):
        self.requeue_own()
        log(f"worker {HOST} on {self.share}, {self.workers} bench workers")
        while not self.stop_requested():
            job, path = self.claim()
            if job is None:
                if once:
                    break
                self.beat("idle")
                time.sleep(self.poll)
                continue
            self.run_job(job, path)
            if once:
                break
        self.beat("stopped")
        log("worker stopped")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--share", default=DEFAULT_SHARE, help="shared folder (default: $NETRESEARCH_SHARE)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2),
                    help="parallel bench processes per job (a job can override this)")
    ap.add_argument("--poll", type=int, default=60, help="seconds between queue checks / mirroring")
    ap.add_argument("--once", action="store_true", help="run at most one job, then exit")
    a = ap.parse_args()
    try:
        Worker(a.share, a.workers, a.poll).loop(a.once)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
