"""The worker that turns queued tasks into results.

Usage on the compute server:

    python3 lab/run_task.py loop            # claim, run, publish, repeat
    python3 lab/run_task.py once            # do exactly one task and stop
    python3 lab/run_task.py status          # what is queued, running, done

Run several `loop` workers to use several cores; each claims its own task and
they coordinate through git, so two workers never run the same one.

Everything this script does to the repository is additive and confined to
`lab/` and `experiments/results/`, which is what keeps it from colliding with
the other agent's commits.  See lab/PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(REPO, "lab")
QUEUE, RUNNING, DONE, STATUS = (os.path.join(LAB, d) for d in
                                ("queue", "running", "done", "status"))
RESULTS = os.path.join(REPO, "experiments", "results")
HOST = socket.gethostname()
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# The only parameters a task may set, and what each one has to be.  Anything
# else is refused: a queue that passed unknown arguments through to a shell
# would make push access to this repository equivalent to a login on the
# server.
SOUP_PARAMS = {
    "name": (str, "--"), "instructions": (int, "--instructions"),
    "seed": (int, "--seed"), "soup": (int, "--soup"),
    "slice_size": (float, "--slice-size"), "slice_pow": (float, "--slice-pow"),
    "copy_mutation": (int, "--copy-mutation"), "cosmic": (int, "--cosmic"),
    "flaw": (int, "--flaw"), "sample_every": (int, "--sample-every"),
    "reap_threshold": (float, "--reap-threshold"),
    "search_limit": (int, "--search-limit"),
    "lazy_reaper": (bool, "--lazy-reaper"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True,
                          text=True, check=check)


def branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def sync(use_git: bool) -> None:
    if use_git:
        git("pull", "--rebase", "origin", branch(), check=False)


def publish(message: str, paths: list[str], use_git: bool, tries: int = 5) -> bool:
    """Commit the given paths and push, rebasing over whatever arrived meanwhile."""
    if not use_git:
        return True
    git("add", "--all", *paths, check=False)
    if not git("diff", "--cached", "--quiet", check=False).returncode:
        return True                                   # nothing staged
    git("commit", "-q", "-m", message, check=False)
    delay = 2
    for attempt in range(tries):
        if not git("push", "origin", branch(), check=False).returncode:
            return True
        git("pull", "--rebase", "origin", branch(), check=False)
        time.sleep(delay)
        delay = min(delay * 2, 30)
    print(f"could not push after {tries} attempts; the commit is local", file=sys.stderr)
    return False


def load_tasks(directory: str) -> list[dict]:
    out = []
    for entry in sorted(os.listdir(directory)) if os.path.isdir(directory) else []:
        if not entry.endswith(".json"):
            continue
        with open(os.path.join(directory, entry)) as fh:
            try:
                task = json.load(fh)
            except json.JSONDecodeError:
                continue
        task["_file"] = os.path.join(directory, entry)
        out.append(task)
    return out


def command_for(task: dict) -> list[str]:
    """Turn a task into an argument list.  Raises ValueError if it is not valid."""
    kind = task.get("kind")
    if kind == "soup_run":
        params = task.get("params") or {}
        name = params.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise ValueError(f"bad or missing run name: {name!r}")
        argv = [sys.executable, "-m", "soup", "run", name]
        for key, value in params.items():
            if key == "name":
                continue
            if key not in SOUP_PARAMS:
                raise ValueError(f"unknown parameter {key!r}")
            want, flag = SOUP_PARAMS[key]
            if want is bool:
                if value:
                    argv.append(flag)
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{key} must be a number, got {value!r}")
            argv += [flag, str(want(value))]
        return argv
    if kind == "experiment":
        script = task.get("params", {}).get("script", "")
        if not re.match(r"^[A-Za-z0-9_]+\.py$", script):
            raise ValueError(f"bad script name: {script!r}")
        path = os.path.join(REPO, "experiments", script)
        if not os.path.exists(path):
            raise ValueError(f"no such script: experiments/{script}")
        argv = [sys.executable, path]
        for item in task.get("params", {}).get("argv", []):
            if not isinstance(item, (str, int, float)) or not NAME_RE.match(str(item)):
                raise ValueError(f"bad argument: {item!r}")
            argv.append(str(item))
        return argv
    raise ValueError(f"unknown task kind: {kind!r}")


def claim(use_git: bool) -> dict | None:
    """Take the highest-priority queued task, or return None."""
    sync(use_git)
    tasks = load_tasks(QUEUE)
    if not tasks:
        return None
    tasks.sort(key=lambda t: (t.get("priority", 50), t.get("id", "")))
    task = tasks[0]
    task_id = task.get("id") or os.path.basename(task["_file"])[:-5]
    target = os.path.join(RUNNING, f"{task_id}.json")
    os.makedirs(RUNNING, exist_ok=True)
    record = {k: v for k, v in task.items() if k != "_file"}
    record.update({"claimed_by": HOST, "claimed_at": now(),
                   "cores": os.cpu_count()})
    with open(target, "w") as fh:
        json.dump(record, fh, indent=1)
    os.remove(task["_file"])
    if not publish(f"lab: {HOST} claims {task_id}", [QUEUE, RUNNING], use_git):
        return None
    # If the rebase took our claim away, somebody else got there first.
    if use_git and not os.path.exists(target):
        return None
    record["_file"] = target
    return record


def finish(task: dict, status: str, started: float, proc: subprocess.CompletedProcess | None,
           before: set[str], use_git: bool) -> None:
    task_id = task.get("id", "task")
    produced = sorted(set(os.listdir(RESULTS)) - before) if os.path.isdir(RESULTS) else []
    tail = []
    if proc is not None:
        tail = (proc.stdout or "").splitlines()[-20:]
    record = {k: v for k, v in task.items() if k != "_file"}
    record.update({
        "status": status, "host": HOST, "cores": os.cpu_count(),
        "finished": now(), "seconds": round(time.time() - started, 1),
        "returncode": proc.returncode if proc else None,
        "produced": [f"experiments/results/{p}" for p in produced],
        "log_tail": tail,
    })
    os.makedirs(DONE, exist_ok=True)
    with open(os.path.join(DONE, f"{task_id}.json"), "w") as fh:
        json.dump(record, fh, indent=1)
    if os.path.exists(task["_file"]):
        os.remove(task["_file"])
    publish(f"lab: {task_id} {status} on {HOST} "
            f"({record['seconds']:.0f}s)", [RUNNING, DONE, RESULTS], use_git)


def run_one(use_git: bool) -> bool:
    task = claim(use_git)
    if task is None:
        return False
    task_id = task.get("id", "task")
    try:
        argv = command_for(task)
    except ValueError as exc:
        print(f"refusing {task_id}: {exc}", file=sys.stderr)
        finish(task, "refused", time.time(), None, set(), use_git)
        return True
    before = set(os.listdir(RESULTS)) if os.path.isdir(RESULTS) else set()
    print(f"[{now()}] {task_id}: {' '.join(argv)}", flush=True)
    started = time.time()
    try:
        proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
        status = "ok" if proc.returncode == 0 else "failed"
    except KeyboardInterrupt:
        finish(task, "interrupted", started, None, before, use_git)
        raise
    finish(task, status, started, proc, before, use_git)
    print(f"[{now()}] {task_id}: {status} in {time.time() - started:.0f}s", flush=True)
    return True


def heartbeat(use_git: bool, push: bool) -> None:
    os.makedirs(STATUS, exist_ok=True)
    running = [t.get("id") for t in load_tasks(RUNNING)]
    progress = {}
    for task in load_tasks(RUNNING):
        name = (task.get("params") or {}).get("name")
        log = os.path.join(RESULTS, f"{name}.log") if name else None
        if log and os.path.exists(log):
            with open(log) as fh:
                lines = fh.readlines()
            progress[name] = lines[-1].strip() if lines else ""
    state = {
        "host": HOST, "time": now(), "cores": os.cpu_count(),
        "load": os.getloadavg(), "queued": len(load_tasks(QUEUE)),
        "running": running, "done": len(load_tasks(DONE)), "progress": progress,
    }
    with open(os.path.join(STATUS, f"{HOST}.json"), "w") as fh:
        json.dump(state, fh, indent=1)
    if push:
        publish(f"lab: heartbeat from {HOST}", [STATUS], use_git)


def cmd_status() -> None:
    print(f"queued  {len(load_tasks(QUEUE))}")
    for task in load_tasks(RUNNING):
        print(f"running {task.get('id')}  claimed by {task.get('claimed_by')} "
              f"at {task.get('claimed_at')}")
    done = load_tasks(DONE)
    print(f"done    {len(done)}")
    for task in done[-5:]:
        print(f"        {task.get('id')}  {task.get('status')}  "
              f"{task.get('seconds', 0):.0f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["once", "loop", "status"])
    parser.add_argument("--poll", type=int, default=300,
                        help="seconds to wait when the queue is empty")
    parser.add_argument("--heartbeat", type=int, default=900,
                        help="seconds between pushed heartbeats")
    parser.add_argument("--no-git", action="store_true",
                        help="work on local files only; for testing")
    args = parser.parse_args()
    use_git = not args.no_git

    if args.mode == "status":
        cmd_status()
        return
    if args.mode == "once":
        if not run_one(use_git):
            print("queue is empty")
        heartbeat(use_git, push=False)
        return

    last_beat = 0.0
    while True:
        try:
            worked = run_one(use_git)
            if time.time() - last_beat > args.heartbeat:
                heartbeat(use_git, push=True)
                last_beat = time.time()
            if not worked:
                time.sleep(args.poll)
        except KeyboardInterrupt:
            print("stopping")
            return
        except Exception as exc:                       # keep the worker alive
            print(f"worker error: {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(min(args.poll, 60))


if __name__ == "__main__":
    main()
