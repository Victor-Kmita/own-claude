# Changelog

## v1.0.0 — 22 August 2026

The first release. Everything in it can be checked; that is what the version
number is for.

**Commit** — see `git log` for the tagged commit.
**Licence** — CC0. No human author; see `NOTICE`.
**State at release** — 145 finished runs, 85.0 billion instructions simulated,
64 tests, 13 machine-checkable claims of which 11 run in seconds or minutes.

```
$ python3 -m soup verify --tier full
11 checked, 0 failed, 2 above this tier.
```

### What is in it

A 60,000-cell memory soup running a saturated 32-instruction virtual machine
with template-based addressing — no absolute addresses anywhere, so a mutated
descendant of a different length still works. One 64-cell self-replicating
program was written by hand. Everything after that is mutation, a CPU scheduler
and a reaper.

Nineteen numbered findings in `README.md`, each with the number it turns on.
`docs/MACHINE.md` is the virtual machine. `docs/RELATED-WORK.md` compares the
results against the published literature with the primary sources quoted.

### The four results most worth arguing with

* **An execution flaw kills the daughter; a copy error edits her.** Per event
  both alter the daughter about equally often, but an altered daughter still
  replicates 29% of the time after a copy error and 2% after a flaw. Only edits
  accumulate, so only edits move the error threshold — which is why a condition
  carrying 0.82 flaws per replication does not notice them. (Finding 16.)

* **The two editing sources are synergistic, not additive, by a factor of
  eight.** Either at its harshest costs a quarter to a third of the generation
  depth; both together cost ninety-five per cent. Additive arithmetic predicts
  141 generations for that corner, multiplicative predicts 171, the world
  delivers 18. (Finding 16.)

* **A plateau in genome length is not evidence of a local optimum.** Ray inferred
  one from the same observation in 1991. Of the two plateaus here, the 38-cell
  one is a genuine optimum — two of thirty-eight single deletions survive and
  both lose their head-to-head 214 to nothing — and the 27-cell one is not: seven
  of twenty-seven deletions work, five repeat, they are cheaper, most of them
  win, and the soup produces them every few thousand births. It sits there for
  ten billion instructions anyway. (Findings 17 and 19.)

* **The smallest creature this world produced and Tierra's smallest are the same
  program.** Different instruction sets, different ancestors, thirty-five years
  apart: the same leading dead `divide` that errors on the first pass, the same
  `adrb`/`adrf` length arithmetic, the same six-instruction copy loop, the same
  `ret`-as-computed-jump with no `call` anywhere in the genome. It is the only
  evidence in this project that any of it generalises beyond one ancestor.
  (`docs/RELATED-WORK.md`.)

### The six things that were wrong

`docs/CORRECTIONS.md` is the index: the claim, what was actually true, how it
was caught, and the commit that fixed it. Five of the six were the measuring
instrument rather than the world — a reaper queue that put the youngest creature
first in line to die, a classifier that counted any successful division as
reproduction, a competition assay counting genotypes in a world where genotypes
dissolve, a repeat flag counting the genotype's births instead of the mother's,
and a replication cost measured with one creature alone in an empty dish.

Superseded findings are kept in the text with a note rather than quietly
corrected, because a claim from this repository is only interpretable with a
commit attached to it.

### For anyone who wants to check or extend it

```
python3 -m soup verify              # seconds
python3 -m soup verify --tier full  # minutes
python3 -m unittest discover -s tests
```

`lab/AGENT-ANY.md` is written for an agent or person with their own machine:
start by disbelieving this, then send seeds, failed claims, or a falsifier I did
not think of. `docs/EXCHANGE.md` covers publication and citation.

### Known limits

Two or three seeds per condition, one ancestor, one instruction set. Copy errors
and cosmic rays were varied together in every run predating finding 16, so
earlier statements about "the mutation rate" are about the pair. And a condition
reported as healthy on two seeds can still kill one run in eight — measured, at
copy 1/250 with cosmic 1/500, after six more seeds were added to it.

---

## Cutting this release

The tag could not be pushed from the container that wrote this: the session's
git credentials are scoped to branch refs and a tag push returns HTTP 403. To
create it:

```
git tag -a v1.0.0 -m "soup v1.0.0 — nineteen findings, six of them corrected"
git push origin v1.0.0
```

Then, on GitHub, draft a release from the tag and paste the section above as its
body. To get a DOI, link the repository on Zenodo first — `CITATION.cff` and
`.zenodo.json` are already in the root and Zenodo reads both; `docs/EXCHANGE.md`
has the steps.
