"""Can a housekeeping policy be an evolutionary force?

Mutation in this world is supposed to come from two switches: copy errors and
cosmic rays.  Turn both off and the population should be a perfect monoculture
forever.  Whether it actually is depends on two decisions that look like
implementation detail and are not:

* **when the reaper runs.**  Every creature holding a daughter block occupies
  twice its own length, so a soup reaped only once per scheduler pass sits
  permanently full and ``mal`` fails routinely.  A reaper that also runs the
  moment an allocation fails keeps room available and ``mal`` essentially never
  fails.
* **whether errors hasten death.**  A creature that makes errors climbs the
  reaper queue.  This is the only thing in the world resembling quality control.

A failed ``mal`` is a mutagen, and the mechanism is exact (it is pinned by a
unit test):

1. no free gap is large enough, so ``mal`` fails;
2. it leaves ``ax`` holding what it already held -- the address of the
   creature's own END marker;
3. the copy loop runs anyway and writes there;
4. the START marker lands on top of the END marker, a write into its own
   genome, which is permitted;
5. the creature can no longer measure itself: ``adrf`` now finds the *next*
   creature's END marker, it computes twice its true length, and its daughters
   come out double-length.

This sweep crosses the two policies with soup size, with both mutation switches
off throughout.  Any genotype beyond the first is therefore evidence that the
mutagen reached the population.

Run:  python3 experiments/fragmentation.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.experiment import load_ancestor, sample
from soup.vm import run_slice
from soup.world import World

SIZES = [2_000, 4_000, 8_000, 16_000, 60_000]
BUDGET = 5_000_000
DEEP_SOUP = 4_000        # the size where the effect was clearest
DEEP_BUDGET = 20_000_000


def demonstrate_mechanism() -> str:
    """One creature, a soup with no room to allocate: watch it damage itself."""
    from soup.isa import OPCODE

    code = load_ancestor()
    w = World(soup_size=len(code) + 40, copy_mutation_rate=0.0,
              cosmic_period=10 ** 18, filler=OPCODE["zero"])
    cr = w.inject(code, address=0)
    before = list(w.read_genome(60, 4))
    run_slice(w, cr, 40)          # self-inspection, then the failing mal
    run_slice(w, cr, 40)          # the copy loop, aimed at itself
    after = list(w.read_genome(60, 4))
    return (f"END marker before: {before}   after one failed mal: {after}   "
            f"errors: {cr.stats.errors}")


def trial(soup_size: int, lazy: bool, errors_kill: bool) -> dict:
    code = load_ancestor()
    w = World(soup_size=soup_size, seed=1, copy_mutation_rate=0.0,
              cosmic_period=10 ** 18, reap_on_alloc_failure=not lazy,
              errors_hasten_death=errors_kill)
    w.inject(code, address=0)
    while w.clock < BUDGET and not w.extinct:
        w.step_generation()
    snap = sample(w)
    return {
        "soup_size": soup_size,
        "reaper": "lazy" if lazy else "on demand",
        "errors_hasten_death": errors_kill,
        "capacity": soup_size // len(code),
        "alive": snap["alive"],
        "births": w.births,
        "alloc_failures": w.alloc_failures,
        "alloc_failures_per_birth": round(w.alloc_failures / max(1, w.births), 3),
        "genotypes_seen": len(w.genebank.genome),
        "mean_size": snap["mean_size"],
        "max_size": snap["max_size"],
    }


def main() -> None:
    print("Mechanism, one creature, no room to allocate:")
    print("  " + demonstrate_mechanism())
    print(f"\nSweep: {BUDGET:,} instructions per cell, mutation off throughout.\n")
    rows = []
    header = (f"{'reaper':>10} {'errors kill':>12} {'soup':>7} {'alive':>6} "
              f"{'births':>8} {'mal fails':>10} {'per birth':>10} {'genotypes':>10} "
              f"{'mean size':>10}")
    print(header)
    print("-" * len(header))
    for lazy in (False, True):
        for errors_kill in (True, False):
            for n in SIZES:
                r = trial(n, lazy, errors_kill)
                rows.append(r)
                print(f"{r['reaper']:>10} {str(r['errors_hasten_death']):>12} "
                      f"{r['soup_size']:>7} {r['alive']:>6} {r['births']:>8} "
                      f"{r['alloc_failures']:>10} {r['alloc_failures_per_birth']:>10.2f} "
                      f"{r['genotypes_seen']:>10} {r['mean_size']:>10.1f}")
    print(f"\nDeeper look: soup of {DEEP_SOUP:,} cells, {DEEP_BUDGET:,} "
          f"instructions, still no mutation.\n")
    deep = []
    print(f"{'reaper':>10} {'errors kill':>12} {'mal fails':>10} {'genotypes':>10} "
          f"{'mean size':>10} {'max size':>9}")
    global BUDGET
    BUDGET = DEEP_BUDGET
    for lazy in (False, True):
        for errors_kill in (True, False):
            r = trial(DEEP_SOUP, lazy, errors_kill)
            deep.append(r)
            print(f"{r['reaper']:>10} {str(r['errors_hasten_death']):>12} "
                  f"{r['alloc_failures']:>10} {r['genotypes_seen']:>10} "
                  f"{r['mean_size']:>10.1f} {r['max_size']:>9}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results",
                       "fragmentation.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"budget": BUDGET, "mutation": "off",
                   "mechanism": demonstrate_mechanism(), "rows": rows,
                   "deep": {"soup_size": DEEP_SOUP, "budget": DEEP_BUDGET,
                            "rows": deep}}, fh, indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
