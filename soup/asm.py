"""Assembler and disassembler for soup machine code.

The source language is deliberately thin -- one instruction per token, ``;`` to
end-of-line comments, and one piece of sugar: ``.t 1011`` expands to the nop run
``nop1 nop0 nop1 nop1``.  Templates are written as bit strings because that is
how you have to think about them when you are hand-writing a self-replicator:
the question is never "what address" but "which pattern, and does anything else
in the genome accidentally match it".

Labels (``name:``) are allowed but carry no semantics; they exist so that the
listing produced by :func:`disassemble` can be read next to the source.
"""

from __future__ import annotations

from .isa import (
    INSTRUCTIONS,
    NOP0,
    NOP1,
    OPCODE,
    TEMPLATE_INSTRUCTIONS,
    is_nop,
    template_str,
)


class AssemblyError(ValueError):
    pass


def assemble(source: str) -> list[int]:
    """Turn source text into a list of opcodes."""
    code: list[int] = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.endswith(":"):           # label, purely decorative
                i += 1
                continue
            if tok == ".t":
                if i + 1 >= len(tokens):
                    raise AssemblyError(f"line {lineno}: .t needs a bit string")
                bits = tokens[i + 1]
                if not bits or set(bits) - {"0", "1"}:
                    raise AssemblyError(f"line {lineno}: bad template {bits!r}")
                code.extend(NOP1 if b == "1" else NOP0 for b in bits)
                i += 2
                continue
            if tok not in OPCODE:
                raise AssemblyError(f"line {lineno}: unknown instruction {tok!r}")
            code.append(OPCODE[tok])
            i += 1
    return code


def read_template(code, start: int, size: int | None = None) -> list[int]:
    """Collect the run of nops beginning at ``start`` (wrapping if ``size``)."""
    out: list[int] = []
    n = len(code) if size is None else size
    i = start
    for _ in range(n):
        op = code[i % n] if size is not None else code[i]
        if not is_nop(op):
            break
        out.append(op)
        i += 1
    return out


def disassemble(code, origin: int = 0, annotate: bool = True) -> str:
    """Produce a readable listing, collapsing nop runs into templates."""
    lines: list[str] = []
    i = 0
    n = len(code)
    while i < n:
        op = code[i] & 31
        if is_nop(op):
            run = []
            j = i
            while j < n and is_nop(code[j] & 31):
                run.append(code[j] & 31)
                j += 1
            lines.append(f"{origin + i:5d}  .t {template_str(run)}")
            i = j
            continue
        name = INSTRUCTIONS[op]
        note = ""
        if annotate and op in TEMPLATE_INSTRUCTIONS:
            run = []
            j = i + 1
            while j < n and is_nop(code[j] & 31):
                run.append(code[j] & 31)
                j += 1
            if run:
                note = f"    ; seeks {template_str(complement_bits(run))}"
        lines.append(f"{origin + i:5d}  {name}{note}")
        i += 1
    return "\n".join(lines)


def complement_bits(run: list[int]) -> list[int]:
    return [NOP1 if t == NOP0 else NOP0 for t in run]
