"""Does resistance spread when there is something to resist?

Finding 6 in the README is an observation: one evolved replicator happened to be
immune to every parasite in its run, because parasites search for the four-cell
template ``1100`` and that replicator no longer contains one.  An observation is
not a demonstration that immunity is *selected*.  This is the demonstration.

Three genomes, no mutation of any kind, so nothing changes except who is
reproducing:

* **susceptible** -- the ancestor, unmodified.  410 instructions per daughter.
* **resistant**   -- the ancestor with its copy-loop marker moved from ``1100``
  to ``1101`` and the one template that points at it corrected.  Also 410
  instructions per daughter, an exact tie, and invisible to the parasite's
  search.
* **parasite**    -- ``0045adk``, evolved in baseline-s2: no copy loop of its
  own, and confirmed by co-culture to reproduce itself off the susceptible host
  and not at all off the resistant one.

The two hosts are seeded in equal numbers and cost exactly the same to run, so
in the absence of parasites neither has an advantage and the mix should hold.
Add parasites and, if immunity is worth anything, the susceptible host should be
driven down and the parasite with it.

The parasites are introduced into a soup that has already filled up, not seeded
alongside the hosts at the start.  That is not a cosmetic choice: a parasite
seeded into an empty soup reproduces perfectly well and then dies out anyway,
because the allocator puts its daughters in the empty two thirds of the world
where there is no host within search range.  Parasitism needs a crowd.

Run:  python3 experiments/epidemic.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.analysis import describe, interaction
from soup.experiment import load_ancestor
from soup.isa import NOP0, NOP1
from soup.plot import line_chart
from soup.world import World

BUDGET = 20_000_000
SOUP = 20_000
HOSTS_EACH = 16
PARASITES = 6
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def genomes() -> dict[str, bytes]:
    anc = load_ancestor()
    resistant = list(anc)
    resistant[43] = NOP1        # copy-loop marker 1100 -> 1101
    resistant[32] = NOP0        # the call's own template 0011 -> 0010
    with open(os.path.join(RESULTS, "baseline-s2.json")) as fh:
        parasite = bytes(json.load(fh)["genomes"]["0045adk"])
    return {"susceptible": bytes(anc), "resistant": bytes(resistant),
            "parasite": parasite}


SATURATE = 3_000_000     # let the hosts fill the soup before anything is added


def seed_hosts(w: World, gs: dict[str, bytes], hosts: list[str],
               layout: int) -> dict[str, str]:
    """Interleave the given hosts, packed back to back, from address zero."""
    order = []
    for i in range(HOSTS_EACH):
        block = list(hosts)
        if (i + layout) % 2:
            block.reverse()
        order.extend(block)
    labels = {}
    addr = 0
    for name in order:
        cr = w.inject(list(gs[name]), address=addr)
        labels[cr.genotype] = name
        addr += len(gs[name])
    return labels


def introduce(w: World, genome: bytes, count: int) -> int:
    """Drop creatures into gaps in an established soup, next to whoever is there."""
    placed = 0
    for start, length in list(w.memory.gaps()):
        while length >= len(genome) and placed < count:
            w.inject(list(genome), address=start)
            start += len(genome)
            length -= len(genome)
            placed += 1
        if placed >= count:
            break
    return placed


def run(with_parasites: bool, layout: int, hosts=("susceptible", "resistant")) -> dict:
    gs = genomes()
    w = World(soup_size=SOUP, seed=1, copy_mutation_rate=0.0,
              cosmic_period=10 ** 18)
    labels = seed_hosts(w, gs, list(hosts), layout)

    def census():
        counts = {"susceptible": 0, "resistant": 0, "parasite": 0}
        for cr in w.creatures:
            if cr.alive:
                counts[labels.get(cr.genotype, "parasite")] += 1
        return counts

    history = []
    next_sample = 0
    introduced = False
    while w.clock < BUDGET and not w.extinct:
        w.step_generation()
        if with_parasites and not introduced and w.clock >= SATURATE:
            introduced = True
            n = introduce(w, gs["parasite"], PARASITES)
            for cr in w.creatures:
                if cr.size == len(gs["parasite"]):
                    labels[cr.genotype] = "parasite"
            history.append({"clock": w.clock, "event": f"{n} parasites introduced",
                            **census()})
        if w.clock >= next_sample:
            history.append({"clock": w.clock, **census()})
            next_sample += BUDGET // 40
    return {"with_parasites": with_parasites, "layout": layout,
            "hosts": list(hosts), "history": history, "final": history[-1]}


def main() -> None:
    gs = genomes()
    print("Ingredients, checked before use:")
    for name in ("susceptible", "resistant"):
        print(f"  {name:<12} {describe(gs[name], budget=200_000)}")
    print(f"  parasite vs susceptible: "
          f"{interaction(gs['parasite'], gs['susceptible'], budget=200_000)}")
    print(f"  parasite vs resistant  : "
          f"{interaction(gs['parasite'], gs['resistant'], budget=200_000)}\n")

    out = []
    conditions = [
        (False, ("susceptible", "resistant")),
        (True, ("susceptible", "resistant")),
        (True, ("susceptible",)),
        (True, ("resistant",)),
    ]
    for with_parasites, hosts in conditions:
        for layout in (0, 1):
            r = run(with_parasites, layout, hosts)
            out.append(r)
            f = r["final"]
            print(f"hosts={'+'.join(hosts):<24} parasites={str(with_parasites):<5} "
                  f"layout={layout}  final: susceptible={f['susceptible']:4d} "
                  f"resistant={f['resistant']:4d} parasite={f['parasite']:4d}")

    for r in out:
        if r["layout"] != 0:
            continue
        h = r["history"]
        print(f"\nhosts: {'+'.join(r['hosts'])}, "
              f"{'with' if r['with_parasites'] else 'without'} parasites:")
        print("```")
        print(line_chart({k: [row[k] for row in h]
                          for k in ("susceptible", "resistant", "parasite")},
                         x=[row["clock"] for row in h], height=12, width=66,
                         ylabel="creatures alive", xlabel="instructions"))
        print("```")

    path = os.path.join(RESULTS, "epidemic.json")
    with open(path, "w") as fh:
        json.dump({"budget": BUDGET, "soup": SOUP, "hosts_each": HOSTS_EACH,
                   "parasites": PARASITES, "runs": out}, fh, indent=1)
    print("\nwrote", path)


if __name__ == "__main__":
    main()
