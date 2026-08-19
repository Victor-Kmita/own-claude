"""Recompute the census classification of saved runs.

The genomes of every genotype in a run's census are stored in its result file,
so when the classifier changes there is no need to spend an hour re-running the
simulations: the assays can simply be redone against the saved genomes.  The
histories, which are what the runs are actually for, are untouched.

Run:  python3 experiments/reclassify.py [results/*.json]
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import describe

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def reclassify(path: str) -> None:
    with open(path) as fh:
        result = json.load(fh)
    if "census" not in result or "genomes" not in result:
        return
    changed = []
    for row in result["census"]:
        genome = bytes(result["genomes"][row["genotype"]])
        what = describe(genome, budget=400_000)
        if what["kind"] != row.get("kind") or what["cost"] != row.get("cost"):
            changed.append((row["genotype"], row.get("kind"), row.get("cost"),
                            what["kind"], what["cost"]))
        row.update(what)
    result["classifier"] = "exact-copy"
    with open(path, "w") as fh:
        json.dump(result, fh, indent=1)
    name = os.path.basename(path)
    if changed:
        print(f"{name}: {len(changed)} of {len(result['census'])} changed")
        for label, was, was_cost, now, now_cost in changed:
            print(f"    {label}  {was}({was_cost}) -> {now}({now_cost})")
    else:
        print(f"{name}: unchanged")


def main() -> None:
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(RESULTS, "*.json")))
    for path in paths:
        if os.path.basename(path) in ("fragmentation.json", "viability.json"):
            continue
        reclassify(path)


if __name__ == "__main__":
    main()
