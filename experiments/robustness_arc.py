"""Does evolution here buy robustness, or spend it?

Three things could be under selection in this world: replication cost, genome
length, and mutational robustness -- how much of the space around a genome is
still habitable.  The first two are easy to read off a census.  The third takes
a measurement: flip every bit of every cell in turn and culture each mutant
alone.

This walks the champions of runs of increasing length -- the cheapest
self-sufficient replicator each one produced -- and asks what happened to their
neighbourhoods along the way.

Run:  python3 experiments/robustness_arc.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import robustness
from soup.experiment import load_ancestor

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RUNS = ["baseline-s1", "long-constant-s1", "mut-k8-s3",
        "deep-constant-s1", "deep-constant-s2"]


def champion(name: str):
    path = os.path.join(RESULTS, name + ".json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        r = json.load(fh)
    reps = [c for c in r["census"] if c.get("cost")]
    if not reps:
        return None
    best = min(reps, key=lambda c: c["cost"])
    return (best["genotype"], bytes(r["genomes"][best["genotype"]]),
            r["config"]["instructions"])


def main() -> None:
    picks = [("ancestor", bytes(load_ancestor()), 0)]
    for name in RUNS:
        c = champion(name)
        if c:
            picks.append((f"{c[0]} ({name})", c[1], c[2]))

    header = (f"{'champion':>32} {'run':>7} {'cells':>6} {'cost':>6} "
              f"{'viable':>7} {'neutral':>8} {'within 10%':>11} "
              f"{'median':>7} {'mean':>8}")
    print(header)
    print("-" * len(header))
    rows = []
    for name, genome, length in picks:
        r = robustness(genome)
        rows.append({"champion": name, "instructions": length, **r})
        print(f"{name:>32} {length/1e6:>6.0f}M {r['cells']:>6} "
              f"{str(r['parent_cost']):>6} {r['fraction_viable']:>7.0%} "
              f"{r['fraction_neutral']:>8.0%} {r['fraction_within_10pc']:>11.0%} "
              f"{str(r['median_cost_of_survivors']):>7} "
              f"{str(r['mean_cost_of_survivors']):>8}")

    with open(os.path.join(RESULTS, "robustness_arc.json"), "w") as fh:
        json.dump({"rows": rows}, fh, indent=1)
    print(f"\nwrote {os.path.join(RESULTS, 'robustness_arc.json')}")


if __name__ == "__main__":
    main()
