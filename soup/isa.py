"""The instruction set of the soup machine.

Design constraints, in order of importance:

1.  **Every bit pattern is a legal instruction.**  The opcode space is exactly
    32 wide and every opcode is defined, so a random bit flip anywhere in the
    soup produces a different *valid* program rather than a crash.  This is the
    single most important property for evolvability: mutation must be survivable
    often enough that selection has something to work with.

2.  **No absolute addresses.**  Nothing in the instruction set can name a
    location in memory numerically.  Control flow and self-inspection work by
    *template matching*: an addressing instruction is followed by a run of
    ``nop0``/``nop1`` instructions, and the machine searches outward from the
    instruction pointer for the complementary run.  A mutation that lengthens or
    shifts a creature therefore does not break its internal references -- and,
    crucially, a creature can accidentally find *another creature's* code.  That
    accident is what makes parasitism possible.

3.  **Small integer registers, no literals.**  There are no immediate operands.
    Numbers are built with ``zero``/``or1``/``shl``/``inc``/``dec`` or obtained
    from self-inspection.  This keeps the encoding one-byte-per-instruction and
    removes another way for mutation to be fatal.

The set below is a deliberate cousin of Tom Ray's Tierra instruction set
(1991), rearranged and re-specified so that the semantics here are exactly what
this VM implements rather than what a paper describes.
"""

from __future__ import annotations

# --- opcode table ----------------------------------------------------------
# The order matters only in that the space must be exactly 32 entries.

INSTRUCTIONS: tuple[str, ...] = (
    "nop0",      # 0x00  template bit 0 / no operation
    "nop1",      # 0x01  template bit 1 / no operation
    "or1",       # 0x02  cx ^= 1                     (build odd constants)
    "shl",       # 0x03  cx <<= 1
    "zero",      # 0x04  cx = 0
    "ifz",       # 0x05  if cx == 0 run next instruction, else skip it
    "subCAB",    # 0x06  cx = ax - bx
    "subAAC",    # 0x07  ax = ax - cx
    "incA",      # 0x08  ax += 1
    "incB",      # 0x09  bx += 1
    "incC",      # 0x0a  cx += 1
    "decC",      # 0x0b  cx -= 1
    "pushA",     # 0x0c
    "pushB",     # 0x0d
    "pushC",     # 0x0e
    "pushD",     # 0x0f
    "popA",      # 0x10
    "popB",      # 0x11
    "popC",      # 0x12
    "popD",      # 0x13
    "jmp",       # 0x14  jump to nearest complementary template (both ways)
    "jmpb",      # 0x15  jump to nearest complementary template, backward only
    "call",      # 0x16  push return address, then jmp
    "ret",       # 0x17  pop return address
    "movDC",     # 0x18  dx = cx
    "movBA",     # 0x19  bx = ax
    "movii",     # 0x1a  soup[bx] = soup[ax]         (the copy instruction)
    "adr",       # 0x1b  search both ways: ax = address, cx = template length
    "adrb",      # 0x1c  search backward
    "adrf",      # 0x1d  search forward
    "mal",       # 0x1e  allocate cx cells for a daughter, address into ax
    "divide",    # 0x1f  release the daughter as an independent creature
)

assert len(INSTRUCTIONS) == 32, "the opcode space must be saturated"

OPCODE = {name: i for i, name in enumerate(INSTRUCTIONS)}
NUM_OPCODES = len(INSTRUCTIONS)
OPCODE_BITS = 5

# Instructions that consume a template (the run of nops that follows them).
TEMPLATE_INSTRUCTIONS = frozenset(
    OPCODE[n] for n in ("jmp", "jmpb", "call", "adr", "adrb", "adrf")
)

NOP0 = OPCODE["nop0"]
NOP1 = OPCODE["nop1"]


def is_nop(op: int) -> bool:
    return op == NOP0 or op == NOP1


def complement(template: list[int]) -> list[int]:
    """0 <-> 1.  A template is matched by its bitwise complement."""
    return [NOP1 if t == NOP0 else NOP0 for t in template]


def template_str(template: list[int]) -> str:
    return "".join("1" if t == NOP1 else "0" for t in template)
