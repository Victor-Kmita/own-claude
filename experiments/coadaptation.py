"""Why does a transplanted parasite die?

`0045adk` held a fifth of the population in the run it evolved in.  Introduced
into a saturated soup of ancestors it barely establishes, and in an
all-susceptible soup it dies out entirely (README finding 11).  The obvious
explanation is co-adaptation: a parasite reaches its host by searching for a
pattern, and how far the search has to go depends on which genotypes are lying
around it and how they are spaced.  A naive population is a different world.

This tests that directly by rebuilding, in three stages, the community the
parasite came from:

* **ancestors** -- the naive population from finding 11;
* **its own host** -- the susceptible replicator from the same run;
* **its own community** -- the top replicators of that run together, in the
  proportions the census found them in.

Each community is seeded, allowed to fill the soup, and then infected with six
parasites.  If co-adaptation is the answer, the parasite should persist in the
third and fail in the first.

Run:  python3 experiments/coadaptation.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.experiment import load_ancestor, sample
from soup.world import World

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
SOURCE = os.path.join(RESULTS, "baseline-s2.json")
PARASITE = "0045adk"
SATURATE = 3_000_000
BUDGET = 25_000_000
SOUP = 20_000
PARASITES = 6
HOSTS_EACH = 16
MAX_SEED_CELLS = 6_000      # keep the seeded community well under the soup size


def load_source() -> dict:
    with open(SOURCE) as fh:
        return json.load(fh)


def communities(run: dict) -> dict[str, list[bytes]]:
    genomes = {k: bytes(v) for k, v in run["genomes"].items()}
    replicators = [row["genotype"] for row in run["census"]
                   if row["kind"] == "replicator"]
    own_host = replicators[0] if replicators else None
    # The census as it actually stood: seven host-dependent genotypes and two
    # replicators, in the numbers they were found in.  A parasite-rich soup is
    # a different environment from a soup of hosts, and rebuilding only the
    # hosts may be why the earlier reconstructions failed.
    census_mix: list[bytes] = []
    for row in run["census"]:
        if row["genotype"] == PARASITE:
            continue
        census_mix.extend([genomes[row["genotype"]]] * max(1, row["n"] // 10))
    return {
        "ancestors": [bytes(load_ancestor())],
        "its own host": [genomes[own_host]] if own_host else [],
        "its own community": [genomes[g] for g in replicators],
        "its whole census": census_mix,
    }


def trial(hosts: list[bytes], parasite: bytes, mutation: bool = False) -> dict:
    w = World(soup_size=SOUP, seed=1,
              copy_mutation_rate=1 / 1000 if mutation else 0.0,
              cosmic_period=2000 if mutation else 10 ** 18)
    addr = 0
    for i in range(HOSTS_EACH):
        for genome in hosts:
            if addr + len(genome) > MAX_SEED_CELLS:
                break
            w.inject(list(genome), address=addr, lineage="host")
            addr += len(genome)

    history = []
    introduced = False
    parasite_label = None
    next_sample = 0
    while w.clock < BUDGET and not w.extinct:
        w.step_generation()
        if not introduced and w.clock >= SATURATE:
            introduced = True
            placed = 0
            for start, length in list(w.memory.gaps()):
                while length >= len(parasite) and placed < PARASITES:
                    cr = w.inject(list(parasite), address=start, lineage="parasite")
                    parasite_label = cr.genotype
                    start += len(parasite)
                    length -= len(parasite)
                    placed += 1
                if placed >= PARASITES:
                    break
        if w.clock >= next_sample:
            counts = {"host": 0, "parasite": 0}
            # Two different questions.  The lineage count asks whether the
            # creatures introduced have living descendants.  The genotype count
            # asks whether that exact genome is present at all -- which in a
            # mutating soup it can be without any of them being descendants,
            # because a host can mutate into it.  The second is the one that
            # tests whether the parasite lived by being re-created.
            same_genome = 0
            for cr in w.creatures:
                if not cr.alive:
                    continue
                if cr.lineage in counts:
                    counts[cr.lineage] += 1
                if parasite_label and cr.genotype == parasite_label:
                    same_genome += 1
            history.append({"clock": w.clock, **counts,
                            "parasite_genotype": same_genome})
            next_sample += BUDGET // 10
    snap = sample(w)
    return {"history": history, "final": history[-1], "alive": snap["alive"]}


def main() -> None:
    run = load_source()
    parasite = bytes(run["genomes"][PARASITE])
    print(f"{PARASITE}: {len(parasite)} cells, host-dependent, held a fifth of "
          f"the population in {run['name']}\n")
    out = {}
    for mutation in (False, True):
        print(f"--- mutation {'on' if mutation else 'off'} "
              f"{'(the parasite lineage can be re-created from its hosts)' if mutation else ''}")
        for name, hosts in communities(run).items():
            if not hosts:
                continue
            result = trial(hosts, parasite, mutation=mutation)
            out[f"{name} / mutation {'on' if mutation else 'off'}"] = result
            f = result["final"]
            print(f"{name:>20}: {len(hosts)} host genotype(s) -> "
                  f"final hosts {f['host']:4d}, parasite lineage {f['parasite']:4d}, "
                  f"copies of its genome anywhere {f['parasite_genotype']:4d}")
            print("   lineage : " + " ".join(f"{r['parasite']:3d}"
                                             for r in result["history"]))
            print("   genotype: " + " ".join(f"{r['parasite_genotype']:3d}"
                                             for r in result["history"]))
    with open(os.path.join(RESULTS, "coadaptation.json"), "w") as fh:
        json.dump({"parasite": PARASITE, "budget": BUDGET, "results": out}, fh,
                  indent=1)
    print(f"\n(the row of numbers is the parasite count at each sample)")


if __name__ == "__main__":
    main()
