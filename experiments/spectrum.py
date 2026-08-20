"""What kinds of daughter can this world's mutations actually produce?

Finding 13 says flaws are what gives this world insertions and deletions, and
finding 17 needed to know how often a *clean interior deletion* happens, because
the 26-cell genomes that beat their 27-cell parents are all interior deletions.
So: one mother alone, one mutation source at a time, classify every daughter
against the mother that produced her.

Run:  python3 experiments/spectrum.py
"""

from __future__ import annotations

import collections
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.experiment import load_ancestor
from soup.world import World

TRIALS = 1500
SOUP = 4_000
BUDGET = 40_000


def one_pair(seed: int, **params) -> tuple[bytes, bytes] | None:
    """A mother and her first daughter, as they stand at the moment of birth."""
    world = World(soup_size=SOUP, seed=seed, **params)
    if world.flaw_period:
        # Start the flaw clock at a random phase; see heritability.py.
        world.flaw_countdown = random.Random(seed).randrange(1, world.flaw_period + 1)
    world.inject(load_ancestor(), address=0)
    mother = world.creatures[0]
    while world.clock < BUDGET and not world.extinct and mother.stats.births == 0:
        world.step_generation()
    if mother.stats.births == 0:
        return None
    kids = [c for c in world.creatures if c is not mother]
    if not kids:
        return None
    def read(cr):
        return bytes(world.soup[(cr.start + i) % world.soup_size] for i in range(cr.size))
    return read(mother), read(kids[0])


def classify(mother: bytes, child: bytes) -> str:
    if child == mother:
        return "identical"
    if len(child) == len(mother):
        n = sum(1 for a, b in zip(mother, child) if a != b)
        return ("same length, one cell changed" if n == 1
                else "same length, many cells changed")
    if len(child) < len(mother):
        if child == mother[:len(child)]:
            return "shorter: the tail is gone"
        for i in range(len(mother)):
            if mother[:i] + mother[i + 1:] == child:
                return "shorter: one cell deleted from the middle"
        return "shorter: something else"
    if child[:len(mother)] == mother:
        return "longer: mother plus a tail"
    return "longer: something else"


CONDITIONS = [
    ("flaws, one in 250", dict(copy_mutation_rate=0.0, cosmic_period=10 ** 9, flaw_period=250)),
    ("copy errors, one in 83", dict(copy_mutation_rate=1 / 83, cosmic_period=10 ** 9, flaw_period=0)),
    ("cosmic rays, one in 200", dict(copy_mutation_rate=0.0, cosmic_period=200, flaw_period=0)),
]


def main() -> None:
    for label, params in CONDITIONS:
        pairs = [p for p in (one_pair(s, **params) for s in range(1, TRIALS + 1)) if p]
        counts = collections.Counter(classify(m, c) for m, c in pairs)
        print(f"\n{label}  ({len(pairs)} daughters)")
        for kind, n in counts.most_common():
            print(f"   {n:5}  {n / len(pairs):6.1%}  {kind}")


if __name__ == "__main__":
    main()
