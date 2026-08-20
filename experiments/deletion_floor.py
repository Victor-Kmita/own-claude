"""Is the length a deep run stops at a floor, or just where it stopped?

Four of seven deep runs with flaws converged on a 27-cell replicator and none
went below it, which reads like a limit.  This checks whether it is one, by
asking three questions about the genomes one deletion away:

* **do they work?**  Delete each cell in turn and culture the result.
* **do they win?**   Put each working shorter variant against the exact champion
  it came from, twelve of each, background noise on.
* **are they flatter?**  Compare the fraction of each one's single-mutation
  neighbourhood that still replicates.

The answer in the README is that a cheaper 26-cell repeater exists one mutation
away, usually wins the head-to-head, and is produced by the soup every few
thousand births -- so the plateau is not a floor.

Run:  python3 experiments/deletion_floor.py [run-name ...]
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import competition, describe, robustness

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DEFAULT = ["flaw-3b-s5", "flaw-3b-s6", "flaw-10b-s10", "deep-flaw-s2"]
# A "replicator" that needs forty instructions per cell is one that stumbled
# into a division after wandering; the champions run at under seven.
SANE = 40


def champion(name: str) -> tuple[bytes, dict]:
    """The cheapest genome in a saved run's census that really replicates."""
    with open(os.path.join(RESULTS, f"{name}.json")) as fh:
        result = json.load(fh)
    best = None
    for row in result["census"]:
        genome = bytes(result["genomes"][row["genotype"]])
        what = describe(genome)
        if what["kind"] != "replicator":
            continue
        if best is None or what["cost"] < best[1]["cost"]:
            best = (genome, what)
    return best


def deletions(genome: bytes, budget: int = 50_000) -> list[tuple[int, bytes, dict]]:
    out = []
    for i in range(len(genome)):
        shorter = genome[:i] + genome[i + 1:]
        what = describe(shorter, budget=budget)
        if what["kind"] == "replicator" and what["cost"] < SANE * len(shorter):
            out.append((i, shorter, what))
    return out


def greedy(genome: bytes) -> None:
    """Keep deleting the cell that leaves the cheapest working replicator."""
    what = describe(genome)
    print(f"  start: {len(genome)} cells, {what['cost']} instructions, "
          f"repeats={what['repeats']}")
    while True:
        options = deletions(genome)
        if not options:
            break
        i, genome, what = min(options, key=lambda o: o[2]["cost"])
        print(f"  drop cell {i:2} -> {len(genome):2} cells, {what['cost']:3} "
              f"instructions, repeats={what['repeats']} "
              f"({len(options)} viable deletions here)")


def main(names: list[str]) -> None:
    wins = losses = 0
    flatter = 0
    pairs = 0
    for name in names:
        genome, what = champion(name)
        working = deletions(genome)
        repeaters = [(i, g, w) for i, g, w in working if w["repeats"]]
        print(f"\n{name}: {len(genome)} cells at {what['cost']} instructions; "
              f"{len(working)} of {len(genome)} single deletions still replicate, "
              f"{len(repeaters)} of those more than once")
        parent_flat = robustness(genome, budget=40_000)["fraction_viable"]
        for i, shorter, w in repeaters:
            out = competition({"parent": genome, "shorter": shorter},
                              budget=8_000_000, cosmic_period=2000)
            flat = robustness(shorter, budget=40_000)["fraction_viable"]
            final = out["final"]
            pairs += 1
            if out["winner"] == "parent":
                wins += 1
            else:
                losses += 1
            if flat < parent_flat:
                flatter += 1
            print(f"   delete {i:2}: {what['cost']}->{w['cost']} instructions, "
                  f"final {final.get('parent', 0):4} vs {final.get('shorter', 0):4}"
                  f"  ({out['winner']}), neighbourhood "
                  f"{parent_flat:.3f} -> {flat:.3f}")
    print(f"\n{pairs} pairs: the longer parent wins {wins}, the shorter variant "
          f"wins {losses}; the shorter one is less robust in {flatter}")
    print("\ngreedy deletion from the first champion:")
    greedy(champion(names[0])[0])


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
