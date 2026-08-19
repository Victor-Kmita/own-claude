"""The soup: a block of memory, a memory allocator, and a CPU that runs on it.

Everything a creature can do to the world happens here.  The interpreter is
written as a *slice runner* -- it executes up to N instructions for one creature
per call -- because the hot loop is the whole cost of the simulation and Python
function-call overhead per instruction would dominate otherwise.

Memory model
------------
The soup is a flat, circular array of 5-bit cells.  Every address arithmetic
wraps.  A creature owns exactly one block (its genome) and may own a second,
temporary block (its daughter) between ``mal`` and ``divide``.

Reads and execution are unprotected: a creature may read or jump anywhere.
Writes are protected: ``movii`` only succeeds into the creature's own genome or
its daughter block.  That asymmetry is the entire ecology.  It means one
creature can *use* another's code without being able to corrupt it, which is the
precondition for parasitism -- and, later, for immunity.
"""

from __future__ import annotations

import random
from bisect import bisect_left, insort

from .isa import INSTRUCTIONS, NOP0, NOP1, NUM_OPCODES, OPCODE, is_nop

MASK32 = 0xFFFFFFFF
STACK_DEPTH = 10

# Cache opcode numbers as module constants: the interpreter compares against
# these thousands of times per millisecond.
_NOP0, _NOP1 = OPCODE["nop0"], OPCODE["nop1"]
_OR1, _SHL, _ZERO, _IFZ = OPCODE["or1"], OPCODE["shl"], OPCODE["zero"], OPCODE["ifz"]
_SUBCAB, _SUBAAC = OPCODE["subCAB"], OPCODE["subAAC"]
_INCA, _INCB, _INCC, _DECC = OPCODE["incA"], OPCODE["incB"], OPCODE["incC"], OPCODE["decC"]
_PUSHA, _PUSHB, _PUSHC, _PUSHD = (OPCODE["pushA"], OPCODE["pushB"],
                                  OPCODE["pushC"], OPCODE["pushD"])
_POPA, _POPB, _POPC, _POPD = (OPCODE["popA"], OPCODE["popB"],
                              OPCODE["popC"], OPCODE["popD"])
_JMP, _JMPB, _CALL, _RET = OPCODE["jmp"], OPCODE["jmpb"], OPCODE["call"], OPCODE["ret"]
_MOVDC, _MOVBA, _MOVII = OPCODE["movDC"], OPCODE["movBA"], OPCODE["movii"]
_ADR, _ADRB, _ADRF = OPCODE["adr"], OPCODE["adrb"], OPCODE["adrf"]
_MAL, _DIVIDE = OPCODE["mal"], OPCODE["divide"]


class Cpu:
    """Register file and control state of one creature."""

    __slots__ = ("ip", "ax", "bx", "cx", "dx", "stack", "sp")

    def __init__(self, ip: int = 0):
        self.ip = ip
        self.ax = self.bx = self.cx = self.dx = 0
        self.stack = [0] * STACK_DEPTH
        self.sp = 0

    def snapshot(self) -> dict:
        return {
            "ip": self.ip, "ax": self.ax, "bx": self.bx,
            "cx": self.cx, "dx": self.dx, "sp": self.sp,
            "stack": list(self.stack),
        }


class Memory:
    """Allocator over the circular soup.

    Blocks are kept as a sorted list of ``(start, size)`` pairs; allocation is
    first-fit scanning forward from a rotating cursor so that new creatures are
    scattered rather than piled at low addresses.  With at most a few thousand
    live blocks a linear scan is cheaper than any cleverer structure and is far
    easier to reason about when something goes wrong.
    """

    def __init__(self, size: int):
        self.size = size
        self.blocks: list[tuple[int, int]] = []   # sorted by start
        self.used = 0
        self.cursor = 0

    def gaps(self):
        """Yield ``(start, length)`` of every free run, in address order."""
        if not self.blocks:
            yield 0, self.size
            return
        prev_end = 0
        for start, length in self.blocks:
            if start > prev_end:
                yield prev_end, start - prev_end
            prev_end = start + length
        if prev_end < self.size:
            yield prev_end, self.size - prev_end

    def allocate(self, size: int) -> int | None:
        """First fit at or after the cursor; returns the start address."""
        if size <= 0 or size > self.size:
            return None
        candidates = list(self.gaps())
        if not candidates:
            return None
        # Rotate the gap list so the search starts near the cursor.
        idx = 0
        for i, (start, _length) in enumerate(candidates):
            if start >= self.cursor:
                idx = i
                break
        order = candidates[idx:] + candidates[:idx]
        for start, length in order:
            if length >= size:
                insort(self.blocks, (start, size))
                self.used += size
                self.cursor = (start + size) % self.size
                return start
        return None

    def free(self, start: int, size: int) -> None:
        i = bisect_left(self.blocks, (start, size))
        if i < len(self.blocks) and self.blocks[i] == (start, size):
            self.blocks.pop(i)
            self.used -= size

    @property
    def load(self) -> float:
        return self.used / self.size


