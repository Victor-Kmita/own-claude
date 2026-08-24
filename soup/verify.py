"""Check this repository's own claims against this machine.

Four of the nineteen findings in README.md have been rewritten after checking,
and three times the fault was the measuring instrument rather than the world.
So the claims are also kept as data, in ``claims.json``, each with a check that
runs here and now.  ``python3 -m soup verify`` runs them and prints a table.

This is the part of the project meant to travel.  Somebody who finds this
repository -- a person, or another agent with its own machine and no reason to
trust mine -- should be able to establish which claims still hold before
reading a word of the write-up, and should get a non-zero exit code if any of
them does not.
"""

from __future__ import annotations

import json
import os
import random

from .analysis import describe, isolation_assay, robustness, sustained_cost
from .asm import assemble
from .experiment import load_ancestor, sample
from .world import World

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CLAIMS = os.path.join(HERE, "claims.json")
ANCESTORS = os.path.join(REPO, "experiments", "ancestors")

TIERS = ("fast", "full", "deep")


def load_claims() -> dict:
    with open(CLAIMS) as fh:
        return json.load(fh)


def genome_named(name: str) -> bytes:
    if name == "ancestor":
        return bytes(load_ancestor())
    with open(os.path.join(ANCESTORS, f"{name}.sm")) as fh:
        return bytes(assemble(fh.read()))


def within(value, bound) -> bool:
    """A bound is either an exact value or a [low, high] pair, inclusive."""
    if isinstance(bound, list):
        return value is not None and bound[0] <= value <= bound[1]
    return value == bound


# -- the checks --------------------------------------------------------------
# Each returns (ok, one line saying what was actually measured).

def check_describe_ancestor(claim: dict) -> tuple[bool, str]:
    what = describe(bytes(load_ancestor()))
    ok = all(within(what.get(k), v) for k, v in claim["expect"].items())
    return ok, (f"cost {what['cost']}, second {what['second_copy_cost']}, "
                f"repeats {what['repeats']}")


def check_describe_ancestor_file(claim: dict) -> tuple[bool, str]:
    what = describe(genome_named(claim["genome"]))
    ok = all(within(what.get(k), v) for k, v in claim["expect"].items())
    return ok, (f"cost {what['cost']}, repeats {what['repeats']}, "
                f"{what['cost_per_cell']} per cell")


def check_sustained(claim: dict) -> tuple[bool, str]:
    got = sustained_cost(genome_named(claim["genome"]))
    ok = all(within(got.get(k), v) for k, v in claim["expect"].items())
    return ok, (f"{got['instructions_per_birth']} instructions per birth, "
                f"{got['errors_per_creature']} errors per creature")


def check_deletions(claim: dict) -> tuple[bool, str]:
    genome = genome_named(claim["genome"])
    parent = describe(genome)
    viable, repeating, cheapest = 0, 0, None
    for i in range(len(genome)):
        shorter = genome[:i] + genome[i + 1:]
        what = describe(shorter, budget=60_000)
        # A "replicator" needing forty instructions per cell wandered into a
        # division; the real ones run at under seven.
        if what["kind"] != "replicator" or what["cost"] >= 40 * len(shorter):
            continue
        viable += 1
        if what["repeats"]:
            repeating += 1
        if cheapest is None or what["cost"] < cheapest:
            cheapest = what["cost"]
    got = {"viable": viable, "repeating": repeating,
           "cheapest_below_parent": cheapest is not None and cheapest < parent["cost"]}
    ok = all(within(got.get(k), v) for k, v in claim["expect"].items())
    return ok, (f"{viable} of {len(genome)} deletions replicate, {repeating} repeat, "
                f"cheapest {cheapest} against the parent's {parent['cost']}")


def check_determinism(claim: dict) -> tuple[bool, str]:
    def trajectory(every: int):
        w = World(soup_size=6000, seed=42, copy_mutation_rate=1 / 800,
                  cosmic_period=1500, flaw_period=1000)
        w.inject(load_ancestor(), address=0)
        history, due = [sample(w)], every
        while w.clock < 300_000:
            w.step_generation()
            if w.clock >= due:
                history.append(sample(w))
                due += every
        return history, (w.births, w.deaths, sorted(w.population().items()))

    dense, end_dense = trajectory(25_000)
    sparse, end_sparse = trajectory(100_000)
    by_clock = {h["clock"]: h for h in dense}
    shared = [h for h in sparse if h["clock"] in by_clock]
    same = all(by_clock[h["clock"]] == h for h in shared)
    ok = end_dense == end_sparse and same and len(shared) > 1
    return ok, (f"{end_dense[0]} births both times, {len(shared)} shared snapshots "
                f"{'identical' if same else 'DIFFERENT'}")


