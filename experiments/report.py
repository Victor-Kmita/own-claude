"""Turn saved run histories into a readable report.

Usage:  python3 experiments/report.py [> experiments/REPORT.md]

Everything printed here is read out of the JSON files in results/; nothing is
recomputed and nothing is rounded by hand, so the report cannot drift away from
the runs it describes.
"""

from __future__ import annotations

import glob
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup.plot import histogram, line_chart

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(pattern: str) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(RESULTS, pattern))):
        with open(path) as fh:
            data = json.load(fh)
        # Skip the standalone sweeps (no config) and the checkpoints written by
        # runs that are still going (config and history, but no totals yet).
        if "config" in data and "totals" in data:
            out.append(data)
    return out


def tail(history: list[dict], key: str, frac: float = 0.3) -> list[float]:
    cut = int(len(history) * (1 - frac))
    return [row[key] for row in history[cut:]]


def table(headers: list[str], rows: list[list]) -> str:
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
              for i, h in enumerate(headers)]
    out = ["| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)) + " |",
           "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


STANDARD = {"copy_mutation_rate": 1 / 1000, "cosmic_period": 2000}


def is_standard(run: dict) -> bool:
    """Standard mutation, no flaws -- the runs the length comparison is about."""
    c = run["config"]
    return (c["copy_mutation_rate"] == STANDARD["copy_mutation_rate"]
            and c["cosmic_period"] == STANDARD["cosmic_period"]
            and not c.get("flaw_period"))


def length_by_condition(runs: list[dict]) -> str:
    """The comparison the runs were done for, on one line per condition.

    Only runs at the standard mutation rate and without instruction flaws: the
    mutation-rate sweep and the flaw sweep vary something else on purpose, and
    averaging them in here would say nothing about the scheduler.
    """
    groups: dict[str, list] = {}
    for r in runs:
        if r["config"]["copy_mutation_rate"] == 0 or not is_standard(r):
            continue
        h = r["history"]
        groups.setdefault(condition_of(r), []).append(
            round(st.mean(tail(h, "mean_size")), 1))
    return table(["condition", "runs", "mean genome length in each run"],
                 [[name, len(v), ", ".join(str(x) for x in sorted(v))]
                  for name, v in sorted(groups.items())])


def summary_section(runs: list[dict]) -> str:
    rows = []
    for r in runs:
        h = r["history"]
        rows.append([
            r["name"], r["config"]["slice_pow"], r["config"]["seed"],
            r["config"].get("flaw_period") or "-",
            f"{r['config']['instructions'] / 1e6:.0f}M",
            round(st.mean(tail(h, "mean_size")), 1),
            round(st.mean(tail(h, "genotypes"))),
            round(st.mean(tail(h, "diversity")), 2),
            round(st.mean(tail(h, "alive"))),
            round(st.mean(tail(h, "foreign_breeder_share")), 2)
            if "foreign_breeder_share" in h[-1] else "-",
            r["totals"]["births"],
            r["totals"]["genotypes_seen"],
        ])
    return table(["run", "slice_pow", "seed", "flaws", "length", "mean size", "types alive",
                  "diversity H", "alive", "foreign breeders", "births", "types seen"],
                 rows)


def chart_section(runs: list[dict], key: str, ylabel: str) -> str:
    series = {r["name"]: [row[key] for row in r["history"]] for r in runs}
    x = [row["clock"] for row in runs[0]["history"]]
    return line_chart(series, x=x, ylabel=ylabel, xlabel="instructions executed",
                      height=15, width=76)


def condition_of(run: dict) -> str:
    if run["config"]["copy_mutation_rate"] == 0:
        return "no mutation (control)"
    if run["config"].get("flaw_period"):
        return f"instruction flaws, one in {run['config']['flaw_period']:,}"
    if run["config"]["slice_pow"] == 0:
        return "constant CPU slice"
    # The first proportional run used a slice four times larger in absolute
    # terms; it is kept, but not averaged in with the matched ones.
    if run["config"]["slice_size"] >= 1:
        return "slice proportional (unmatched pilot)"
    return "slice proportional to length"


def chart_conditions(runs: list[dict], key: str, ylabel: str) -> str:
    """Average the seeds within each condition, then plot one line per condition.

    Individual seeds wander a long way; the comparison that means anything is
    between conditions, so that is what gets drawn.
    """
    groups: dict[str, list[dict]] = {}
    for r in runs:
        groups.setdefault(condition_of(r), []).append(r)
    series = {}
    for name, members in groups.items():
        n = min(len(m["history"]) for m in members)
        series[f"{name} (n={len(members)})"] = [
            st.mean(m["history"][i][key] for m in members) for i in range(n)
        ]
    x = [row["clock"] for row in runs[0]["history"]]
    return line_chart(series, x=x, ylabel=ylabel, xlabel="instructions executed",
                      height=15, width=76)


def census_section(run: dict) -> str:
    rows = [[c["genotype"], c["n"], c["size"], c["births"], c["fidelity"],
             c["kind"], c.get("cost") or "-", c["mean_foreign_calls"], c["parent"]]
            for c in run["census"]]
    return table(["genotype", "alive", "size", "births", "fidelity", "kind",
                  "cost", "foreign calls", "first parent"], rows)


def fragmentation_section() -> str:
    path = os.path.join(RESULTS, "fragmentation.json")
    if not os.path.exists(path):
        return "(not run)"
    with open(path) as fh:
        data = json.load(fh)
    rows = [[r["reaper"], r["errors_hasten_death"], r["soup_size"], r["alive"],
             r["births"], r["alloc_failures"], r["alloc_failures_per_birth"],
             r["genotypes_seen"], r["mean_size"]] for r in data["rows"]]
    out = ["Mechanism: " + data.get("mechanism", ""), "",
           table(["reaper", "errors hasten death", "soup cells", "alive",
                  "births", "mal failures", "per birth", "genotypes seen",
                  "mean size"], rows)]
    deep = data.get("deep")
    if deep:
        out += ["", f"Deeper look: soup of {deep['soup_size']:,} cells, "
                    f"{deep['budget']:,} instructions.", "",
                table(["reaper", "errors hasten death", "mal failures",
                       "genotypes seen", "mean size", "max size"],
                      [[r["reaper"], r["errors_hasten_death"],
                        r["alloc_failures"], r["genotypes_seen"],
                        r["mean_size"], r["max_size"]] for r in deep["rows"]])]
    return "\n".join(out)


def main() -> None:
    runs = load("*.json")
    if not runs:
        sys.exit("no results in " + RESULTS)
    hundred = [r for r in runs
               if r["config"]["instructions"] == 100_000_000 and is_standard(r)]
    long_runs = [r for r in runs
                 if r["config"]["instructions"] == 400_000_000 and is_standard(r)]
    deep_runs = [r for r in runs if r["config"]["instructions"] >= 1_000_000_000]

    print("# Results\n")
    print("Generated by `python3 experiments/report.py` from the JSON files in "
          "`experiments/results/`.\n")
    print("## Genome length by scheduling rule\n")
    print("The ancestor is 64 instructions long.  Every mutating run is "
          "averaged over its last 30%.\n")
    print(length_by_condition(runs))
    print("\n## Every run\n")
    print(summary_section(runs))

    if hundred:
        print("\n## Mean genome length over time, by condition (100M runs, "
              "seeds averaged)\n")
        print("```")
        print(chart_conditions(hundred, "mean_size", "cells"))
        print("```")
        print("\n## Genotypes alive at once\n")
        print("```")
        print(chart_conditions(hundred, "genotypes", "distinct genotypes"))
        print("```")
        print("\n## Share of reproducing creatures that executed foreign code\n")
        print("```")
        print(chart_conditions([r for r in hundred
                                if "foreign_breeder_share" in r["history"][-1]],
                               "foreign_breeder_share", "fraction"))
        print("```")

    if long_runs:
        print("\n## 400M runs: mean genome length\n```")
        print(chart_conditions(long_runs, "mean_size", "cells"))
        print("```")
        print("\n## Long runs: genotypes alive\n```")
        print(chart_conditions(long_runs, "genotypes", "distinct genotypes"))
        print("```")

    if deep_runs:
        print("\n## Deep runs: does genome length keep falling?\n")
        print("Ray's Tierra reached a 36-instruction descendant after fifteen "
              "billion instructions.\nThese are three billion.\n")
        print("```")
        print(chart_conditions(deep_runs, "mean_size", "cells"))
        print("```")
        print("\n### Generation depth\n```")
        print(chart_conditions(deep_runs, "mean_generation", "generations"))
        print("```")

    print("\n## Housekeeping policy as an evolutionary force "
          "(all mutation switched off)\n")
    print(fragmentation_section())

    for r in runs:
        print(f"\n## Final census: {r['name']}\n")
        print(census_section(r))
        sizes = {}
        for row in r["history"][-1].get("size_hist", {}).items():
            sizes[int(row[0])] = row[1]
        if sizes:
            print("\nGenome lengths alive at the end:\n")
            print("```")
            print(histogram(sizes))
            print("```")


if __name__ == "__main__":
    main()
