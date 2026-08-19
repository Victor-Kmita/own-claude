"""Does memory fragmentation act as a mutagen?

Mutation in this world is supposed to come from two switches: copy errors and
cosmic rays.  Turn both off and the population is a perfect monoculture forever
-- in a large soup.  In a small one it is not, and the reason is that ``mal``
can fail.  When it does, the ancestor's registers are left holding the address
of its own END marker, and the copy loop that follows writes the START marker
over it.  The creature loses the ability to measure itself and its descendants
come out double length.

This sweep measures the effect: same seed, same everything, mutation fully off,
soup size varied.  If fragmentation is the mutagen, then allocation failures and
genotype counts should both rise as the soup gets smaller, together.

Run:  python3 experiments/fragmentation.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.experiment import load_ancestor, sample
from soup.world import World

SIZES = [1_000, 2_000, 4_000, 8_000, 16_000, 32_000, 60_000]
BUDGET = 5_000_000


def trial(soup_size: int) -> dict:
    code = load_ancestor()
    w = World(soup_size=soup_size, seed=1, copy_mutation_rate=0.0,
              cosmic_period=10 ** 18)
    w.inject(code, address=0)
    while w.clock < BUDGET and not w.extinct:
        w.step_generation()
    snap = sample(w)
    return {
        "soup_size": soup_size,
        "capacity": soup_size // len(code),
        "alive": snap["alive"],
        "genotypes_seen": len(w.genebank.genome),
        "genotypes_alive": snap["genotypes"],
        "alloc_failures": w.alloc_failures,
        "alloc_failures_per_birth": round(w.alloc_failures / max(1, w.births), 3),
        "births": w.births,
        "mean_size": snap["mean_size"],
        "max_size": snap["max_size"],
        "extinct": w.extinct,
    }


def main() -> None:
    rows = [trial(n) for n in SIZES]
    header = (f"{'soup':>7} {'capacity':>9} {'alive':>6} {'births':>8} "
              f"{'mal fails':>10} {'per birth':>10} {'genotypes':>10} {'mean size':>10}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['soup_size']:>7} {r['capacity']:>9} {r['alive']:>6} {r['births']:>8} "
              f"{r['alloc_failures']:>10} {r['alloc_failures_per_birth']:>10.2f} "
              f"{r['genotypes_seen']:>10} {r['mean_size']:>10.1f}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results",
                       "fragmentation.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"budget": BUDGET, "mutation": "off", "rows": rows}, fh, indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
