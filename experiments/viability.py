"""What fraction of the variants a soup throws off can actually reproduce?

The census in a run only ever shows the winners.  This asks the other question:
take the whole gene bank -- every distinct genome that appeared, most of them
once -- and culture a random sample of them properly.

Two samples, because they answer different things:

* **uniform over genotypes** -- of all the distinct variants evolution tried,
  what fraction work?  This is the shape of the mutational landscape.
* **weighted by births** -- of all the reproduction events that happened, what
  fraction produced something viable?  This is what the population experiences.

Run:  python3 experiments/viability.py
"""

from __future__ import annotations

import json
import os
import random
import statistics as st
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import describe
from soup.experiment import load_ancestor
from soup.world import World

BUDGET = 20_000_000
ANCESTOR_COST = 410      # measured, not assumed; see the assertion in main()
SAMPLE = 150
ASSAY_BUDGET = 200_000


def grow() -> World:
    w = World(soup_size=60_000, seed=1, copy_mutation_rate=1 / 1000,
              cosmic_period=2000)
    w.inject(load_ancestor(), address=0)
    while w.clock < BUDGET and not w.extinct:
        w.step_generation()
    return w


def survey(w: World, labels: list[str]) -> dict:
    kinds = Counter()
    costs = []
    cheapest = None
    for label in labels:
        genome = w.genebank.genome[label]
        what = describe(genome, budget=ASSAY_BUDGET)
        kinds[what["kind"]] += 1
        if what["cost"]:
            costs.append((what["cost"], label, len(genome)))
            if cheapest is None or what["cost"] < cheapest[0]:
                cheapest = (what["cost"], label, len(genome))
    return {"kinds": kinds, "costs": costs, "cheapest": cheapest}


def main() -> None:
    measured = describe(bytes(load_ancestor()), budget=ASSAY_BUDGET)
    assert measured["cost"] == ANCESTOR_COST, measured
    w = grow()
    rng = random.Random(7)
    labels = list(w.genebank.genome)
    print(f"{w.clock:,} instructions, {w.births:,} births, "
          f"{len(labels):,} distinct genotypes seen\n")

    uniform = rng.sample(labels, min(SAMPLE, len(labels)))
    weights = [w.genebank.births[l] for l in labels]
    weighted = rng.choices(labels, weights=weights, k=SAMPLE)

    out = {}
    for name, sample in (("uniform over genotypes", uniform),
                         ("weighted by births", weighted)):
        result = survey(w, sample)
        total = sum(result["kinds"].values())
        print(f"{name}  (n={total})")
        for kind, n in result["kinds"].most_common():
            print(f"    {kind:<15} {n:>4}  {n / total:6.1%}")
        if result["costs"]:
            costs = [c for c, _, _ in result["costs"]]
            print(f"    replication cost: min {min(costs)}, median "
                  f"{int(st.median(costs))}, max {max(costs)}   "
                  f"(the ancestor needs {ANCESTOR_COST})")
            print(f"    cheapest: {result['cheapest'][1]} at "
                  f"{result['cheapest'][0]} instructions, "
                  f"{result['cheapest'][2]} cells")
        print()
        out[name] = {
            "kinds": dict(result["kinds"]),
            "costs": [[c, l, n] for c, l, n in result["costs"]],
            "cheapest": result["cheapest"],
        }

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results",
                        "viability.json")
    with open(path, "w") as fh:
        json.dump({"instructions": BUDGET, "sample": SAMPLE,
                   "assay_budget": ASSAY_BUDGET,
                   "genotypes_seen": len(labels), "births": w.births,
                   "samples": out}, fh, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
