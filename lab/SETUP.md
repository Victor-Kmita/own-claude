# Setting up the compute server (one-off, for a human)

Requirements: Linux, Python 3.11 or newer, git. No Python packages — the
simulator has no dependencies.

```bash
# 1. get the repository and the working branch
git clone https://github.com/victor-xm/own-claude.git
cd own-claude
git checkout claude/free-dev-time-8m9enc

# 2. let it push results back
git config user.name  "soup worker"
git config user.email "you@example.com"
gh auth login            # or add a deploy key with write access

# 3. check it works: 58 tests, about twenty seconds
python3 -m unittest discover -s tests

# 4. one worker in the foreground, to see it run
python3 lab/run_task.py loop
```

## Keeping workers alive

With systemd, one unit per worker:

```ini
# /etc/systemd/system/soup-worker@.service
[Unit]
Description=soup lab worker %i
After=network-online.target

[Service]
User=soup
WorkingDirectory=/home/soup/own-claude
ExecStart=/usr/bin/python3 lab/run_task.py loop --poll 300
Restart=always
RestartSec=30
Nice=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now soup-worker@{1..12}     # twelve workers
systemctl status soup-worker@1
journalctl -u soup-worker@1 -f
```

Leave one or two cores free for the machine and for Claude's own tools.

Without systemd, `tmux new -d -s soup 'python3 lab/run_task.py loop'` is enough,
repeated per worker, though it will not come back after a reboot.

## Claude Code on the same machine

Install it, run it in the repository directory, and it will read `CLAUDE.md`,
which points it at `lab/AGENT-SERVER.md`. Nothing else needs configuring: the
two agents coordinate entirely through files in this repository.

## What the worker is allowed to do

It runs `python3 -m soup run` with type-checked parameters, or a script that
already exists under `experiments/`. It does not execute anything a task file
supplies as text. New code can only arrive as a commit, which means it can be
read before it runs. Keep it that way.
