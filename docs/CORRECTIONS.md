# Everything in this project that turned out to be wrong

The findings in `README.md` are numbered and several of them have been rewritten.
This file is the index of those rewrites: what was claimed, what was actually
true, how it was caught, and the commit that fixed it. Nothing here is deleted
from the write-up — the superseded version stays in the text with a note — but
the write-up is long, and a reader who wants only the failures should not have
to hunt for them.

Five of the six entries are the same shape. A number looked surprising, the
instrument got suspected before the world did, and the instrument was at fault.
That is the house rule of this project and it is five for six.

---

## 1. The reaper queue ran backwards

**Claimed** — creatures die oldest-first, so the reaper is a pure age filter and
the results of the housekeeping-policy sweep measure what the policy does.

**Actually** — the queue removed an entry by swapping it with the last one,
which moves the *youngest* creature to the front of the line to die. Every run
before the fix had a death process that partly inverted age.

**Caught by** — the population's age structure not looking like anything a
first-in-first-out queue should produce.

**Fixed in** — `800dec12`, a doubly linked list, followed by `0a647ffd`, which
re-ran every experiment on the corrected machine and rewrote the findings rather
than patching the numbers.

**Cost** — every result in the project up to that point.

---

## 2. Dividing was counted as reproducing

**Claimed** — the cheapest replicator found so far costs *n* instructions per
daughter.

**Actually** — the classifier counted any successful `divide` as reproduction. A
creature that asks for the smallest legal block, scribbles in half of it and
splits has reproduced *something* in a few dozen instructions and has never made
a copy of itself. Those creatures were topping the cost table.

**Caught by** — a champion whose cost was implausibly low for its length.

**Fixed in** — `800dec12`. Classification now requires an exact self-copy, and
`test_dividing_is_not_the_same_as_reproducing` pins it.

---

## 3. The competition assay counted exact genotypes

**Claimed** — in head-to-head competition, genotype A beats genotype B.

**Actually** — in a soup with mutation on, an exact genotype dissolves within a
few thousand births; the assay was counting a label that had stopped existing,
and reported single-digit birth counts after forty million instructions. Worse,
with the counting corrected the answer to one competition reversed.

**Caught by** — birth counts that were three orders of magnitude too small.

**Fixed in** — `fa10b184`, which accumulates births per *lineage* as they
happen, since summing over the living population misses everyone already reaped
— at steady state, nearly everyone.

---

## 4. "Twenty-seven cells is a floor"

**Claimed** — finding 17, as first written: four independent runs converge on a
27-cell replicator and ten billion instructions do not go below it, so 27 is
where this world bottoms out.

**Actually** — not a floor at all. Seven of the 27 single-cell deletions of the
champion still replicate, five of those still go round again, they are cheaper,
most of them beat their parent in a head-to-head, and the soup manufactures
26-cell genotypes every few thousand births. The population sits at 27 anyway.
The real finding — that length evolution freezes at a plateau which need not be
a local optimum — is more interesting than the one it replaced, and Ray reported
the same freezing in 1991.

**Caught by** — asking what "floor" would have to mean, and then enumerating the
neighbourhood instead of asserting it.

**Fixed in** — `64136f5f`, with `experiments/deletion_floor.py` so the check
re-runs.

---

## 5. `repeats` counted the genotype's births, not the mother's

**Claimed** — three of the four 27-cell champions make more than one daughter,
so the one-shot strategy noted in finding 13 was a property of that lineage
rather than of the length.

**Actually** — the isolation assay incremented its repeat counter whenever the
*genotype* recorded a birth. Every one-shot has a daughter that divides once —
that is what a one-shot is — so the flag read `True` for almost everything. Two
of the four repeat. Finding 13's original reading was right all along, and the
correction of it was the artefact.

**Caught by** — a creature reported as a repeater that produced 110 births in a
billion instructions when it was actually run.

**Fixed in** — `6dfd8299`, counting the mother's own births, with
`test_repeating_is_the_mothers_own_second_daughter`.

---

## 6. Cost was measured in an empty dish

**Claimed** — the headline cost of every champion in findings 4, 5, 13 and 17:
instructions from start to first daughter, cultured alone.

**Actually** — for most genomes that transfers to a population within a fifth,
and for four of the nine deep-run champions it understates the true cost by
eight to a hundred times. Two 27-cell creatures with solo costs of 178 and 180
cost their populations 1,573 and 219. The split is exactly the one-shots against
the repeaters, so defects 5 and 6 are the same defect seen from two directions.

**Caught by** — starting a run from the champion and getting 110 births in a
billion instructions.

**Fixed in** — `6dfd8299`, which added `analysis.sustained_cost`, and `68806dce`,
which rewrote the affected findings. Consequence: the best creature this world
has produced is not the one that had been quoted for two days.

---

## And one that was not the instrument

## 7. Mutational load does not simply add across sources

**Claimed** — collapse depends on the total number of mutational events per
replication and not on which source produces them. Stated as a falsifiable
prediction, with the arithmetic written out, before the runs.

**Actually** — false twice over. Execution flaws barely count at all, because
they kill the daughter rather than editing her, and only edits accumulate. And
the two sources that *do* edit are synergistic rather than additive: either at
its harshest costs a quarter to a third of the generation depth, both together
cost ninety-five per cent, where additive arithmetic predicts 141 generations
and the world delivers 18.

**Caught by** — eighteen runs designed to test it, then twelve more to separate
the confounded sources, then eighteen more as a dose–response grid.

**Recorded in** — finding 16. This is the one entry here where the world was the
surprise rather than the instrument, and it is also the only one that was
predicted in advance and then measured. Those two facts are probably related.

---

## What the pattern is worth

Six of seven were measurement, not nature. In every case the wrong number was
*plausible* — that is what made it survive. The reaper produced sensible-looking
age structure; the fragment that divided in forty instructions looked like a
brilliant optimisation; the solo cost of a one-shot is a real number honestly
measured, of the wrong thing.

`python3 -m soup verify` exists because of this list. It re-checks every claim
that can be checked by running something, and on its first run it caught a
seventh error — two 27-cell champions with their deletion counts swapped in a
table written an hour earlier. That one never reached this file because it never
survived an hour, which is the point.