def _first_daughter(seed: int, **params):
    """One mother, alone, to her first daughter.  Returns (mother, daughter)."""
    w = World(soup_size=4000, seed=seed, **params)
    if w.flaw_period:
        w.flaw_countdown = random.Random(seed).randrange(1, w.flaw_period + 1)
    w.inject(load_ancestor(), address=0)
    mother = w.creatures[0]
    while w.clock < 40_000 and not w.extinct and mother.stats.births == 0:
        w.step_generation()
    if mother.stats.births == 0:
        return None
    kids = [c for c in w.creatures if c is not mother]
    if not kids:
        return None
    read = lambda cr: bytes(w.soup[(cr.start + i) % w.soup_size] for i in range(cr.size))
    return read(mother), read(kids[0])


def check_heritability(claim: dict) -> tuple[bool, str]:
    trials = 220
    out = {}
    for label, params in (("copy", dict(copy_mutation_rate=1 / 83,
                                        cosmic_period=10 ** 9, flaw_period=0)),
                          ("flaw", dict(copy_mutation_rate=0.0,
                                        cosmic_period=10 ** 9, flaw_period=250))):
        altered = [c for m, c in
                   (p for p in (_first_daughter(s, **params)
                                for s in range(1, trials + 1)) if p)
                   if c != m]
        works = sum(1 for g in altered
                    if describe(g, budget=20_000)["kind"] == "replicator")
        out[label] = (works / len(altered) if altered else 0.0, len(altered))
    copy_v, flaw_v = out["copy"][0], out["flaw"][0]
    ok = (within(copy_v, claim["expect"]["copy_viable"])
          and within(flaw_v, claim["expect"]["flaw_viable"])
          and (flaw_v == 0 or copy_v / flaw_v >= claim["expect"]["ratio_at_least"]))
    return ok, (f"altered daughters still replicate: copy {copy_v:.0%} "
                f"(n={out['copy'][1]}), flaw {flaw_v:.0%} (n={out['flaw'][1]})")


def check_spectrum(claim: dict) -> tuple[bool, str]:
    trials = 500
    counts = {}
    for label, params in (("copy", dict(copy_mutation_rate=1 / 83,
                                        cosmic_period=10 ** 9, flaw_period=0)),
                          ("cosmic", dict(copy_mutation_rate=0.0,
                                          cosmic_period=200, flaw_period=0)),
                          ("flaw", dict(copy_mutation_rate=0.0,
                                        cosmic_period=10 ** 9, flaw_period=250))):
        pairs = [p for p in (_first_daughter(s, **params)
                             for s in range(1, trials + 1)) if p]
        counts[label] = sum(1 for m, c in pairs if len(c) != len(m))
    ok = (counts["copy"] == claim["expect"]["copy_length_changes"]
          and counts["cosmic"] == claim["expect"]["cosmic_length_changes"]
          and counts["flaw"] >= claim["expect"]["flaw_length_changes_at_least"])
    return ok, (f"daughters of a different length: copy {counts['copy']}, "
                f"cosmic {counts['cosmic']}, flaw {counts['flaw']} of {trials}")


def check_none(claim: dict) -> tuple[bool, str]:
    return True, "superseded; kept for the record"


CHECKS = {
    "describe_ancestor": check_describe_ancestor,
    "describe_ancestor_file": check_describe_ancestor_file,
    "sustained": check_sustained,
    "deletions": check_deletions,
    "determinism": check_determinism,
    "heritability": check_heritability,
    "spectrum": check_spectrum,
    "none": check_none,
}


def verify(tier: str = "fast", only: str | None = None) -> int:
    """Run every claim at or below ``tier``.  Returns a process exit code."""
    doc = load_claims()
    wanted = TIERS[:TIERS.index(tier) + 1]
    failed, ran, skipped = 0, 0, 0

    print(f"soup: checking claims at tier '{tier}' and below\n")
    for claim in doc["claims"]:
        if only and claim["id"] != only:
            continue
        if claim["tier"] not in wanted:
            skipped += 1
            continue
        name = claim["id"]
        if claim.get("status") == "superseded":
            print(f"  ~  {name:36} superseded -- {claim['claim'].split('.')[1].strip()[:60]}")
            continue
        check = CHECKS.get(claim.get("check", "none"))
        if check is None:
            print(f"  ?  {name:36} no check named {claim.get('check')!r}")
            failed += 1
            continue
        ran += 1
        try:
            ok, detail = check(claim)
        except Exception as exc:                       # a broken check is a failure
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        failed += not ok
        print(f"  {'ok' if ok else 'NO':>2} {name:36} {detail}")

    deep = [c for c in doc["claims"] if c["tier"] == "deep" and c["tier"] not in wanted]
    if deep:
        print(f"\n  {len(deep)} claim(s) need hours of compute and were not run. "
              f"To check them:")
        for claim in deep:
            print(f"     {claim['command']}")

    print(f"\n{ran} checked, {failed} failed, {skipped} above this tier.")
    if failed:
        print("A failure here means the README is wrong, or this machine is, "
              "or the simulator changed under a claim. All three have happened.")
    return 1 if failed else 0
