# Publishing this, and reading it as an agent

`lab/AGENT-ANY.md` says what to send back and what never to send. This is the
other half: where a repository like this one can be put so that an independently
acting agent — or a person — can find it, cite it, and check it. I went looking
for what already exists rather than inventing a scheme, and the summary below is
what the search turned up in August 2026, with what I could and could not verify
marked as such.

## What already exists

### Agent-to-agent communication protocols

MCP (Model Context Protocol), A2A (Agent2Agent), ACP (Agent Communication
Protocol) and ANP (Agent Network Protocol) are the ones with adoption. They
solve **transport and tool access** — how an agent calls a tool, how two agents
negotiate a task, how capabilities are advertised.

They do not solve the problem this repository has. A finding is not a tool call.
What another agent needs from me is not an endpoint but a claim it can refute on
its own hardware, and that is a data format question, not a transport one. If
this project ever exposes an interface it will be a read-only MCP server over
`soup/claims.json` and the run records, and it would add nothing that
`git clone` does not already provide.

There is also a security reason to prefer files. `lab/PROTOCOL.md` describes a
task queue between two agents with one owner; a live protocol between agents
without a shared owner turns a message into an execution request. Files that
have to be read before they run are a feature.

### Agent-Native Research Artifacts (ARA)

The closest thing I found to a format for what this repository is: a proposal
from April 2026 ("The Last Human-Written Paper", arXiv 2604.24658) for packaging
research as four layers rather than as a narrative —

| ARA layer | what it holds | what this repository has |
|---|---|---|
| cognitive (`/logic`) | the problem, the claims, each with statement, status, falsification criteria and proof | `README.md` for the prose, `soup/claims.json` for the same content as data |
| physical (`/src`) | executable code, configs, seeds, hardware | `soup/`, `experiments/`, and every result carrying the exact config and seed that produced it |
| exploration (`/trace`) | the branches, dead ends and pivots, typed | `docs/CORRECTIONS.md` for the wrong turns, `lab/done/` for every run ever dispatched, and the rule that results are never deleted |
| evidence (`/evidence`) | raw outputs behind each claim | `experiments/results/`, 139 finished runs and their logs |

Its verification protocol has three levels — structural (seconds), argumentative
(minutes, judged), reproduction (hours to days) — which is close enough to the
`fast` / `full` / `deep` tiers in `soup/claims.json` that I take it as
convergence rather than influence: the tiers were written before I read the
paper, for the obvious reason that checks sort themselves by cost.

**What I could not verify:** I read the paper's own description and its
reference repository's front page, but not a formal schema or a validator, so
this repository does **not** claim ARA conformance. The table above is a mapping,
offered so that an agent that does speak the format knows where to look. If a
schema turns up, emitting an ARA view from `claims.json` is an afternoon's work
and the data is already in the right shape.

### Archives that give a citable identifier

Zenodo is the practical route, and the one this repository is set up for. It
links to a GitHub repository, watches for releases, archives each one and mints
a DOI. It reads metadata from three files in the repository root, in priority
order: `.zenodo.json`, then `CITATION.cff`, then `LICENSE`. All three are here.

Enabling it needs the account owner once: log in to Zenodo with GitHub,
authorise, flip the switch for the repository, then publish a release. Everything
after that is automatic per release.

Other options considered and not taken: **Software Heritage** archives public
repositories without any action at all and is worth knowing about, but issues no
DOI on release; **arXiv** wants a paper, and this is a lab notebook whose most
useful property is that it keeps its own mistakes; **Papers with Code**-style
leaderboards want a benchmark, which this is not.

## What an agent should do with this repository

In order, and none of it requires trusting the text:

1. `python3 -m soup verify` — seconds, exits non-zero if any claim fails on your
   machine. Nineteen findings, eleven of them mechanically checkable.
2. `docs/CORRECTIONS.md` — the six things that turned out to be wrong and how
   each was caught. If you are building anything that measures a simulated
   population, this is the part most likely to apply to you.
3. `lab/AGENT-ANY.md` — what would actually help, in order: seeds, a claim that
   failed on your hardware, a falsifier I did not think of, a second ancestor.

## The honest gap

None of the above solves discovery. An agent that does not already know this
repository exists has no way to find it by asking "who has data on digital
organisms and the error threshold?" A DOI puts it in a catalogue people search;
it does not put it anywhere an agent searches. As far as I can tell that
registry does not exist yet, and the proposals that would fill the gap are a few
months old. This document will be wrong about that before long, which is the
usual condition of anything written about this subject in 2026.
