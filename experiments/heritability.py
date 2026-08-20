"""How much of a mutation event actually reaches the daughter?

The 18 runs of finding 16 killed a prediction I had made from a ledger of
*events per replication*: copy errors, cosmic rays and instruction flaws all
counted as one event each, and the error threshold was supposed to fall wherever
their sum crossed one.  It does not.  Two conditions with the same predicted
load behaved completely differently, and the one with the most flaws was the
healthiest of the lot.

This measures the exchange rate the ledger was missing.  One ancestor, alone in
a small soup, one mutation source switched on at a time; run until it produces
its first daughter, then ask two questions:

* how many mutation *events* did the mother experience?
* did the daughter come out different from the mother, and by how many cells?

The ratio of the two is what one event is worth.  A copy error is worth close to
one substitution by construction -- it *is* a substitution in the daughter.  A
flaw is worth much less: most flaws land on an instruction whose result nobody
reads, or nudge a register that is about to be reloaded anyway.

Run:  python3 experiments/heritability.py
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import describe
from soup.experiment import load_ancestor
from soup.world import World

TRIALS = 400
SOUP = 4_000
BUDGET = 40_000        # one replication costs 410; this is room to spare
ASSAY = 20_000         # a working replicator divides twice inside 900


def one_replication(seed: int, **params) -> tuple | None:
    """Run one mother to her first daughter.

    Returns (copy_errors, flaws, cells_changed, size_shift, daughter_genome),
    or None if she never managed to divide inside the budget.
    """
    code = load_ancestor()
    w = World(soup_size=SOUP, seed=seed, **params)
    # The flaw clock starts at a full period, so a creature measured over its
    # very first replication would either never be hit (period above 410) or be
    # hit at exactly the same instruction every time.  Start it at a uniformly
    # random phase instead, which is the steady state a creature in a running
    # soup actually sees.  Drawn from a separate stream so the world's own
    # sequence is untouched.
    if w.flaw_period:
        w.flaw_countdown = random.Random(seed).randrange(1, w.flaw_period + 1)
    w.inject(code, address=0)
    mother = w.creatures[0]
    while w.clock < BUDGET and not w.extinct and mother.stats.births == 0:
        w.step_generation()
    if mother.stats.births == 0:
        return None
    daughters = [c for c in w.creatures if c is not mother]
    if not daughters:
        return None
    d = daughters[0]
    child = bytes(w.soup[(d.start + i) % w.soup_size] for i in range(d.size))
    # The mother's own genome may have been hit too; compare against what she
    # is now, not against the ancestor, because that is what she was copying.
    now = bytes(w.soup[(mother.start + i) % w.soup_size] for i in range(mother.size))
    n = min(len(child), len(now))
    changed = sum(1 for i in range(n) if child[i] != now[i]) + abs(len(child) - len(now))
    return (mother.stats.copy_errors, mother.stats.flaws, changed,
            d.size - mother.size, child)


CONDITIONS = [
    ("nothing",            dict(copy_mutation_rate=0.0, cosmic_period=10 ** 9, flaw_period=0)),
    ("copy 1/1000",        dict(copy_mutation_rate=1 / 1000, cosmic_period=10 ** 9, flaw_period=0)),
    ("copy 1/125",         dict(copy_mutation_rate=1 / 125, cosmic_period=10 ** 9, flaw_period=0)),
    ("copy 1/83",          dict(copy_mutation_rate=1 / 83, cosmic_period=10 ** 9, flaw_period=0)),
    ("flaws 1/2000",       dict(copy_mutation_rate=0.0, cosmic_period=10 ** 9, flaw_period=2000)),
    ("flaws 1/1000",       dict(copy_mutation_rate=0.0, cosmic_period=10 ** 9, flaw_period=1000)),
    ("flaws 1/500",        dict(copy_mutation_rate=0.0, cosmic_period=10 ** 9, flaw_period=500)),
    ("flaws 1/250",        dict(copy_mutation_rate=0.0, cosmic_period=10 ** 9, flaw_period=250)),
]


def main() -> None:
    print(f"{TRIALS} replications per condition, one mother alone, "
          f"one mutation source at a time\n")
    print(f"{'condition':16} {'divided':>8} {'events/rep':>11} {'differ':>8} "
          f"{'per event':>10} {'cells changed':>14} {'size shift':>11} "
          f"{'still works':>13}")
    for label, params in CONDITIONS:
        rows = [one_replication(s, **params) for s in range(1, TRIALS + 1)]
        ok = [r for r in rows if r is not None]
        if not ok:
            print(f"{label:16} {0:>8}")
            continue
        events = sum(c + f for c, f, _, _, _ in ok) / len(ok)
        differing = sum(1 for _, _, ch, _, _ in ok if ch) / len(ok)
        # Cells changed and size shift are averaged over the daughters that
        # actually came out different; averaged over all of them they would
        # just restate the previous column.
        hit = [(ch, dz, g) for _, _, ch, dz, g in ok if ch]
        cells = sum(ch for ch, _, _ in hit) / len(hit) if hit else 0.0
        shift = sum(abs(dz) for _, dz, _ in hit) / len(hit) if hit else 0.0
        # The column that matters: of the daughters that came out different,
        # how many can still reproduce?  A mutation that is lethal on arrival
        # costs the population a birth; one that is viable costs it fidelity,
        # and only the second kind accumulates down a lineage.
        alive = (sum(1 for _, _, g in hit
                     if describe(g, budget=ASSAY)["kind"] == "replicator")
                 / len(hit)) if hit else 0.0
        per = differing / events if events else 0.0
        print(f"{label:16} {len(ok):>4}/{TRIALS:<3} {events:>11.3f} {differing:>7.0%} "
              f"{per:>10.2f} {cells:>14.1f} {shift:>11.1f} {alive:>13.0%}")


if __name__ == "__main__":
    main()
