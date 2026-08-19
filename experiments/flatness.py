"""Fast and fragile, or slow and forgiving: which wins depends on the noise.

Two replicators came out of the three-billion-instruction runs.  One compressed
the ancestor to 37 cells and kept its copy loop, replicating in 239
instructions.  The other unrolled the loop to copy two cells per pass and
replicates in 216 -- 10% cheaper, and by every measure in this repository the
better organism.

Put them together and the cheaper one does not win.  With mutation switched off
they sit in fixed proportions forever, which turns out to be an artifact: a
world with no noise is deterministic and finite, so it must fall into a
periodic orbit.  Add a trickle of noise and the *more expensive* one drives the
cheaper to extinction.

The reason is visible in their neighbourhoods.  Flip every bit of every cell in
turn and culture each mutant alone:

* the compressed replicator's surviving mutants cost 239 instructions on
  average -- the same as their parent.  It sits on a plateau.
* the unrolled replicator's surviving mutants cost 5,109 on average.  It sits on
  a spike.

Under mutation the spike keeps producing crippled children that burn CPU, and
that costs more than the 10% its speed saves.  This is survival of the
flattest (Wilke, Wang, Ofria, Lenski & Adami, Nature 2001) turning up in a
system built without it in mind, and it explains something in this repository's
own results: unrolling appeared in one of two deep runs and never spread.

Run:  python3 experiments/flatness.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import competition, robustness
from soup.experiment import load_ancestor

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
FLAT = "0037vvz"       # 37 cells, 239 instructions, the ancestor's copy loop
SHARP = "0038rdr"      # 38 cells, 216 instructions, an unrolled copy loop
# Noise levels, as one cosmic ray per N instructions executed.  None means no
# mutation at all -- included because a noiseless world is deterministic and
# finite, so it falls into a periodic orbit and neither genotype can win.
NOISE = (None, 20_000_000, 5_000_000, 2_000_000, 800_000, 200_000, 20_000, 2_000)
REPLICATED = (5_000_000, 2_000_000, 800_000, 200_000)   # three seeds at these
BUDGET = 60_000_000


def find(label: str) -> bytes:
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        try:
            with open(path) as fh:
                r = json.load(fh)
        except Exception:
            continue
        if label in r.get("genomes", {}):
            return bytes(r["genomes"][label])
    sys.exit(f"{label} is not in any saved result; run the deep experiments first")


def main() -> None:
    flat, sharp = find(FLAT), find(SHARP)
    print("Mutational neighbourhoods -- every single-bit mutant, cultured alone:\n")
    rows = {}
    for name, genome in (("flat " + FLAT, flat), ("sharp " + SHARP, sharp),
                         ("ancestor", bytes(load_ancestor()))):
        r = robustness(genome)
        rows[name] = r
        print(f"  {name:<16} {r['cells']:>3} cells, costs {r['parent_cost']:>4}: "
              f"{r['fraction_viable']:.0%} of mutants still replicate, "
              f"{r['fraction_neutral']:.0%} are unchanged in cost, "
              f"and the survivors average {r['mean_cost_of_survivors']}")

    print(f"\nCompetition, twelve of each, {BUDGET:,} instructions.  Counted by\n"
          f"lineage -- descendants of each seeded creature -- because the exact\n"
          f"genotypes dissolve within a few million instructions once noise is on.\n"
          f"The last two columns are what the survivors have become.\n")
    print(f"  {'cosmic ray every':>18} {'seed':>5} {'flat':>7} {'sharp':>7} "
          f"{'flat /cell':>11} {'sharp /cell':>12}")
    gradient = []
    for cosmic in NOISE:
        for seed in ((1, 2, 3) if cosmic in REPLICATED else (1,)):
            out = competition({"flat": flat, "sharp": sharp}, budget=BUDGET,
                              samples=3, cosmic_period=cosmic, profile_each=8,
                              seed=seed)
            surv = out["survivors"]
            gradient.append({"cosmic_period": cosmic, "seed": seed,
                             **out["final"], "winner": out["winner"],
                             "births": out["births"],
                             "flat_survivors": surv["flat"],
                             "sharp_survivors": surv["sharp"]})
            print(f"  {(cosmic or 0):>18,} {seed:>5} {out['final']['flat']:>7} "
                  f"{out['final']['sharp']:>7} "
                  f"{str(surv['flat'].get('mean_cost_per_cell')):>11} "
                  f"{str(surv['sharp'].get('mean_cost_per_cell')):>12}")

    print("\nWith no noise the two sit in a periodic orbit and neither wins.  From\n"
          "one ray per five million instructions down to one per two hundred\n"
          "thousand, the flatter and slower lineage wins, and at the bottom of that\n"
          "window the faster one goes extinct in every seed.  Below 200,000 the\n"
          "comparison stops being about the innovation: lineages persist as clouds\n"
          "of damaged creatures, and the cost per cell of the survivors says so.")

    with open(os.path.join(RESULTS, "flatness.json"), "w") as fh:
        json.dump({"budget": BUDGET, "robustness": rows, "gradient": gradient}, fh,
                  indent=1)


if __name__ == "__main__":
    main()
