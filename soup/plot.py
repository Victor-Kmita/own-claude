"""Small ASCII charts, so that results can live in a text file next to the code.

A picture that needs a plotting library, a browser and a screenshot is a picture
that will not be looked at when someone reads this repository three years from
now.  These render into a fenced code block and survive being pasted anywhere.
"""

from __future__ import annotations

BLOCKS = " ▁▂▃▄▅▆▇█"


def sparkline(values) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return BLOCKS[4] * len(values)
    span = hi - lo
    return "".join(BLOCKS[1 + int((v - lo) / span * (len(BLOCKS) - 2))] for v in values)


def line_chart(series: dict[str, list[float]], x: list[float] | None = None,
               height: int = 14, width: int = 74, ylabel: str = "",
               xlabel: str = "") -> str:
    """Overlay one or more series.  Each gets its own plotting character."""
    marks = "o+x*#"
    all_values = [v for s in series.values() for v in s]
    if not all_values:
        return "(no data)"
    lo, hi = min(all_values), max(all_values)
    if hi == lo:
        hi = lo + 1
    n = max(len(s) for s in series.values())
    width = min(width, max(n, 2))
    grid = [[" "] * width for _ in range(height)]

    for (name, values), mark in zip(series.items(), marks):
        for i, v in enumerate(values):
            col = int(i * (width - 1) / max(1, len(values) - 1))
            row = height - 1 - int((v - lo) / (hi - lo) * (height - 1))
            grid[row][col] = mark

    label_w = max(len(f"{hi:,.1f}"), len(f"{lo:,.1f}")) + 1
    out = []
    for r, row in enumerate(grid):
        value = hi - (hi - lo) * r / (height - 1)
        tick = f"{value:>{label_w},.1f}" if r in (0, height - 1, height // 2) else " " * label_w
        out.append(f"{tick} |{''.join(row)}")
    out.append(" " * label_w + " +" + "-" * width)
    if x:
        left, right = f"{x[0]:,.0f}", f"{x[-1]:,.0f}"
        axis = left + " " * max(1, width - len(left) - len(right)) + right
        out.append(" " * (label_w + 2) + axis)
    if xlabel:
        out.append(" " * (label_w + 2) + xlabel.center(width).rstrip())
    legend = "   ".join(f"{m} {name}" for (name, _), m in zip(series.items(), marks))
    header = f"{ylabel}" if ylabel else ""
    return (f"{header}\n" if header else "") + "\n".join(out) + f"\n{' ' * (label_w + 2)}{legend}"


def histogram(counts: dict, width: int = 40, sort_by_key: bool = True) -> str:
    if not counts:
        return "(empty)"
    items = sorted(counts.items()) if sort_by_key else sorted(
        counts.items(), key=lambda kv: -kv[1])
    top = max(counts.values())
    keyw = max(len(str(k)) for k in counts)
    out = []
    for k, v in items:
        bar = "█" * max(1, int(v / top * width)) if v else ""
        out.append(f"{str(k):>{keyw}} | {bar} {v}")
    return "\n".join(out)