class ExecStats:
    """Counters the world uses to decide who dies and what to report."""

    __slots__ = ("instructions", "errors", "births", "foreign_reads",
                 "foreign_calls", "writes")

    def __init__(self):
        self.instructions = 0
        self.errors = 0
        self.births = 0
        self.foreign_reads = 0
        self.foreign_calls = 0
        self.writes = 0


class Creature:
    """One organism: a genome block, a CPU, and some bookkeeping."""

    __slots__ = ("cid", "start", "size", "cpu", "daughter", "daughter_writes",
                 "genotype", "mother", "born_tick", "generation", "stats",
                 "alive", "slice_left")

    def __init__(self, cid: int, start: int, size: int, genotype: str = "?",
                 mother: int | None = None, born_tick: int = 0,
                 generation: int = 0):
        self.cid = cid
        self.start = start
        self.size = size
        self.cpu = Cpu(ip=start)
        self.daughter: tuple[int, int] | None = None
        self.daughter_writes = 0
        self.genotype = genotype
        self.mother = mother
        self.born_tick = born_tick
        self.generation = generation
        self.stats = ExecStats()
        self.alive = True
        self.slice_left = 0

    def owns(self, addr: int, soup_size: int) -> bool:
        rel = (addr - self.start) % soup_size
        if rel < self.size:
            return True
        if self.daughter is not None:
            dstart, dsize = self.daughter
            if (addr - dstart) % soup_size < dsize:
                return True
        return False

    def __repr__(self) -> str:                                # pragma: no cover
        return (f"<Creature {self.cid} {self.genotype} @{self.start}+{self.size} "
                f"ip={self.cpu.ip} births={self.stats.births}>")


def find_template(soup, soup_size: int, origin: int, wanted: list[int],
                  direction: int, limit: int) -> int | None:
    """Search outward from ``origin`` for the run of nops ``wanted``.

    ``direction`` is -1 (backward only), +1 (forward only) or 0 (outward in both
    directions, nearest match wins).  Returns the address of the *first cell* of
    the match, or None.  All arithmetic wraps around the circular soup.

    Note what is deliberately absent: any notion of ownership.  The search walks
    straight through the boundary between one creature and the next.  Templates
    are a shared namespace, and that is what lets an organism that has lost its
    own copy routine borrow its neighbour's.
    """
    length = len(wanted)
    if length == 0:
        return None
    w0 = wanted[0]
    for step in range(limit):
        if direction >= 0:                      # forward candidate, distance step
            p = (origin + step) % soup_size
            if soup[p] == w0:
                for k in range(1, length):
                    if soup[(p + k) % soup_size] != wanted[k]:
                        break
                else:
                    return p
        if direction <= 0:                      # backward candidate, distance step+1
            p = (origin - 1 - step) % soup_size
            if soup[p] == w0:
                for k in range(1, length):
                    if soup[(p + k) % soup_size] != wanted[k]:
                        break
                else:
                    return p
    return None


MAX_TEMPLATE = 10        # longer nop runs are truncated when used as a template


