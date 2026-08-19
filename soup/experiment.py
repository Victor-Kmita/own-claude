"""Running an experiment and writing down what happened.

Everything here exists to make a run *reportable*: the same configuration and
seed must reproduce the same history, the history must be sampled on a clock
that means something (instructions executed, not wall time), and the final
census must say what each surviving genotype actually is rather than how many
of it there are.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import Counter

from .analysis import describe, isolation_assay
from .asm import assemble
from .isa import OPCODE
from .world import World

HERE = os.path.dirname(os.path.abspath(__file__))
ANCESTOR = os.path.join(HERE, "ancestor.sm")


def load_ancestor(path: str = ANCESTOR) -> list[int]:
    with open(path) as fh:
        return assemble(fh.read())


def shannon(counts) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for n in counts.values():
        if n:
            p = n / total
            h -= p * math.log(p, 2)
    return h


def sample(world: World) -> dict:
    living = [c for c in world.creatures if c.alive]
    pop = Counter(c.genotype for c in living)
    sizes = [c.size for c in living]
    foreign = [c for c in living if c.stats.foreign_calls > 0]
    # The sharper signal: creatures that both ran somebody else's code *and*
    # managed to reproduce.  Wandering into a neighbour is common; wandering in
    # and coming back out with a daughter is the ecological event.
    breeders = [c for c in living if c.stats.births > 0]
    foreign_breeders = [c for c in breeders if c.stats.foreign_calls > 0]
    dominant, dominant_n = pop.most_common(1)[0] if pop else ("-", 0)
    return {
        "clock": world.clock,
        "alive": len(living),
        "genotypes": len(pop),
        "diversity": round(shannon(pop), 3),
        "mean_size": round(sum(sizes) / len(sizes), 2) if sizes else 0,
        "median_size": sorted(sizes)[len(sizes) // 2] if sizes else 0,
        "min_size": min(sizes) if sizes else 0,
        "max_size": max(sizes) if sizes else 0,
        "load": round(world.memory.load, 3),
        "births": world.births,
        "deaths": world.deaths,
        "dominant": dominant,
        "dominant_share": round(dominant_n / len(living), 3) if living else 0,
        "foreign_exec_share": round(len(foreign) / len(living), 3) if living else 0,
        "foreign_breeder_share": (round(len(foreign_breeders) / len(breeders), 3)
                                  if breeders else 0),
        "breeders": len(breeders),
        "alloc_failures": world.alloc_failures,
        "size_hist": dict(Counter(sizes).most_common(6)),
    }


def census(world: World, top: int = 12, assay_budget: int = 400_000) -> list[dict]:
    """Who is alive at the end, and what kind of thing is each of them."""
    pop = world.population()
    by_geno: dict[str, list] = {}
    for cr in world.creatures:
        if cr.alive:
            by_geno.setdefault(cr.genotype, []).append(cr)
    rows = []
    for label, n in pop.most_common(top):
        crs = by_geno[label]
        genome = world.genebank.genome[label]
        what = describe(genome, budget=assay_budget)
        rows.append({
            "genotype": label,
            "n": n,
            "size": len(genome),
            "births": world.genebank.births[label],
            "fidelity": round(world.genebank.fidelity(label), 3),
            "parent": world.genebank.origin.get(label),
            "first_seen": world.genebank.first_seen.get(label),
            "kind": what["kind"],
            "cost": what["cost"],
            "cost_paired": what["cost_paired"],
            "mean_foreign_calls": round(sum(c.stats.foreign_calls for c in crs) / len(crs), 1),
            "mean_foreign_reads": round(sum(c.stats.foreign_reads for c in crs) / len(crs), 1),
            "mean_errors": round(sum(c.stats.errors for c in crs) / len(crs), 1),
        })
    return rows


def lineage(world: World, label: str, limit: int = 40) -> list[str]:
    """Walk the chain of first-appearance parents back toward the ancestor."""
    chain = [label]
    seen = {label}
    cur = label
    for _ in range(limit):
        parent = world.genebank.origin.get(cur)
        if parent is None or parent in seen:
            break
        chain.append(parent)
        seen.add(parent)
        cur = parent
    return list(reversed(chain))


def run(
    name: str,
    instructions: int = 50_000_000,
    sample_every: int = 1_000_000,
    seed: int = 1,
    soup_size: int = 60_000,
    slice_size: float = 20,
    slice_pow: float = 0.0,
    copy_mutation_rate: float = 1 / 1000,
    cosmic_period: int = 2000,
    reap_threshold: float = 0.8,
    search_limit: int = 1024,
    quiet: bool = False,
    ancestor_path: str = ANCESTOR,
) -> dict:
    code = load_ancestor(ancestor_path)
    world = World(
        soup_size=soup_size, seed=seed, slice_size=slice_size, slice_pow=slice_pow,
        copy_mutation_rate=copy_mutation_rate, cosmic_period=cosmic_period,
        reap_threshold=reap_threshold, search_limit=search_limit,
    )
    world.inject(code, address=0)

    started = time.time()
    history = [sample(world)]
    next_sample = sample_every
    while world.clock < instructions and not world.extinct:
        world.step_generation()
        if world.clock >= next_sample:
            row = sample(world)
            history.append(row)
            next_sample += sample_every
            if not quiet:
                print(f"  {row['clock']/1e6:6.1f}M  alive={row['alive']:4d} "
                      f"types={row['genotypes']:4d}  H={row['diversity']:5.2f}  "
                      f"size~{row['mean_size']:6.1f}  dom={row['dominant']} "
                      f"({row['dominant_share']:.0%})  foreign={row['foreign_exec_share']:.0%}"
                      f" fbreed={row['foreign_breeder_share']:.0%}")

    elapsed = time.time() - started
    result = {
        "name": name,
        "config": {
            "instructions": instructions, "seed": seed, "soup_size": soup_size,
            "slice_size": slice_size, "slice_pow": slice_pow,
            "copy_mutation_rate": copy_mutation_rate, "cosmic_period": cosmic_period,
            "reap_threshold": reap_threshold, "search_limit": search_limit,
            "ancestor_size": len(code),
        },
        "extinct": world.extinct,
        "elapsed_sec": round(elapsed, 1),
        "instructions_per_sec": round(world.clock / elapsed) if elapsed else 0,
        "totals": {
            "clock": world.clock, "births": world.births, "deaths": world.deaths,
            "genotypes_seen": len(world.genebank.genome),
            "alloc_failures": world.alloc_failures,
        },
        "history": history,
        "census": census(world),
    }
    result["lineage_of_dominant"] = (
        lineage(world, result["census"][0]["genotype"]) if result["census"] else []
    )
    result["genomes"] = {
        row["genotype"]: list(world.genebank.genome[row["genotype"]])
        for row in result["census"]
    }
    return result


def save(result: dict, directory: str) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{result['name']}.json")
    with open(path, "w") as fh:
        json.dump(result, fh, indent=1)
    return path
