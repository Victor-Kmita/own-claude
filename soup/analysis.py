"""Tools for asking what actually evolved.

The important one is :func:`isolation_assay`.  Population statistics alone
cannot tell you whether a genotype is a self-sufficient replicator or a parasite
that borrows its neighbour's copy loop, because in a crowded soup both simply
look like "things that reproduce".  Put a genome alone in an empty soup and the
question answers itself: a self-sufficient replicator still divides, a parasite
sits there and does nothing.

This is the same experiment you would run on a suspected obligate parasite in a
biology lab -- try to culture it axenically -- and it is just as decisive here.
"""

from __future__ import annotations

from collections import Counter

from .asm import disassemble
from .isa import INSTRUCTIONS, OPCODE
from .world import World


def isolation_assay(genome: bytes, budget: int = 500_000, soup_size: int = 4000,
                    copies: int = 1) -> dict:
    """Run ``copies`` of a genome alone in a sterile soup, with no mutation.

    ``copies == 1`` answers "can it reproduce by itself".  ``copies == 2`` (two
    identical neighbours) answers a different and equally interesting question:
    can it reproduce given that a *copy of itself* is available to borrow code
    from?  A genotype that fails the first test and passes the second is a
    parasite whose host happens to be its own species -- which is exactly what a
    creature that lost half of its own copy loop looks like.
    """
    # The sterile medium is filled with ``zero`` instructions, not with the
    # default nop0.  A soup of nop0 is not empty at all -- it is an endless
    # field of template, and any creature searching for an all-zero pattern
    # would match the background immediately and score as self-sufficient on
    # the strength of the petri dish.  ``zero`` is inert and carries no
    # template bits, so every successful search in the assay must have found
    # the creature's own code (or, with copies=2, its neighbour's).
    w = World(soup_size=soup_size, copy_mutation_rate=0.0,
              cosmic_period=10 ** 12, seed=12345, filler=OPCODE["zero"])
    crs = []
    for i in range(copies):
        crs.append(w.inject(list(genome), address=i * (len(genome) + 200)))
    while w.clock < budget and w.alive_count() > 0:
        w.step_generation()
        if w.births:
            break
    first = crs[0]
    return {
        "self_sufficient": w.births > 0,
        "births": w.births,
        "instructions": w.clock,
        "errors": first.stats.errors,
        "foreign_calls": first.stats.foreign_calls,
        "foreign_reads": first.stats.foreign_reads,
    }


def classify(genome: bytes, budget: int = 500_000) -> str:
    """One of: replicator, self-assisted, parasite, inert."""
    alone = isolation_assay(genome, budget=budget, copies=1)
    if alone["self_sufficient"]:
        return "replicator"
    pair = isolation_assay(genome, budget=budget, copies=2)
    if pair["self_sufficient"]:
        return "self-assisted"
    return "parasite" if _has_reproductive_machinery(genome) else "inert"


def _has_reproductive_machinery(genome: bytes) -> bool:
    ops = set(genome)
    return OPCODE["mal"] in ops and OPCODE["divide"] in ops


def genome_diff(a: bytes, b: bytes) -> str:
    """A readable alignment of two genomes of possibly different length."""
    out = []
    n = max(len(a), len(b))
    for i in range(n):
        x = a[i] if i < len(a) else None
        y = b[i] if i < len(b) else None
        if x == y:
            continue
        nx = INSTRUCTIONS[x] if x is not None else "--"
        ny = INSTRUCTIONS[y] if y is not None else "--"
        out.append(f"  {i:4d}  {nx:<8} -> {ny}")
    return "\n".join(out) if out else "  (identical)"


def profile(world: World, top: int = 10) -> list[dict]:
    """Per-genotype summary of the living population."""
    pop = world.population()
    by_geno: dict[str, list] = {}
    for cr in world.creatures:
        if cr.alive:
            by_geno.setdefault(cr.genotype, []).append(cr)
    rows = []
    for label, n in pop.most_common(top):
        crs = by_geno[label]
        rows.append({
            "genotype": label,
            "n": n,
            "size": crs[0].size,
            "births": world.genebank.births[label],
            "mean_foreign_calls": sum(c.stats.foreign_calls for c in crs) / len(crs),
            "mean_foreign_reads": sum(c.stats.foreign_reads for c in crs) / len(crs),
            "mean_errors": sum(c.stats.errors for c in crs) / len(crs),
            "parent": world.genebank.origin.get(label),
            "fidelity": world.genebank.fidelity(label),
            "first_seen": world.genebank.first_seen.get(label),
        })
    return rows


def instruction_histogram(genome: bytes) -> Counter:
    return Counter(INSTRUCTIONS[op] for op in genome)


def listing(genome: bytes) -> str:
    return disassemble(list(genome))
