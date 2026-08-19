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
    first daughter when alone.  For the ancestor that is 420, and it is the
    number to beat: every instruction saved is a slice of CPU that goes into
    reproducing instead of bookkeeping.
    """
    alone = isolation_assay(genome, budget=budget, copies=1)
    if alone["self_sufficient"]:
        return {"kind": "replicator", "cost": alone["instructions"],
                "cost_paired": None}
    pair = isolation_assay(genome, budget=budget, copies=2)
    if pair["self_sufficient"]:
        return {"kind": "self-assisted", "cost": None,
                "cost_paired": pair["instructions"]}
    kind = "host-dependent" if _has_reproductive_machinery(genome) else "inert"
    return {"kind": kind, "cost": None, "cost_paired": None}


def classify(genome: bytes, budget: int = 500_000) -> str:
    """One of: replicator, self-assisted, host-dependent, inert."""
    return describe(genome, budget=budget)["kind"]


def coculture_assay(guest: bytes, host: bytes, budget: int = 500_000,
                    soup_size: int = 6000, gap: int = 0) -> dict:
    """Koch's postulates for a digital parasite.

    Put one guest next to one host in a sterile soup and count who divides.
    Run the same thing with the host left out.  If the guest reproduces only
    when the host is present, and the reproduction is achieved by executing code
    that lies outside the guest's own genome, then the guest is living off the
    host -- not by analogy, but in the plain mechanical sense.

    ``gap`` is the number of empty cells between the two genomes, and it is not
    a detail.  A template search takes the *nearest* match, so a parasite whose
    own body contains a competing pattern only reaches its host when the host is
    closer than that pattern.  The allocator packs live creatures back to back,
    so ``gap=0`` is what the soup actually looks like; larger gaps are a way to
    ask how far infection can reach.
    """
    from .world import World

    guest_like, host_like = guest, host

    def trial(genomes):
        w = World(soup_size=soup_size, copy_mutation_rate=0.0,
                  cosmic_period=10 ** 12, seed=999, filler=OPCODE["zero"])
        crs = []
        addr = 0
        for g in genomes:
            crs.append(w.inject(list(g), address=addr))
            addr += len(g) + gap
        births = {c.cid: 0 for c in crs}
        while w.clock < budget:
            w.step_generation()
            for c in crs:
                births[c.cid] = c.stats.births
            if births[crs[0].cid] > 0:
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
        for (child, parent), n in w.genebank.parent_births.items():
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
        }

    return {
        "with_host": trial([guest, host]),
        "alone": trial([guest]),
        "with_own_kind": trial([guest, guest]),
    }


def interaction(guest: bytes, host: bytes, budget: int = 500_000) -> str:
    """What one genotype does to another when they are neighbours.

    ``parasitism``  the guest reproduces *itself* using the host's code.
    ``hijacked``    the guest reproduces the *host*: its CPU has been captured.
    ``mixed``       both happen.
    ``none``        the guest does not reproduce next to this host.
    """
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
