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

    Reproduction here means an **exact copy**, not merely a successful
    ``divide``.  The distinction is not pedantic: a damaged creature can ask for
    the smallest legal block, scribble in half of it and divide, producing an
    eight-cell fragment in eighty instructions.  Counting that as reproduction
    makes junk look like the fittest thing in the soup.
    """
    # The sterile medium is filled with ``zero`` instructions, not with the
    # default nop0.  A soup of nop0 is not empty at all -- it is an endless
    # field of template, and any creature searching for an all-zero pattern
    # would match the background immediately and score as self-sufficient on
    # the strength of the petri dish.  ``zero`` is inert and carries no
    # template bits, so every successful search in the assay must have found
    # the creature's own code (or, with copies=2, its neighbour's).
    # slice_size=1 so that the reported cost is an exact instruction count
    # rather than a multiple of the scheduler's quantum.  With one or two
    # creatures in the dish the quantum has no other effect.
    w = World(soup_size=soup_size, copy_mutation_rate=0.0, slice_size=1,
              cosmic_period=10 ** 12, seed=12345, filler=OPCODE["zero"])
    crs = []
    for i in range(copies):
        crs.append(w.inject(list(genome), address=i * (len(genome) + 200)))
    label = crs[0].genotype
    seeded = w.genebank.births[label]
    divided_at = None
    first = crs[0]
    # Cost is measured in the mother's *own* instructions, not the world clock:
    # once the first daughter exists it is running too, and the clock stops
    # being a measure of what the mother spent.
    copy_costs: list[int] = []
    spent = 0
    while w.clock < budget and w.alive_count() > 0:
        # The mother's own births, not the genotype's.  Counting the genotype
        # made every creature whose daughter could divide once look as though
        # the *mother* had gone round twice, which is a different claim and the
        # one finding 13 and finding 17 were reading off this field.
        before = first.stats.births
        w.step_generation()
        if divided_at is None and w.births:
            divided_at = w.clock
        if first.stats.births > before:
            copy_costs.append(first.stats.instructions - spent)
            spent = first.stats.instructions
            if len(copy_costs) >= 2:      # enough to know whether it repeats
                break
    copied = w.genebank.births[label] > seeded
    return {
        "self_sufficient": copied,
        "divided": divided_at is not None,
        "instructions": copy_costs[0] if copy_costs else None,
        "second_copy_cost": copy_costs[1] if len(copy_costs) > 1 else None,
        "repeats": len(copy_costs) > 1,
        "instructions_to_first_division": divided_at,
        "births": w.births,
        "errors": first.stats.errors,
        "foreign_calls": first.stats.foreign_calls,
        "foreign_reads": first.stats.foreign_reads,
    }


def describe(genome: bytes, budget: int = 500_000) -> dict:
    """Culture a genome alone, then in a pair, and say what it is.

    ``kind`` is one of:

    ``replicator``     divides with nothing else in the world.
    ``self-assisted``  cannot divide alone, but two of them together can: it has
                       lost something it can borrow back from its own kind.
    ``host-dependent`` cannot divide even beside a copy of itself, yet carries
                       the machinery to try.  In the soup it only works next to
                       some *other* genotype -- but whether it then copies
                       itself (a parasite) or copies its neighbour (its CPU has
                       been captured) cannot be decided from the genome alone.
                       That takes :func:`interaction`.
    ``inert``          no reproductive machinery left at all -- usually a
                       truncated fragment that other creatures keep emitting.

    ``cost`` is the number of instructions the creature spent to produce its
    first daughter when alone; for the ancestor it is 410.  ``cost_per_cell``
    divides that by genome length, and the two together say *how* a descendant
    got cheaper.  A creature that is cheaper only because it is shorter keeps
    the ancestor's 6.4 instructions per cell; one that has found a better copy
    loop -- unrolling it, as Tierra's optimized creatures did -- comes in below
    that.  Ray's ancestor sat at 10.2 per cell and his best descendants reached
    6; mine starts where his finished, so shrinking is the only lever left
    unless a genuinely new loop appears.
    """
    alone = isolation_assay(genome, budget=budget, copies=1)
    if alone["self_sufficient"]:
        return {"kind": "replicator", "cost": alone["instructions"],
                "cost_per_cell": round(alone["instructions"] / len(genome), 2),
                # Whether it can do it twice.  A creature that spends everything
                # on one daughter and then runs itself into an error loop scores
                # best on cost and cannot found a lineage on its own -- which is
                # a strategy, not a bug, and worth telling apart.
                "repeats": alone["repeats"],
                "second_copy_cost": alone["second_copy_cost"],
                "cost_paired": None, "divides_without_copying": False}
    pair = isolation_assay(genome, budget=budget, copies=2)
    if pair["self_sufficient"]:
        return {"kind": "self-assisted", "cost": None, "cost_per_cell": None,
                "cost_paired": pair["instructions"],
                "divides_without_copying": False}
    kind = "host-dependent" if _has_reproductive_machinery(genome) else "inert"
    # It divides, but what comes out is not it.  Worth recording separately:
    # these are the creatures that fill a census with eight-cell fragments.
    return {"kind": kind, "cost": None, "cost_per_cell": None, "cost_paired": None,
            "divides_without_copying": bool(alone["divided"] or pair["divided"])}


def sustained_cost(genome: bytes, copies: int = 16, clock: int = 400_000,
                   soup_size: int = 60_000, gap: int = 0) -> dict:
    """What a daughter costs a *population* of this genome, not a lone creature.

    :func:`describe` cultures one creature alone and reports what its first
    daughter cost.  That is the number this project has quoted as "cost" from
    the beginning, and for the ancestor it is honest: put sixty ancestors in a
    soup and the world spends about the same per birth as one ancestor alone.

    It is not honest for every genome.  The 27-cell champion of finding 17
    reports 178 instructions alone and needs between 900 and 6,000 in a
    population, because after its first daughter it wanders out of its own
    copy loop and has to fall back through its own code to start again,
    accumulating hundreds of errors on the way.  Alone, with the whole soup
    empty, that costs it little; in company it costs it everything.

    So: place ``copies`` of the genome, run the world with mutation off, and
    return the world clock divided by the births it bought, together with the
    errors each creature accumulated.  Mutation is off so that this measures
    the genome and not its descendants.
    """
    world = World(soup_size=soup_size, seed=1, copy_mutation_rate=0.0,
                  cosmic_period=10 ** 18)
    step = len(genome) + gap
    for i in range(copies):
        world.inject(genome, address=(i * step) % soup_size)
    while world.clock < clock and not world.extinct:
        world.step_generation()
    living = [c for c in world.creatures if c.alive]
    births = world.births
    return {
        "copies": copies,
        "births": births,
        "instructions_per_birth": round(world.clock / births, 1) if births else None,
        "errors_per_creature": round(sum(c.stats.errors for c in living)
                                     / len(living), 1) if living else None,
        "alive": len(living),
    }


def classify(genome: bytes, budget: int = 500_000) -> str:
    """One of: replicator, self-assisted, host-dependent, inert."""
    return describe(genome, budget=budget)["kind"]


def coculture_assay(guest: bytes, host: bytes, budget: int = 500_000,
                    soup_size: int = 6000, gap: int = 0,
                    stop_at_first: bool = True, flank: bool = False) -> dict:
    """Koch's postulates for a digital parasite.

    Put one guest next to one host in a sterile soup and count who divides.
    Run the same thing with the host left out.  If the guest reproduces only
    when the host is present, and the reproduction is achieved by executing code
    that lies outside the guest's own genome, then the guest is living off the
    host -- not by analogy, but in the plain mechanical sense.

    ``flank`` puts a host on *each* side of the guest instead of one beside it.
    That is the arrangement Ray used to demonstrate immunity in Tierra -- a
    parasite "flanked on each side with one individual" of the immune genotype
    was eliminated, while the same parasite beside the ancestor coexisted with
    it indefinitely.  It matters because a template search runs outward in both
    directions: a guest with one host on one side and empty medium on the other
    is in a different world from one surrounded.

    ``gap`` is the number of empty cells between the two genomes, and it is not
    a detail.  A template search takes the *nearest* match, so a parasite whose
    own body contains a competing pattern only reaches its host when the host is
    closer than that pattern.  The allocator packs live creatures back to back,
    so ``gap=0`` is what the soup actually looks like; larger gaps are a way to
    ask how far infection can reach.
    """
    from .world import World

    guest_like, host_like = guest, host

    def trial(genomes, guest_index: int = 0):
        w = World(soup_size=soup_size, copy_mutation_rate=0.0,
                  cosmic_period=10 ** 12, seed=999, filler=OPCODE["zero"])
        crs = []
        addr = 0
        for g in genomes:
            crs.append(w.inject(list(g), address=addr))
            addr += len(g) + gap
        crs = [crs[guest_index]] + [c for i, c in enumerate(crs) if i != guest_index]
        births = {c.cid: 0 for c in crs}
        while w.clock < budget:
            w.step_generation()
            for c in crs:
                births[c.cid] = c.stats.births
            if stop_at_first and births[crs[0].cid] > 0:
                break
        guest_cr = crs[0]
        # Whose genome ended up in the daughter?  This is the question that
        # decides what the guest actually is.  A creature that borrows a copy
        # loop and copies *itself* is a parasite.  One that borrows the whole
        # body of its neighbour ends up copying the *neighbour* -- it spends its
        # own CPU making its host's children, which is the opposite arrangement.
        # What did the *guest* produce?  The gene bank already records every
        # birth as (daughter genotype, mother genotype), so ask it rather than
        # guessing from who is lying next to whom at the end.
        guest_label = crs[0].genotype
        host_label = crs[1].genotype if len(crs) > 1 else None
        produced = Counter()
        by_parent_genotype = Counter()
        for (child, parent), n in w.genebank.parent_births.items():
            by_parent_genotype[parent] += n
            if parent == guest_label:
                produced["self" if child == guest_label else
                         "host" if child == host_label else "other"] += n
        return {
            "guest_births": guest_cr.stats.births,
            "guest_foreign_calls": guest_cr.stats.foreign_calls,
            "guest_foreign_reads": guest_cr.stats.foreign_reads,
            "instructions": w.clock,
            "host_births": crs[1].stats.births if len(crs) > 1 else None,
            "offspring": produced,
            # Genotype-level totals: every individual of that genotype, not just
            # the one that was seeded.  Comparing a seeded individual's births
            # with a whole genotype's is the kind of mistake that makes a host
            # look six times less fertile than the parasite living on it.
            "guest_genotype_births": by_parent_genotype.get(guest_label, 0),
            "host_genotype_births": (by_parent_genotype.get(host_label, 0)
                                     if host_label and host_label != guest_label
                                     else None),
            "population": Counter(c.genotype for c in w.creatures if c.alive),
        }

    with_host = [host, guest, host] if flank else [guest, host]
    return {
        "with_host": trial(with_host, guest_index=1 if flank else 0),
        "alone": trial([guest]),
        "with_own_kind": trial([guest, guest]),
    }


def interaction(guest: bytes, host: bytes, budget: int = 500_000) -> str:
    """What one genotype does to another when they are neighbours.

    ``independent`` the guest reproduces on its own; the neighbour is beside
                    the point.  Checked first, because a self-sufficient
                    replicator standing next to anything still makes copies of
                    itself, and calling that parasitism would be nonsense.
    ``parasitism``  the guest reproduces *itself*, and only when the host is
                    there to be used.
    ``hijacked``    the guest reproduces the *host*: its CPU has been captured.
    ``mixed``       both happen.
    ``none``        the guest does not reproduce next to this host.
    """
    if isolation_assay(guest, budget=budget, copies=1)["self_sufficient"]:
        return "independent"
    out = coculture_assay(guest, host, budget=budget)["with_host"]["offspring"]
    self_copies, host_copies = out.get("self", 0), out.get("host", 0)
    if self_copies and host_copies:
        return "mixed"
    if self_copies:
        return "parasitism"
    if host_copies:
        return "hijacked"
    return "other" if out else "none"


def interaction_matrix(genomes: dict[str, bytes], guests: list[str],
                       hosts: list[str], budget: int = 300_000) -> dict:
    """Cross every suspected dependent with every self-sufficient replicator."""
    return {g: {h: interaction(genomes[g], genomes[h], budget=budget)
                for h in hosts if h != g}
            for g in guests}


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


def trace(genome: bytes, steps: int = 400, soup_size: int = 2000,
          neighbours: list[bytes] | None = None) -> list[dict]:
    """Single-step a genome in a sterile soup and record what it does.

    This exists because hand-reading an evolved genome is a good way to convince
    yourself of something false.  Every claim in the write-up about *why* a
    descendant is faster or how a parasite reaches its host was checked against
    a trace, not against a careful look at the listing.
    """
    from .isa import INSTRUCTIONS
    from .vm import run_slice
    from .world import World

    w = World(soup_size=soup_size, copy_mutation_rate=0.0, cosmic_period=10 ** 12,
              seed=4, filler=OPCODE["zero"])
    cr = w.inject(list(genome), address=0)
    addr = len(genome) + 32
    for g in neighbours or []:
        w.inject(list(g), address=addr)
        addr += len(g) + 32
    rows = []
    for _ in range(steps):
        ip = cr.cpu.ip
        op = w.soup[ip]
        before = (cr.stats.errors, cr.stats.births)
        run_slice(w, cr, 1)
        rows.append({
            "ip": ip,
            "op": INSTRUCTIONS[op],
            "ax": cr.cpu.ax, "bx": cr.cpu.bx, "cx": cr.cpu.cx,
            "error": cr.stats.errors > before[0],
            "birth": cr.stats.births > before[1],
            "daughter": cr.daughter,
        })
        if rows[-1]["birth"]:
            break
    return rows


def trace_summary(rows: list[dict], collapse: bool = True) -> str:
    """Render a trace, collapsing repeated loops into one line each.

    A replication cycle is ~400 instructions of which ~370 are the copy loop
    going round.  Printing all of them hides the interesting part, so any run of
    instructions that repeats the same sequence of addresses is folded into a
    single line reporting how many times it went round.
    """
    out = []
    i = 0
    n = len(rows)
    while i < n:
        cycle = 0
        if collapse:
            ip0 = rows[i]["ip"]
            for k in range(i + 1, min(i + 40, n)):        # find the loop period
                if rows[k]["ip"] == ip0:
                    period = k - i
                    reps = 0
                    j = i
                    while (j + 2 * period <= n and
                           all(rows[j + m]["ip"] == rows[j + period + m]["ip"]
                               for m in range(period))):
                        reps += 1
                        j += period
                    if reps >= 2:
                        cycle = (period, reps, j)
                    break
        if cycle:
            period, reps, end = cycle
            span = sorted({r["ip"] for r in rows[i:i + period]})
            out.append(f"        \u21ba {reps + 1} iterations of the loop at "
                       f"{span[0]}..{span[-1]} ({period} instructions each), "
                       f"cx {rows[i]['cx']} -> {rows[end]['cx']}")
            i = end
            continue
        r = rows[i]
        flag = "!" if r["error"] else ("*" if r["birth"] else " ")
        out.append(f"{flag} {r['ip']:5d}  {r['op']:<8} ax={r['ax']:<6} bx={r['bx']:<6} "
                   f"cx={r['cx']:<6} daughter={r['daughter']}")
        i += 1
    return "\n".join(out)


def solo_rate(genome: bytes, budget: int = 200_000) -> int:
    """Births by the whole genotype, seeded alone, in a fixed instruction budget."""
    return coculture_assay(genome, genome, budget=budget,
                           stop_at_first=False)["alone"]["guest_genotype_births"]


def susceptibility(host: bytes, parasite: bytes, budget: int = 200_000) -> dict:
    """How much reproduction does one host hand to one parasite?

    Both are placed packed together and left to run for a fixed number of
    instructions -- no early exit -- so the numbers are rates, not times.  The
    question this is built for: are evolved replicators any less exploitable
    than the ancestor they descend from, or does the soup never get around to
    defending itself?
    """
    out = coculture_assay(parasite, host, budget=budget,
                          stop_at_first=False)["with_host"]
    parasite_births = out["guest_genotype_births"]
    host_births = out["host_genotype_births"] or 0
    total = parasite_births + host_births
    return {
        "parasite_births": parasite_births,
        "host_births": host_births,
        "captured_share": round(parasite_births / total, 3) if total else 0.0,
        "parasite_alive": out["population"].get(
            next(iter(k for k in out["population"] if True), None), 0),
        "instructions": out["instructions"],
    }


def phenotype_signature(genome: bytes, panel: list[bytes], budget: int = 200_000):
    """What a genome *does*, as opposed to what it is.

    Standish (2004) found that Tierra's phylogenies contained far fewer
    behaviours than genotypes -- tens of thousands of distinct genomes collapsed
    onto fewer than two hundred distinct phenotypes -- and that the way to tell
    two genotypes apart is to put each one through the same set of encounters
    and compare the outcomes.  This does that: the signature is what the genome
    is when cultured alone, what a daughter costs it, and what happens beside
    each reference organism in the panel.

    Two genotypes with the same signature are neutral variants of each other as
    far as anything in this world can tell.
    """
    what = describe(genome, budget=budget)
    encounters = tuple(interaction(genome, ref, budget=budget) for ref in panel)
    return (what["kind"], what["cost"], what["divides_without_copying"]) + encounters


def competition(genomes: dict[str, bytes], budget: int = 20_000_000,
                soup_size: int = 20_000, each: int = 12, layout: int = 0,
                samples: int = 20, cosmic_period: int | None = None,
                profile_each: int = 0, seed: int = 1) -> dict:
    """Put two or more genotypes in one soup and see which one takes it over.

    A cheaper replicator is only interesting if being cheaper actually wins, and
    that is not a given: a creature also has to survive the reaper, find room to
    allocate, and not be eaten.  This is the digital version of a competition
    assay -- equal numbers of each, interleaved so neither gets a better
    neighbourhood, and then simply count.

    ``cosmic_period`` adds background noise.  It is worth using: with mutation
    off this world is deterministic and finite, so it must eventually fall into
    a periodic orbit, and two genotypes can then sit in fixed proportions
    forever without that meaning selection cannot tell them apart.  A trickle of
    noise breaks the orbit and lets the contest resolve.
    """
    from .world import World

    w = World(soup_size=soup_size, seed=seed, copy_mutation_rate=0.0,
              cosmic_period=cosmic_period or 10 ** 18)
    names = list(genomes)
    labels: dict[str, str] = {}
    addr = 0
    for i in range(each):
        order = names[i % len(names):] + names[:i % len(names)] if layout else names
        for name in order:
            cr = w.inject(list(genomes[name]), address=addr, lineage=name)
            labels[cr.genotype] = name
            addr += len(genomes[name])

    def census():
        """Count by lineage, not by genotype.

        With any mutation at all the seeded genotypes disappear within a few
        million instructions -- not because they lost, but because their
        children are no longer bit-identical to them.  Counting descendants
        instead is what makes the contest answerable at all.
        """
        counts = {n: 0 for n in names}
        for cr in w.creatures:
            if cr.alive and cr.lineage in counts:
                counts[cr.lineage] += 1
        return counts

    history = []
    step = max(1, budget // samples)
    next_sample = 0
    while w.clock < budget and not w.extinct:
        w.step_generation()
        if w.clock >= next_sample:
            history.append({"clock": w.clock, **census()})
            next_sample += step
    final = census()
    total = sum(final.values()) or 1
    # Standing population is not the whole story: a faster replicator can have
    # produced far more daughters and still hold the same number of cells, if
    # what limits the population is memory rather than CPU.
    births = {n: w.lineage_births.get(n, 0) for n in names}
    # Two replicators sharing a soup are not necessarily just competing.  If one
    # of them is reaching into the other's code, that shows up here.
    foreign = {n: {"calls": 0, "reads": 0, "n": 0} for n in names}
    for cr in w.creatures:
        if cr.alive and cr.lineage in foreign:
            f = foreign[cr.lineage]
            f["calls"] += cr.stats.foreign_calls
            f["reads"] += cr.stats.foreign_reads
            f["n"] += 1
    for n in names:
        c = foreign[n]
        if c["n"]:
            c["calls_per_creature"] = round(c["calls"] / c["n"], 1)
            c["reads_per_creature"] = round(c["reads"] / c["n"], 1)
    return {
        "final": final,
        "share": {n: round(final[n] / total, 3) for n in names},
        "births": births,
        "winner": max(final, key=final.get),
        "foreign": foreign,
        "survivors": _survivor_profile(w, names, profile_each),
        "history": history,
        "instructions": w.clock,
    }


def _survivor_profile(w, names: list[str], sample_size: int) -> dict:
    """What is left of each lineage at the end, as behaviour rather than count.

    A lineage can be numerous and no longer carry the thing that made it
    interesting.  Sampling its living members and culturing each one says
    whether the innovation is still there: an unrolled copy loop shows up as a
    cost per cell below six, a reverted one as six and a half.
    """
    import random as _random

    if not sample_size:
        return {}
    rng = _random.Random(11)
    out = {}
    for name in names:
        members = [c for c in w.creatures if c.alive and c.lineage == name]
        if not members:
            out[name] = {"alive": 0}
            continue
        picked = rng.sample(members, min(sample_size, len(members)))
        kinds, per_cell = Counter(), []
        for cr in picked:
            what = describe(w.read_genome(cr.start, cr.size), budget=120_000)
            kinds[what["kind"]] += 1
            if what.get("cost_per_cell"):
                per_cell.append(what["cost_per_cell"])
        out[name] = {
            "alive": len(members),
            "sampled": len(picked),
            "kinds": dict(kinds),
            "replicator_share": round(kinds["replicator"] / len(picked), 2),
            "mean_cost_per_cell": (round(sum(per_cell) / len(per_cell), 2)
                                   if per_cell else None),
        }
    return out


def robustness(genome: bytes, budget: int = 150_000) -> dict:
    """How much of a genome's one-mutation neighbourhood still works.

    Every single-bit flip of every cell, cultured alone.  The fraction that
    still replicates is the genotype's *flatness*: how much of the space around
    it is habitable.  Quasispecies theory says selection acts on that
    neighbourhood, not only on the genotype itself, which is why a slower but
    flatter replicator can beat a faster but more fragile one when mutation is
    common -- survival of the flattest, in Wilke's phrase.

    Returns the fraction that still self-replicate, the fraction that are
    exactly as cheap as the parent, and both the mean and the median cost of
    the survivors -- the mean because a few catastrophically slow survivors say
    something real about the shape of the neighbourhood, the median because
    otherwise they say all of it.
    """
    parent = describe(genome, budget=budget)
    survivors, neutral, costs = 0, 0, []
    total = 0
    for i in range(len(genome)):
        for bit in range(5):
            mutant = bytearray(genome)
            mutant[i] ^= 1 << bit
            total += 1
            what = describe(bytes(mutant), budget=budget)
            if what["kind"] == "replicator":
                survivors += 1
                costs.append(what["cost"])
                if what["cost"] == parent["cost"] and len(mutant) == len(genome):
                    neutral += 1
    near = sum(1 for c in costs if parent["cost"] and c <= parent["cost"] * 1.1)
    ordered = sorted(costs)
    return {
        "cells": len(genome),
        "parent_cost": parent["cost"],
        "mutants": total,
        "still_replicate": survivors,
        "fraction_viable": round(survivors / total, 3) if total else 0.0,
        "fraction_neutral": round(neutral / total, 3) if total else 0.0,
        "fraction_within_10pc": round(near / total, 3) if total else 0.0,
        "mean_cost_of_survivors": round(sum(costs) / len(costs), 1) if costs else None,
        "median_cost_of_survivors": (ordered[len(ordered) // 2] if ordered else None),
    }