def run_slice(world, cr: "Creature", budget: int) -> int:
    """Execute up to ``budget`` instructions for one creature.

    Returns the number actually executed.  Registers live in locals for the
    duration of the slice and are written back at the end; in CPython that is
    worth roughly a factor of two on the whole simulation.
    """
    soup = world.soup
    N = world.soup_size
    cpu = cr.cpu
    ip, ax, bx, cx, dx = cpu.ip, cpu.ax, cpu.bx, cpu.cx, cpu.dx
    stack, sp = cpu.stack, cpu.sp
    st = cr.stats
    limit = world.search_limit
    rng = world.rng
    copy_mut = world.copy_mutation_rate
    start, csize = cr.start, cr.size

    executed = 0
    while executed < budget:
        op = soup[ip]
        nxt = ip + 1
        if nxt == N:
            nxt = 0
        executed += 1

        # --- hot path first: the copy loop is most of all cycles ever run ----
        if op == _MOVII:
            src = ax % N
            dst = bx % N
            if (dst - start) % N < csize:
                own = True
            elif cr.daughter is not None and (dst - cr.daughter[0]) % N < cr.daughter[1]:
                own = True
                cr.daughter_writes += 1
            else:
                own = False
            if own:
                val = soup[src]
                if copy_mut and rng.random() < copy_mut:
                    val ^= 1 << rng.randrange(5)
                soup[dst] = val
                st.writes += 1
                if (src - start) % N >= csize:
                    st.foreign_reads += 1
            else:
                st.errors += 1
        elif op == _INCA:
            ax = (ax + 1) & MASK32
        elif op == _INCB:
            bx = (bx + 1) & MASK32
        elif op == _DECC:
            cx = (cx - 1) & MASK32
        elif op == _IFZ:
            if cx != 0:
                nxt += 1
                if nxt >= N:
                    nxt -= N
        elif op == _NOP0 or op == _NOP1:
            pass
        elif op == _JMPB or op == _JMP or op == _CALL:
            t = []
            q = nxt
            while len(t) < MAX_TEMPLATE:
                c = soup[q]
                if c > 1:
                    break
                t.append(c)
                q += 1
                if q == N:
                    q = 0
            nxt = q
            if not t:
                st.errors += 1
            else:
                want = [1 - b for b in t]
                direction = -1 if op == _JMPB else 0
                hit = find_template(soup, N, nxt, want, direction, limit)
                if hit is None:
                    st.errors += 1
                else:
                    target = (hit + len(t)) % N
                    if op == _CALL:
                        stack[sp] = nxt
                        sp = (sp + 1) % STACK_DEPTH
                    if (target - start) % N >= csize:
                        st.foreign_calls += 1
                    nxt = target
        elif op == _INCC:
            cx = (cx + 1) & MASK32
        elif op == _RET:
            sp = (sp - 1) % STACK_DEPTH
            nxt = stack[sp] % N
            if (nxt - start) % N >= csize:
                st.foreign_calls += 1
        elif op == _PUSHA:
            stack[sp] = ax
            sp = (sp + 1) % STACK_DEPTH
        elif op == _PUSHB:
            stack[sp] = bx
            sp = (sp + 1) % STACK_DEPTH
        elif op == _PUSHC:
            stack[sp] = cx
            sp = (sp + 1) % STACK_DEPTH
        elif op == _PUSHD:
            stack[sp] = dx
            sp = (sp + 1) % STACK_DEPTH
        elif op == _POPA:
            sp = (sp - 1) % STACK_DEPTH
            ax = stack[sp]
        elif op == _POPB:
            sp = (sp - 1) % STACK_DEPTH
            bx = stack[sp]
        elif op == _POPC:
            sp = (sp - 1) % STACK_DEPTH
            cx = stack[sp]
        elif op == _POPD:
            sp = (sp - 1) % STACK_DEPTH
            dx = stack[sp]
        elif op == _ADR or op == _ADRB or op == _ADRF:
            t = []
            q = nxt
            while len(t) < MAX_TEMPLATE:
                c = soup[q]
                if c > 1:
                    break
                t.append(c)
                q += 1
                if q == N:
                    q = 0
            nxt = q
            if not t:
                st.errors += 1
            else:
                want = [1 - b for b in t]
                direction = 0 if op == _ADR else (-1 if op == _ADRB else 1)
                hit = find_template(soup, N, nxt, want, direction, limit)
                if hit is None:
                    st.errors += 1
                else:
                    ax = hit
                    cx = len(t)
        elif op == _SUBCAB:
            cx = (ax - bx) & MASK32
        elif op == _SUBAAC:
            ax = (ax - cx) & MASK32
        elif op == _ZERO:
            cx = 0
        elif op == _OR1:
            cx ^= 1
        elif op == _SHL:
            cx = (cx << 1) & MASK32
        elif op == _MOVBA:
            bx = ax
        elif op == _MOVDC:
            dx = cx
        elif op == _MAL:
            want_size = cx
            if want_size < world.min_daughter_size or want_size > world.max_daughter_size:
                st.errors += 1
            else:
                if cr.daughter is not None:
                    world.memory.free(*cr.daughter)
                    cr.daughter = None
                addr = world.memory.allocate(want_size)
                if addr is None:
                    addr = world.make_room(want_size, requester=cr)
                if addr is None:
                    # No contiguous gap big enough.  This is not a neutral
                    # failure: ax still holds whatever the creature last put
                    # there, and the copy loop that follows will write to it.
                    # Fragmentation is a mutagen -- see the write-up.
                    world.alloc_failures += 1
                    st.errors += 1
                else:
                    cr.daughter = (addr, want_size)
                    cr.daughter_writes = 0
                    ax = addr
        elif op == _DIVIDE:
            if cr.daughter is None:
                st.errors += 1
            elif cr.daughter_writes * 2 < cr.daughter[1]:
                st.errors += 1          # refuse to release a mostly-uncopied cell
            else:
                cpu.ip, cpu.ax, cpu.bx, cpu.cx, cpu.dx, cpu.sp = ip, ax, bx, cx, dx, sp
                world.birth(cr)
                st.births += 1
        else:                                                  # pragma: no cover
            raise AssertionError(f"unhandled opcode {op}")

        ip = nxt

    cpu.ip, cpu.ax, cpu.bx, cpu.cx, cpu.dx, cpu.sp = ip, ax, bx, cx, dx, sp
    st.instructions += executed
    return executed
