"""How many genotypes share a phenotype, and does parasitism change that?

Standish (2004) found that Tierra's gene banks held far more genotypes than
behaviours -- 69,139, 87,003 and 198,982 genotypes over about a billion
instructions collapsed onto 83, 86 and 158 distinct phenotypes -- and that
neutral variants were *rarer* than expected.  His explanation is ecological: a
parasite needs a host within search range, so a neutral variant that lands
somewhere without one never replicates, and host-parasite competition therefore
suppresses neutrality.

That gives a directional prediction this soup can test, because its runs split
into two kinds of world by seed alone: some fill up with parasites and some stay
almost free of them.  If Standish is right, the parasite-rich world should show
*fewer* genotypes per phenotype than the quiet ones.

A phenotype here is what a genome does, not what it is: what it becomes when
cultured alone, what a daughter costs it, and what happens beside each reference
organism.  Two genotypes with the same signature are neutral variants as far as
anything in this world can distinguish.

Run:  python3 experiments/neutrality.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import phenotype_signature
from soup.experiment import load_ancestor, sample
from soup.isa import NOP0, NOP1
from soup.world import World

BUDGET = 60_000_000
SAMPLE = 70
ASSAY_BUDGET = 120_000
SEEDS = (1, 2, 3)
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def chao1(counts: Counter) -> float:
    """Estimate how many phenotypes exist, from how many were seen once or twice.

    A sample of seventy genotypes cannot count the phenotypes in a gene bank of
    fifteen thousand, but the shape of the sample says something about what was
    missed: if many phenotypes turned up exactly once, there are probably more
    out there that turned up not at all.  This is the standard Chao1 estimator
    from ecology, used here for exactly the job it was designed for, and it is
    what makes a number comparable with Standish's counts over whole Tierra
    gene banks.
    """
    observed = len(counts)
    f1 = sum(1 for n in counts.values() if n == 1)
    f2 = sum(1 for n in counts.values() if n == 2)
    if f2 == 0:
        return round(observed + f1 * (f1 - 1) / 2, 1)
    return round(observed + f1 * f1 / (2 * f2), 1)


def panel() -> list[bytes]:
    """Reference organisms every sampled genome is put next to."""
    anc = load_ancestor()
    resistant = list(anc)
    resistant[43] = NOP1        # copy-loop marker moved out of a parasite's reach
    resistant[32] = NOP0
    return [bytes(anc), bytes(resistant)]


def grow(seed: int) -> World:
    w = World(soup_size=60_000, seed=seed, copy_mutation_rate=1 / 1000,
              cosmic_period=2000)
    w.inject(load_ancestor(), address=0)
    while w.clock < BUDGET and not w.extinct:
        w.step_generation()
    return w


def from_saved(paths: list[str], refs: list[bytes], limit: int = 70) -> list[dict]:
    """Same measurement, but on the gene-bank samples stored in saved runs.

    Runs that recorded a slice of their gene bank can be re-examined without
    re-simulating them, which is what makes a within-condition comparison
    affordable: two runs at the *same* mutation rate, one that filled with
    parasites and one that did not, is the contrast Standish's explanation
    actually predicts something about.
    """
    rows = []
    for path in paths:
        with open(path) as fh:
            r = json.load(fh)
        labels = r.get("gene_bank_sample") or list(r["genomes"])
        rng = random.Random(r["config"]["seed"])
        chosen = rng.sample(labels, min(limit, len(labels)))
        sigs = Counter(phenotype_signature(bytes(r["genomes"][l]), refs,
                                           budget=ASSAY_BUDGET) for l in chosen)
        h = r["history"][-1]
        rows.append({
            "run": r["name"], "sampled": len(chosen), "phenotypes": len(sigs),
            "phenotypes_estimated": chao1(sigs),
            "genotypes_per_phenotype": round(len(chosen) / len(sigs), 2),
            "foreign_breeder_share": h["foreign_breeder_share"],
            "genotypes_seen": r["totals"]["genotypes_seen"],
            "mean_generation": h.get("mean_generation", 0),
        })
        print(f"{r['name']}: {len(chosen)} sampled -> {len(sigs)} phenotypes "
              f"(Chao1 estimate {rows[-1]['phenotypes_estimated']} in the whole "
              f"bank of {r['totals']['genotypes_seen']:,}); "
              f"parasitism {h['foreign_breeder_share']:.0%}; "
              f"generations {rows[-1]['mean_generation']:.0f}")
    return rows


def main() -> None:
    refs = panel()
    if len(sys.argv) > 1:
        rows = from_saved(sys.argv[1:], refs)
        out = os.path.join(RESULTS, "neutrality_saved.json")
        with open(out, "w") as fh:
            json.dump({"assay_budget": ASSAY_BUDGET, "rows": rows}, fh, indent=1)
        print("wrote", out)
        return
    rows = []
    for seed in SEEDS:
        w = grow(seed)
        snap = sample(w)
        rng = random.Random(seed)
        labels = list(w.genebank.genome)
        chosen = rng.sample(labels, min(SAMPLE, len(labels)))
        signatures = Counter(
            phenotype_signature(w.genebank.genome[label], refs, budget=ASSAY_BUDGET)
            for label in chosen)
        row = {
            "seed": seed,
            "genotypes_seen": len(labels),
            "sampled": len(chosen),
            "phenotypes": len(signatures),
            "phenotypes_estimated": chao1(signatures),
            "genotypes_per_phenotype": round(len(chosen) / len(signatures), 2),
            "foreign_breeder_share": snap["foreign_breeder_share"],
            "alive": snap["alive"],
            "mean_generation": snap["mean_generation"],
            "commonest": [[list(sig), n] for sig, n in signatures.most_common(4)],
        }
        rows.append(row)
        print(f"seed {seed}: {len(labels):,} genotypes seen, {len(chosen)} sampled -> "
              f"{len(signatures)} phenotypes "
              f"({row['genotypes_per_phenotype']} genotypes per phenotype); "
              f"parasitism indicator {row['foreign_breeder_share']:.0%}")
        for sig, n in signatures.most_common(4):
            print(f"    {n:>3}  {sig}")

    rich = max(rows, key=lambda r: r["foreign_breeder_share"])
    quiet = [r for r in rows if r is not rich]
    print(f"\nparasite-rich seed {rich['seed']} "
          f"({rich['foreign_breeder_share']:.0%} foreign breeders): "
          f"{rich['genotypes_per_phenotype']} genotypes per phenotype")
    print("quieter seeds: " + ", ".join(
        f"{r['genotypes_per_phenotype']} (seed {r['seed']}, "
        f"{r['foreign_breeder_share']:.0%})" for r in quiet))
    print("\nStandish predicts the parasite-rich world shows the LEAST neutrality "
          "(fewest genotypes per phenotype).")

    with open(os.path.join(RESULTS, "neutrality.json"), "w") as fh:
        json.dump({"budget": BUDGET, "sample": SAMPLE,
                   "assay_budget": ASSAY_BUDGET, "rows": rows}, fh, indent=1)
    print("wrote", os.path.join(RESULTS, "neutrality.json"))


if __name__ == "__main__":
    main()
