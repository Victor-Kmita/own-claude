"""How cheap a replicator gets, against how long the run was.

One table, gathered from every finished run in results/: the cheapest
self-sufficient replicator each one produced, what it cost per daughter, and
how many instructions per cell copied that works out to.  Runs are split by
whether instruction flaws were switched on, because that turns out to be the
single largest factor in how fast this world optimizes.

The ancestor is the baseline in every row: 64 cells, 410 instructions per
daughter, 6.41 per cell copied.

Run:  python3 experiments/optimization_curve.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
ANCESTOR = (64, 410, 6.41)


def rows() -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        try:
            with open(path) as fh:
                r = json.load(fh)
        except Exception:
            continue
        if "census" not in r or "config" not in r or "totals" not in r:
            continue
        if r["config"]["copy_mutation_rate"] == 0:
            continue
        best = None
        for row in r["census"]:
            if row.get("kind") == "replicator" and row.get("cost"):
                if best is None or row["cost"] < best["cost"]:
                    best = row
        if not best:
            continue
        out.append({
            "run": r["name"],
            "instructions": r["config"]["instructions"],
            "flaws": r["config"].get("flaw_period") or 0,
            "genotype": best["genotype"],
            "cells": best["size"],
            "cost": best["cost"],
            "per_cell": best.get("cost_per_cell"),
            "mean_length": r["history"][-1]["mean_size"],
            "generations": r["history"][-1].get("mean_generation", 0),
        })
    return out


def main() -> None:
    data = rows()
    if not data:
        sys.exit("no finished runs in " + RESULTS)
    for flaws_on in (False, True):
        group = [d for d in data if bool(d["flaws"]) == flaws_on]
        if not group:
            continue
        print(f"\n{'with instruction flaws' if flaws_on else 'no instruction flaws'}"
              f"   (ancestor: {ANCESTOR[0]} cells, {ANCESTOR[1]} instructions, "
              f"{ANCESTOR[2]} per cell)\n")
        header = (f"  {'run':<22}{'length':>9}{'cheapest':>10}{'cells':>7}"
                  f"{'per cell':>10}{'mean len':>10}{'gens':>8}")
        print(header)
        print("  " + "-" * (len(header) - 2))
        for d in sorted(group, key=lambda d: (d["instructions"], d["cost"])):
            print(f"  {d['run']:<22}{d['instructions']/1e6:>8.0f}M{d['cost']:>10}"
                  f"{d['cells']:>7}{str(d['per_cell']):>10}"
                  f"{d['mean_length']:>10.1f}{d['generations']:>8.0f}")
    with open(os.path.join(RESULTS, "optimization_curve.json"), "w") as fh:
        json.dump({"ancestor": {"cells": ANCESTOR[0], "cost": ANCESTOR[1],
                                "per_cell": ANCESTOR[2]}, "rows": data}, fh, indent=1)


if __name__ == "__main__":
    main()
