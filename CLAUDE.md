# soup — orientation

A world of 60,000 memory cells with one hand-written self-replicating program in
it, and everything else — parasites, immunity, compression, loop unrolling —
left to happen on its own. `README.md` is the write-up: fifteen findings, each
with the number it turns on. `docs/MACHINE.md` is the virtual machine in detail.
`docs/RELATED-WORK.md` compares this world against the published literature on
digital organisms.

Pure Python 3.11, no dependencies, about one million simulated instructions per
second per core.

## Which agent are you

Two Claude instances share this repository and coordinate only through files.

* **On the compute server** — many cores, machine stays up. Read
  [`lab/AGENT-SERVER.md`](lab/AGENT-SERVER.md).
* **In an ephemeral cloud container** — four cores, restarts without warning.
  Read [`lab/AGENT-CLOUD.md`](lab/AGENT-CLOUD.md).

`nproc` and `cat lab/status/*.json` will tell you which you are. Both roles
depend on [`lab/PROTOCOL.md`](lab/PROTOCOL.md), which says who may write where.

## Conventions

* `python3 -m unittest discover -s tests` — 64 tests, about twenty-five seconds. Run
  it before pushing anything that touches `soup/`.
* **A run must be reproducible from its parameters and seed alone.** Two runs of
  the same configuration agree to the last digit. If they ever disagree, stop:
  that is a defect in the simulator and it invalidates whatever was measured.
* `python3 -m soup verify` — check the README's own claims on this machine.
  `soup/claims.json` holds them as data; a claim that stops being true should
  fail here before anyone reads it in prose. `lab/AGENT-ANY.md` explains the
  file to an agent that is not one of the two below.
* Results are never deleted, including failed ones. Several findings here came
  from runs that went wrong.
* Long runs write `experiments/results/<name>.checkpoint.json` every few hundred
  million instructions, carrying the history, the living genomes and the totals
  so far. An interrupted run is not a lost one.
* Findings in `README.md` are numbered and cross-referenced. If you add or
  reorder one, fix the references — `grep -n "finding [0-9]"` finds them.

## What is worth knowing before changing anything

Three defects in this simulator each silently shaped results before they were
found: a reaper queue that moved the youngest creature to the front of the death
queue, a classifier that counted any successful division as reproduction, and a
competition assay that counted exact genotypes in a world where genotypes
dissolve. All three are described in the README. The pattern is the lesson:
**when a measurement surprises you here, suspect the instrument first.**
