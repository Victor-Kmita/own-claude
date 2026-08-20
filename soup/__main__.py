"""Command line front end:  python3 -m soup <command>"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from . import analysis, experiment
from .asm import assemble, disassemble

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO, "experiments", "results")
ANCESTORS = os.path.join(REPO, "experiments", "ancestors")


def ancestor_path(name: str | None) -> str:
    """Resolve --ancestor to a file in experiments/ancestors, and nowhere else.

    A bare name, not a path: the task queue in ``lab/`` passes this straight
    through from a file written by the other agent, and a queue that can name
    any file on disk is a queue that can read any file on disk.
    """
    if not name:
        return experiment.ANCESTOR
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise SystemExit(f"bad ancestor name {name!r}: letters, digits, - and _ only")
    path = os.path.join(ANCESTORS, f"{name}.sm")
    if not os.path.exists(path):
        raise SystemExit(f"no such ancestor: {path}")
    return path


def cmd_run(args) -> None:
    os.makedirs(args.out, exist_ok=True)
    result = experiment.run(
        name=args.name, instructions=args.instructions, seed=args.seed,
        soup_size=args.soup, slice_size=args.slice_size, slice_pow=args.slice_pow,
        copy_mutation_rate=(1 / args.copy_mutation if args.copy_mutation else 0.0),
        cosmic_period=(args.cosmic if args.cosmic else 10 ** 18),
        sample_every=args.sample_every, reap_threshold=args.reap_threshold,
        search_limit=args.search_limit,
        reap_on_alloc_failure=not args.lazy_reaper, flaw_period=args.flaw,
        ancestor_path=ancestor_path(args.ancestor),
        checkpoint_path=os.path.join(args.out, f"{args.name}.checkpoint.json"),
    )
    path = experiment.save(result, args.out)
    print(f"\nwrote {path}  ({result['instructions_per_sec']:,} instructions/sec)")
    print_census(result)


def print_census(result: dict) -> None:
    print(f"\n{'genotype':>9} {'n':>4} {'size':>5} {'births':>7} {'fid':>5} "
          f"{'kind':>13} {'cost':>6}  {'fcalls':>7} parent")
    for row in result["census"]:
        cost = row.get("cost")
        print(f"{row['genotype']:>9} {row['n']:>4} {row['size']:>5} {row['births']:>7} "
              f"{row['fidelity']:>5.2f} {row['kind']:>13} "
              f"{(str(cost) if cost else '-'):>6}  "
              f"{row['mean_foreign_calls']:>7.0f} {row['parent']}")


def cmd_show(args) -> None:
    with open(args.result) as fh:
        result = json.load(fh)
    genome = result["genomes"].get(args.genotype)
    if genome is None:
        sys.exit(f"{args.genotype} is not in {args.result}")
    print(f"; {args.genotype}  ({len(genome)} instructions)")
    print(disassemble(genome))
    if args.against:
        other = result["genomes"].get(args.against) or experiment.load_ancestor()
        print(f"\n; difference from {args.against}:")
        print(analysis.genome_diff(bytes(other), bytes(genome)))


def cmd_assay(args) -> None:
    with open(args.result) as fh:
        result = json.load(fh)
    genome = bytes(result["genomes"][args.genotype])
    alone = analysis.isolation_assay(genome, copies=1)
    pair = analysis.isolation_assay(genome, copies=2)
    print(f"{args.genotype}: alone={alone}\n{' ' * len(args.genotype)}  paired={pair}")
    print("verdict:", analysis.classify(genome))


def cmd_trace(args) -> None:
    genome = _genome(args.result, args.genotype)
    neighbours = [_genome(args.result, g) for g in (args.with_ or [])]
    rows = analysis.trace(genome, steps=args.steps, neighbours=neighbours)
    print(analysis.trace_summary(rows, collapse=not args.full))


def cmd_coculture(args) -> None:
    guest = _genome(args.result, args.genotype)
    host = _genome(args.result, args.host)
    out = analysis.coculture_assay(guest, host, gap=args.gap)
    print(f"guest {args.genotype} ({len(guest)} cells), host {args.host} ({len(host)} cells)")
    for setting in ("with_host", "with_own_kind", "alone"):
        r = out[setting]
        print(f"  {setting:<14} guest births={r['guest_births']}  "
              f"foreign calls={r['guest_foreign_calls']}  "
              f"foreign reads={r['guest_foreign_reads']}  "
              f"instructions={r['instructions']:,}  "
              f"offspring={dict(r['offspring']) or '{}'}")


def _genome(result_path: str, genotype: str) -> bytes:
    if genotype in ("ancestor", "-"):
        return bytes(experiment.load_ancestor())
    with open(result_path) as fh:
        result = json.load(fh)
    if genotype not in result["genomes"]:
        sys.exit(f"{genotype} is not in {result_path}; "
                 f"available: {', '.join(sorted(result['genomes']))}")
    return bytes(result["genomes"][genotype])


def cmd_interactions(args) -> None:
    with open(args.result) as fh:
        result = json.load(fh)
    genomes = {k: bytes(v) for k, v in result["genomes"].items()}
    kinds = {row["genotype"]: row["kind"] for row in result["census"]}
    # "parasite" is the old name for "host-dependent"; results saved before the
    # rename still use it.
    guests = [g for g, k in kinds.items()
              if k in ("host-dependent", "self-assisted", "parasite")]
    hosts = [g for g, k in kinds.items() if k == "replicator"]
    genomes["ancestor"] = bytes(experiment.load_ancestor())
    hosts = hosts + ["ancestor"]
    if not guests:
        print("no host-dependent genotypes in this result")
        return
    matrix = analysis.interaction_matrix(genomes, guests, hosts)
    code = {"parasitism": "P", "hijacked": "H", "mixed": "M", "other": "o",
            "none": "."}
    print("           " + " ".join(f"{h[-4:]:>4}" for h in hosts))
    for g, row in matrix.items():
        cells = " ".join(f"{code.get(row.get(h, ''), ' '):>4}" for h in hosts)
        print(f"{g:>9}  {cells}   ({kinds[g]})")
    print("\ncolumns are hosts (last four characters of each label)")
    print("P = guest copies itself using the host's code (parasitism)")
    print("H = guest spends its own CPU copying the host (its CPU was captured)")
    print("M = both;  . = the guest does not reproduce beside this host")


def cmd_resistance(args) -> None:
    with open(args.result) as fh:
        result = json.load(fh)
    genomes = {k: bytes(v) for k, v in result["genomes"].items()}
    genomes["ancestor"] = bytes(experiment.load_ancestor())
    kinds = {row["genotype"]: row["kind"] for row in result["census"]}
    hosts = [g for g, k in kinds.items() if k == "replicator"] + ["ancestor"]
    parasites = args.parasites or [
        g for g, k in kinds.items()
        if k in ("host-dependent", "self-assisted", "parasite")]
    print(f"{'host':>10} {'size':>5} {'births alone':>13} {'births infected':>16} "
          f"{'parasite births':>16} {'captured':>9}")
    for h in hosts:
        rows = [analysis.susceptibility(genomes[h], genomes[p], budget=args.budget)
                for p in parasites]
        alone = analysis.solo_rate(genomes[h], budget=args.budget)
        infected = sum(r["host_births"] for r in rows) / len(rows)
        stolen = sum(r["parasite_births"] for r in rows) / len(rows)
        share = sum(r["captured_share"] for r in rows) / len(rows)
        print(f"{h:>10} {len(genomes[h]):>5} {alone:>13} {infected:>16.1f} "
              f"{stolen:>16.1f} {share:>9.1%}")
    print(f"\nmean over {len(parasites)} parasites, "
          f"{args.budget:,} instructions per pairing")


def cmd_ancestor(args) -> None:
    code = experiment.load_ancestor()
    print(f"; ancestor, {len(code)} instructions")
    print(disassemble(code))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="soup", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run an experiment and save the history")
    r.add_argument("name")
    r.add_argument("--instructions", type=int, default=50_000_000)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--soup", type=int, default=60_000)
    r.add_argument("--slice-size", type=float, default=20,
               help="instructions per turn; multiplied by size**slice_pow")
    r.add_argument("--slice-pow", type=float, default=0.0,
                   help="0 = every creature gets the same CPU slice (small is fast); "
                        "1 = slice proportional to genome length (size neutral)")
    r.add_argument("--copy-mutation", type=int, default=1000,
                   help="one copy error per N cells copied; 0 disables")
    r.add_argument("--cosmic", type=int, default=2000,
                   help="one random bit flip per N instructions executed")
    r.add_argument("--ancestor", default=None,
                   help="start from an evolved genome in experiments/ancestors "
                        "instead of the hand-written ancestor, by name")
    r.add_argument("--sample-every", type=int, default=1_000_000)
    r.add_argument("--reap-threshold", type=float, default=0.8)
    r.add_argument("--search-limit", type=int, default=1024)
    r.add_argument("--flaw", type=int, default=0,
                   help="one instruction in N produces a result off by one "
                        "(Tierra's third mutation mode); 0 disables")
    r.add_argument("--lazy-reaper", action="store_true",
                   help="do not reap when an allocation fails; the soup then "
                        "sits full and mal failures become a mutagen")
    r.add_argument("--out", default=RESULTS)
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("show", help="disassemble a genotype from a saved result")
    s.add_argument("result")
    s.add_argument("genotype")
    s.add_argument("--against", nargs="?", const="ancestor")
    s.set_defaults(func=cmd_show)

    a = sub.add_parser("assay", help="culture a genotype alone and in a pair")
    a.add_argument("result")
    a.add_argument("genotype")
    a.set_defaults(func=cmd_assay)

    t = sub.add_parser("trace", help="single-step a genotype and show what it does")
    t.add_argument("result")
    t.add_argument("genotype")
    t.add_argument("--steps", type=int, default=800)
    t.add_argument("--full", action="store_true", help="do not collapse loops")
    t.add_argument("--with", dest="with_", nargs="*",
                   help="genotypes to place beside it in the soup")
    t.set_defaults(func=cmd_trace)

    c = sub.add_parser("coculture", help="test a suspected parasite against a host")
    c.add_argument("result")
    c.add_argument("genotype")
    c.add_argument("host")
    c.add_argument("--gap", type=int, default=0,
                   help="empty cells between guest and host (0 = packed, as the "
                        "allocator leaves them)")
    c.set_defaults(func=cmd_coculture)

    m = sub.add_parser("interactions", help="cross dependents against replicators")
    m.add_argument("result")
    m.set_defaults(func=cmd_interactions)

    x = sub.add_parser("resistance", help="how exploitable is each host")
    x.add_argument("result")
    x.add_argument("--budget", type=int, default=200_000)
    x.add_argument("--parasites", nargs="*")
    x.set_defaults(func=cmd_resistance)

    n = sub.add_parser("ancestor", help="print the ancestor listing")
    n.set_defaults(func=cmd_ancestor)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
