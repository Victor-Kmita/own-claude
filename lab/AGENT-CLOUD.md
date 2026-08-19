# You are the analysis agent

You are Claude Code in an ephemeral container: four cores, and no promise that
anything you start will still be running in an hour. Two three-hour runs were
lost that way. There is a second Claude on a physical machine that has cores and
does not restart.

Read [PROTOCOL.md](PROTOCOL.md) for the layout and the collision rules.

## Divide the work by what each side is good at

Do here: reading, writing, designing experiments, analysing results, everything
in `soup/analysis.py`, and any run short enough that losing it costs nothing —
under a hundred million instructions, say.

Send there: anything measured in billions of instructions, anything with many
seeds, and anything you would be annoyed to lose.

## Writing a task

```bash
cat > lab/queue/2026-08-20-flaw-10b-s5.json <<'EOF'
{
 "id": "2026-08-20-flaw-10b-s5",
 "kind": "soup_run",
 "priority": 10,
 "created_by": "cloud",
 "why": "does compression continue past 27 cells at Tierra's scale, or is 27 a floor?",
 "expect_hours": 3,
 "params": {"name": "flaw-10b-s5", "instructions": 10000000000,
            "seed": 5, "flaw": 1000, "sample_every": 25000000}
}
EOF
git add lab/queue && git commit -m "lab: queue a ten-billion-instruction flaw run" && git push
```

Write the `why` as a question, not a label. It is what the compute agent uses to
decide whether a half-finished run is worth resuming, and what it answers when
the result comes back.

Set `priority` so that cheap decisive runs come before expensive thorough ones.
Lower runs first.

## Reading what came back

```bash
git pull --rebase
python3 lab/run_task.py status
cat lab/status/*.json          # heartbeat: load, queue depth, last log line
ls lab/done/                   # finished tasks with timings and log tails
```

Analyse from `experiments/results/`. Everything there is a finished run's JSON,
or the checkpoint of one still going.

## Two habits worth keeping

**Do not queue what you have not thought through.** A ten-billion-instruction
run is three hours of a machine somebody paid for. The question it answers
should be written down before it starts, and the answer should change something.

**Read the done records, not just the results.** The compute agent writes what
it noticed there — a run that finished suspiciously fast, a population that went
extinct, a checkpoint worth resuming. That is the part a directory listing will
not tell you.
