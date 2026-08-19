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

    for k copy cosmic in (0.25 4000 8000) (0.5 2000 4000) (1 1000 2000) \\
                         (2 500 1000) (4 250 500) (8 125 250) (16 63 125) (32 31 63):
        for seed in 1 2 3:
            python3 -m soup run mut-k$k-s$seed --instructions 60000000 \\
                    --seed $seed --copy-mutation $copy --cosmic $cosmic \\
                    --sample-every 3000000

Three seeds per rate is not a luxury.  A single run's ecology varies so much
between seeds -- one fills with parasites, the next stays almost free of them --
that one run per condition cannot support any claim about ecology at all.

Run:  python3 experiments/mutation_rate.py
"""

from __future__ import annotations

import glob
import json
import os
import re
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load() -> dict[float, list[dict]]:
    runs: dict[float, list[dict]] = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "mut-k*.json"))):
        name = os.path.basename(path)
        m = re.match(r"mut-k([\d.]+)-s(\d+)\.json", name)
        if not m:
            continue
        with open(path) as fh:
            runs.setdefault(float(m.group(1)), []).append(json.load(fh))
    return runs


def digest(run: dict) -> dict:
    h = run["history"]
    tail = h[len(h) * 7 // 10:]
    costs = [c["cost"] for c in run["census"] if c.get("cost")]
    return {
        "seed": run["config"]["seed"],
        "best_cost": min(costs) if costs else None,
        "mean_len": round(st.mean(x["mean_size"] for x in tail), 1),
        "diversity": round(st.mean(x["diversity"] for x in tail), 2),
        "foreign": round(st.mean(x["foreign_breeder_share"] for x in tail), 2),
        "types_seen": run["totals"]["genotypes_seen"],
        "alive": h[-1]["alive"],
        "generations": h[-1].get("mean_generation", 0),
        "extinct": run["extinct"],
    }


def main() -> None:
    groups = load()
    if not groups:
        sys.exit("no mut-k*-s*.json in " + RESULTS + " -- see the docstring")
    header = (f"{'k':>6} {'copy err':>9} {'mu/genome':>10} {'generations':>18} "
              f"{'best cost':>26} {'mean length':>22} {'foreign breeders':>22} "
              f"{'alive':>20}")
    print(header)
    print("-" * len(header))
    out = []
    for k in sorted(groups):
        ds = sorted((digest(r) for r in groups[k]), key=lambda d: d["seed"])
        copy = round(1 / groups[k][0]["config"]["copy_mutation_rate"])
        fmt = lambda key: str([d[key] for d in ds])
        # Mutations per genome per replication -- the unit quasispecies theory
        # is stated in.  The classic error threshold sits at about one.
        mu = round(groups[k][0]["config"]["copy_mutation_rate"] * 64, 3)
        print(f"{k:>6} {copy:>9} {mu:>10} {fmt('generations'):>18} "
              f"{fmt('best_cost'):>26} {fmt('mean_len'):>22} "
              f"{fmt('foreign'):>22} {fmt('alive'):>20}")
        out.append({"k": k, "copy_error_per": copy,
                    "mutations_per_genome_per_replication": mu, "runs": ds,
                    "best_cost": min([d["best_cost"] for d in ds
                                      if d["best_cost"]], default=None),
                    "mean_foreign": round(st.mean(d["foreign"] for d in ds), 2),
                    "mean_diversity": round(st.mean(d["diversity"] for d in ds), 2),
                    "mean_generations": round(st.mean(d["generations"] for d in ds)),
                    "extinctions": sum(1 for d in ds if d["extinct"])})

    print("\n(each cell lists the three seeds; the ancestor replicates in 410)")
    best = min((r for r in out if r["best_cost"]), key=lambda r: r["best_cost"])
    richest = max(out, key=lambda r: r["mean_foreign"])
    print(f"\ncheapest replicator anywhere: {best['best_cost']} instructions, "
          f"at k={best['k']}")
    print(f"most parasitic ecology on average: k={richest['k']} "
          f"({richest['mean_foreign']:.0%} of breeders running foreign code)")
    print("extinctions: " +
          (", ".join(f"k={r['k']}: {r['extinctions']}/3" for r in out
                     if r["extinctions"]) or "none at any rate tested"))
    print("\nGeneration depth is the thing to watch at the top of the sweep: a "
          "population\nthat cannot pass its information on shows shallow "
          "lineages long before it dies out.")
    print("generations reached: " +
          ", ".join(f"k={r['k']}: {r['mean_generations']}" for r in out))
    with open(os.path.join(RESULTS, "mutation_rate.json"), "w") as fh:
        json.dump({"rates": out}, fh, indent=1)


if __name__ == "__main__":
    main()
