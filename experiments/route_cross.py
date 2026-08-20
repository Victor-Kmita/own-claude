"""Start a run from an evolved champion instead of from the hand-written ancestor.

Finding 17 says the two mutation regimes reach the floor by different routes.
Without flaws the copy loop unrolls -- 5.68 instructions per cell -- and the
genome stops at 38 cells.  With flaws the genome falls to 27 cells and the loop
never improves, staying at the ancestor's 6.4 per cell.  Neither run has ever
produced a creature with both gains.

This crosses them: take the champion of one route as the starting organism and
apply the other route's mutation regime.  If the two gains simply never met,
the unrolled genome should now shrink and the short genome should now unroll.
If each excludes the other, neither will move.

    python3 experiments/route_cross.py <ancestor> <flaw-period> <seed> [instructions]

``ancestor`` names a file in ``experiments/ancestors/``.  There is a
``soup run --ancestor`` that does the same thing; this script exists as well
because the task queue on the compute server validates parameters against a
whitelist, and a worker process that has been running since before that
whitelist gained the ancestor parameter cannot accept it.  A script is the one
thing such a worker will still run, and the script is committed code that can be
read before it executes, which is what the protocol asks for.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup import experiment

HERE = os.path.dirname(os.path.abspath(__file__))
ANCESTORS = os.path.join(HERE, "ancestors")
RESULTS = os.path.join(HERE, "results")


def main(argv: list[str]) -> None:
    if not 3 <= len(argv) <= 4:
        raise SystemExit(__doc__)
    name, flaw, seed = argv[0], int(argv[1]), int(argv[2])
    instructions = int(argv[3]) if len(argv) == 4 else 1_000_000_000
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise SystemExit(f"bad ancestor name {name!r}")
    path = os.path.join(ANCESTORS, f"{name}.sm")
    if not os.path.exists(path):
        raise SystemExit(f"no such ancestor: {path}")

    run_name = f"from-{name}-flaw{flaw}-s{seed}"
    result = experiment.run(
        name=run_name, instructions=instructions, seed=seed,
        flaw_period=flaw, sample_every=10_000_000, ancestor_path=path,
        checkpoint_path=os.path.join(RESULTS, f"{run_name}.checkpoint.json"),
    )
    out = experiment.save(result, RESULTS)
    print(f"\nwrote {out}  ({result['instructions_per_sec']:,} instructions/sec)")


if __name__ == "__main__":
    main(sys.argv[1:])
