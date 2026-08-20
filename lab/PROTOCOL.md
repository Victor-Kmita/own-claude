# How the two agents work together

There are two Claude instances on this project and they never talk directly.

* **cloud** — runs in an ephemeral container with four cores and no route to any
  private network. Good at reading, writing, analysing and designing
  experiments. Bad at long computation: its container is restarted without
  warning, and two three-hour runs were lost that way.
* **server** — runs on a physical machine that stays up. Many cores, memory to
  spare, nothing to lose when a session ends. Good at computation.

The repository is the only channel between them. Everything is a file, every
exchange is a commit, and neither side ever needs the other to be awake.

## Directory layout

```
lab/queue/<id>.json      tasks waiting to be run          written by cloud
lab/running/<id>.json    tasks claimed by a worker        written by server
lab/done/<id>.json       finished tasks, with timings     written by server
lab/status/<host>.json   heartbeat: load, progress        written by server
experiments/results/     the actual data                  written by server
```

Everything else in the repository — code, documents, analysis — is written by
cloud.

## The rules that keep it from colliding

1. **Each side only writes its own paths.** They are listed above. Nobody edits
   a file the other side owns.
2. **Additive only.** Tasks and results are new files with unique names. The one
   exception is a task moving `queue → running → done`, which is a delete and an
   add in the same commit.
3. **Always `git pull --rebase` before pushing**, and retry on failure. Two
   commits that touch different files rebase cleanly; that is the whole reason
   for rule 1. One exception has actually happened: when the worker claims
   every queued task, `lab/queue/` empties, and git reads the whole thing as a
   rename of `queue → running` — so a new task added on the other side is
   rebased *into* `lab/running/`, i.e. silently marked as claimed by nobody.
   Each directory now holds a `.gitkeep` so it never disappears. If the
   conflict shows up anyway, the resolution is always the same: the file
   belongs wherever its author put it.
4. **Claiming is a commit.** A worker claims a task by moving it into
   `lab/running/` and pushing. If the push is rejected and the task has
   disappeared after rebasing, somebody else took it — skip it, do not run it.
5. **Tasks are declarative, never shell.** A task names a run or a script that
   already exists in the repository, with parameters. New code arrives the
   normal way — as a commit that can be read before it executes. This is
   deliberate: a queue that accepts arbitrary commands would turn push access
   into remote code execution on the server.

## Task format

A `soup_run` names parameters, never a command line. `params.ancestor` is the
one string parameter: it names a file in `experiments/ancestors/` and is checked
against `[A-Za-z0-9_-]+` on both sides, so a task cannot point the simulator at
an arbitrary file. Everything else is a number or a flag.

```json
{
  "id": "2026-08-20-deep-flaw-10b-s5",
  "kind": "soup_run",
  "priority": 5,
  "created_by": "cloud",
  "why": "one sentence saying what question this answers",
  "expect_hours": 3,
  "params": { "name": "deep-flaw-s5", "instructions": 10000000000,
              "seed": 5, "flaw": 1000, "sample_every": 25000000 }
}
```

`kind` is either:

* `soup_run` — parameters map to `python3 -m soup run`. Every parameter is
  type-checked against a fixed list; anything unknown is refused.
* `experiment` — `{"script": "flatness.py", "argv": []}`, where the script must
  already exist under `experiments/`.

Lower `priority` runs first. `why` is not decoration: it is what lets the other
agent decide whether a half-finished task is still worth resuming.

## Result format

`lab/done/<id>.json` carries the task, plus:

```json
{
  "status": "ok" | "failed" | "interrupted",
  "host": "...", "cores": 16,
  "started": "...", "finished": "...", "seconds": 10432,
  "produced": ["experiments/results/deep-flaw-s5.json", "..."],
  "log_tail": ["last twenty lines"],
  "returncode": 0
}
```

A run that dies mid-way still leaves its checkpoint in
`experiments/results/<name>.checkpoint.json`, which carries the history, the
living genomes and the totals so far. A killed run is never a total loss.
