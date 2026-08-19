"""How big does an advantage have to be before selection can see it?

Two facts sat oddly together.  The ancestor, at 410 instructions per daughter,
is wiped out within two million instructions when placed beside evolved
replicators costing 216 and 239.  But those two, differing from each other by
10%, sit side by side for fifty million instructions without either displacing
the other -- the cheaper one takes 6% more births and no more ground.

So selection here is not a smooth function of replication cost.  This measures
where it bites: the ancestor against a series of descendants of known cost, each
competition seeded with equal numbers, interleaved, no mutation, and run until
either one wins or it is clear that neither will.

The result matters for reading everything else in this repository.  If a 10%
advantage is effectively invisible, then the tempo of optimization -- and Ray's
need for billions of instructions to get anywhere -- is not a puzzle but an
arithmetic consequence.

Run:  python3 experiments/selection.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import competition, describe
from soup.experiment import load_ancestor

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
BUDGET = 40_000_000
ANCESTOR_COST = 410
# Optional: a budget in instructions, then a maximum advantage to test, so that
# the near-neutral contests can be re-run for ten times as long without
# repeating the ones that were already decisive.
#   python3 experiments/selection.py 400000000 0.03


def candidates() -> list[tuple[int, int, str, bytes]]:
    """One replicator per distinct cost, gathered from every saved run."""
    best: dict[int, tuple[int, int, str, bytes]] = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        try:
            with open(path) as fh:
                r = json.load(fh)
        except Exception:
            continue
        if "census" not in r or "genomes" not in r:
            continue
        for row in r["census"]:
            if row.get("kind") != "replicator" or not row.get("cost"):
                continue
            cost = row["cost"]
            if cost not in best and cost < ANCESTOR_COST:
                best[cost] = (cost, row["size"], row["genotype"],
                              bytes(r["genomes"][row["genotype"]]))
    return sorted(best.values())


def main() -> None:
    global BUDGET
    if len(sys.argv) > 1:
        BUDGET = int(sys.argv[1])
    max_advantage = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    ancestor = bytes(load_ancestor())
    assert describe(ancestor)["cost"] == ANCESTOR_COST
    picks = candidates()
    # Spread the sample across the range of costs rather than taking the first
    # dozen, which would all be within a few instructions of each other.
    step = max(1, len(picks) // 8)
    picks = picks[::step][:9]
    picks = [p for p in picks
             if (ANCESTOR_COST - p[0]) / ANCESTOR_COST <= max_advantage]

    header = (f"{'challenger':>10} {'cells':>6} {'cost':>6} {'advantage':>10} "
              f"{'final share':>12} {'births':>18} {'outcome':>12}")
    print(f"the ancestor is 64 cells at {ANCESTOR_COST} instructions per daughter; "
          f"{BUDGET:,} instructions per contest\n")
    print(header)
    print("-" * len(header))
    rows = []
    for cost, size, label, genome in picks:
        out = competition({"ancestor": ancestor, "challenger": genome},
                          budget=BUDGET)
        adv = (ANCESTOR_COST - cost) / ANCESTOR_COST
        share = out["share"]["challenger"]
        outcome = ("challenger sweeps" if share > 0.98 else
                   "ancestor sweeps" if share < 0.02 else "coexist")
        rows.append({"genotype": label, "size": size, "cost": cost,
                     "advantage": round(adv, 3), "share": share,
                     "births": out["births"], "outcome": outcome})
        print(f"{label:>10} {size:>6} {cost:>6} {adv:>9.1%} {share:>11.1%} "
              f"{str(out['births']):>18} {outcome:>12}")

    name = ("selection.json" if BUDGET == 40_000_000
            else f"selection-{BUDGET // 1_000_000}M.json")
    with open(os.path.join(RESULTS, name), "w") as fh:
        json.dump({"budget": BUDGET, "ancestor_cost": ANCESTOR_COST,
                   "rows": rows}, fh, indent=1)
    print(f"\nwrote {os.path.join(RESULTS, name)}")


if __name__ == "__main__":
    main()
