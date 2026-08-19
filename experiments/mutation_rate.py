"""How does the mutation rate change what evolves?

Ray reports two things about Tierra that are worth checking here, because they
pull in opposite directions:

* "optimization of the algorithm is maximized at the highest mutation rate that
  does not cause instability";
* "ecological interactions appear to be richer at slightly lower mutation
  rates".

Quasispecies theory adds a third expectation: above some critical rate the
population can no longer hold onto its information and melts (the error
threshold).  Digital-organism work has tested this directly and found the
critical rate to sit *above* the theoretical error threshold.

The sweep multiplies both of this world's mutation rates by the same factor k,
so k=1 is the standard setting (one copy error per 1,000 cells copied, one
cosmic ray per 2,000 instructions) and k=8 is eight times that.

The runs are produced by the CLI, one per rate, and this script summarises
their saved histories:

    for k, copy, cosmic in (0.25 4000 8000) (0.5 2000 4000) (1 1000 2000) \\
                           (2 500 1000) (4 250 500) (8 125 250):
        python3 -m soup run mut-k$k --instructions 60000000 --seed 1 \\
                --copy-mutation $copy --cosmic $cosmic --sample-every 3000000

Run:  python3 experiments/mutation_rate.py
"""

from __future__ import annotations

import glob
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load() -> list[dict]:
    runs = []
    for path in sorted(glob.glob(os.path.join(RESULTS, "mut-k*.json")),
                       key=lambda p: float(os.path.basename(p)[5:-5])):
        with open(path) as fh:
            runs.append(json.load(fh))
    return runs


def main() -> None:
    runs = load()
    if not runs:
        sys.exit("no mut-k*.json in " + RESULTS + " -- see the docstring")
    header = (f"{'k':>5} {'copy err':>9} {'cosmic':>8} {'alive':>6} {'gens':>6} "
              f"{'types seen':>11} {'H':>6} {'mean len':>9} {'best cost':>10} "
              f"{'at len':>7} {'foreign breeders':>17}")
    print(header)
    print("-" * len(header))
    rows = []
    for r in runs:
        k = float(r["name"].split("k")[1])
        h = r["history"]
        tail = h[len(h) * 7 // 10:]
        costs = [(c["cost"], c["size"]) for c in r["census"] if c.get("cost")]
        best = min(costs) if costs else (None, None)
        row = {
            "k": k,
            "copy": round(1 / r["config"]["copy_mutation_rate"]),
            "cosmic": r["config"]["cosmic_period"],
            "alive": h[-1]["alive"],
            "generations": h[-1].get("mean_generation", 0),
            "types_seen": r["totals"]["genotypes_seen"],
            "diversity": round(st.mean(x["diversity"] for x in tail), 2),
            "mean_len": round(st.mean(x["mean_size"] for x in tail), 1),
            "best_cost": best[0],
            "best_len": best[1],
            "foreign": round(st.mean(x["foreign_breeder_share"] for x in tail), 2),
            "extinct": r["extinct"],
        }
        rows.append(row)
        print(f"{row['k']:>5} {row['copy']:>9} {row['cosmic']:>8} {row['alive']:>6} "
              f"{row['generations']:>6.0f} {row['types_seen']:>11} "
              f"{row['diversity']:>6.2f} {row['mean_len']:>9.1f} "
              f"{str(row['best_cost']):>10} {str(row['best_len']):>7} "
              f"{row['foreign']:>17.2f}")

    best = min((r for r in rows if r["best_cost"]), key=lambda r: r["best_cost"])
    richest = max(rows, key=lambda r: r["foreign"])
    print(f"\ncheapest replicator found at k={best['k']} "
          f"({best['best_cost']} instructions, {best['best_len']} cells; "
          f"the ancestor needs 410)")
    print(f"richest ecology (most reproducing creatures running foreign code) "
          f"at k={richest['k']} ({richest['foreign']:.0%})")
    with open(os.path.join(RESULTS, "mutation_rate.json"), "w") as fh:
        json.dump({"rows": rows}, fh, indent=1)


if __name__ == "__main__":
    main()
