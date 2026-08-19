# The machine, in detail

Everything in this soup runs on one small virtual CPU. This document explains it
from the bottom up: what a creature *is*, how it finds its own parts without
knowing any addresses, what each of the 32 instructions does, and then a
line-by-line reading of the ancestor with a real execution trace beside it.

If you only read one section, read [Templates](#templates-addressing-without-addresses).
It is the idea the whole world is built on, and nothing else makes sense
without it.

## A creature

A creature is two things: a **block of memory** it owns, and a **CPU state**.

```
registers   ax  bx  cx  dx        32-bit unsigned, wrap on overflow
stack       10 slots, circular    push overwrites the oldest when full
ip          the instruction pointer
genome      a start address and a length in the soup
daughter    a second block, owned between `mal` and `divide` (or none)
```

There is nothing else. No flags, no immediate operands, no absolute addresses
anywhere in the instruction set.

The soup itself is a flat circular array of 60,000 cells, each holding one
5-bit instruction. Address arithmetic wraps: the cell after the last is the
first.

**Reads and jumps go anywhere. Writes do not.** A creature may read, search and
execute any cell in the soup, including code belonging to its neighbours, but
`movii` only succeeds when writing into its own genome or into the daughter
block it has allocated. That single asymmetry is what makes the ecology
possible: a creature can *use* another's code without being able to damage it.

## Templates: addressing without addresses

The problem: a program that copies itself has to refer to its own parts — where
do I begin, where do I end, where is my copy loop. If it referred to them by
address, then any mutation that shifted or lengthened it would break every
reference at once, and nothing could evolve.

The solution, taken from Tierra, is to name locations by **pattern**. Two of the
32 instructions, `nop0` and `nop1`, do nothing when executed. A run of them is a
*template* — a bit pattern sitting in the code. Instructions that need an
address are followed by a template, and the machine searches outward from the
instruction pointer for the **complementary** pattern: `0` matches `1`.

A worked example. Suppose these cells sit in the soup:

```
address:   100  101  102  103  104   ...   118   119  120  121  122  123
content:  nop1 nop1 nop1 nop1 adrb   ...  incA  adrf nop0 nop0 nop0 nop1
                                                     └─ template 0001 ─┘
          └──── template 1111 ────┘
```

The `adrf` at 119 is followed by the template `0001` in cells 120–123. The
machine:

1. reads the run of nops after the instruction — `0001`, four cells;
2. resumes the instruction pointer *after* that run, at 124;
3. complements the pattern: `0001` → `1110`;
4. searches forward from 124 for four consecutive cells matching `1110`;
5. puts the address of the **first cell of the match** into `ax`, and the
   template's length (4) into `cx`.

`adrb` searches backward instead, `adr` searches outward in both directions and
takes the nearer match. The jump instructions use the same search but land
*just past* the match, so that a template acts like a label with the code
following it.

Three consequences follow, and all three matter:

* **Mutation-tolerant.** A creature that gains or loses cells still finds its own
  parts, because nothing is addressed numerically.
* **Shared namespace.** The search does not stop at the edge of a creature. A
  creature that has lost its own copy loop will find its *neighbour's*. This is
  where parasitism comes from — see finding 7 in the README.
* **Templates can be attacked and defended.** A host that changes the pattern
  naming its copy loop becomes invisible to a parasite searching for the old
  one, at no cost to itself. That is finding 8.

Templates are capped at 10 cells. A longer nop run is truncated when used as a
template.

## The instruction set

Exactly 32 opcodes, and all 32 are defined, so **every possible bit pattern is a
legal instruction**. A mutation produces a different program, never a crash.

### Doing nothing, and marking places

| | |
|---|---|
| `nop0` | no operation; a `0` bit when part of a template |
| `nop1` | no operation; a `1` bit when part of a template |

### Building numbers

There are no literals. Numbers are built up, or obtained by measuring yourself.

| | |
|---|---|
| `zero` | `cx = 0` |
| `or1` | `cx ^= 1` — flips the low bit, so odd constants are reachable |
| `shl` | `cx <<= 1` |
| `incA` `incB` `incC` | add one to `ax`, `bx`, `cx` |
| `decC` | subtract one from `cx` |
| `subCAB` | `cx = ax - bx` — the instruction that measures a genome |
| `subAAC` | `ax = ax - cx` |

### Moving things around

| | |
|---|---|
| `pushA` `pushB` `pushC` `pushD` | push a register onto the 10-slot circular stack |
| `popA` `popB` `popC` `popD` | pop into a register |
| `movBA` | `bx = ax` |
| `movDC` | `dx = cx` |
| `movii` | **the copy instruction**: `soup[bx] = soup[ax]`, if `bx` is inside the creature's own genome or its daughter block; otherwise an error |

`push` followed by `pop` is how a value gets from any register to any other one:
the set of direct moves is deliberately thin, and evolution routinely rearranges
these sequences.

### Control flow, by template

| | |
|---|---|
| `ifz` | if `cx == 0` execute the next instruction, otherwise skip it |
| `jmp` | jump to the nearest complementary template, searching both ways |
| `jmpb` | jump to the nearest complementary template, backward only |
| `call` | push the return address, then jump like `jmp` |
| `ret` | pop an address into the instruction pointer |
| `adr` | search both ways: `ax` = address of the match, `cx` = template length |
| `adrb` | the same, backward only |
| `adrf` | the same, forward only |

### Life and death

| | |
|---|---|
| `mal` | allocate `cx` cells for a daughter; the address goes into `ax`. Frees any previous daughter first. Fails if `cx` is out of range or no contiguous gap is free — and a failed `mal` leaves `ax` untouched, which turns out to matter a great deal (finding 2) |
| `divide` | release the daughter block as an independent creature. Fails unless at least half of it has been written |

## Reading the ancestor

The ancestor is 64 instructions and does one thing in a loop: work out where it
begins and ends, ask for that much memory, copy itself into it, split it off,
repeat. Thirty-six of its 64 cells are nops forming nine templates.

### Phase 1 — measure yourself

```
start:  .t 1111             ; a marker. Not executed for effect; it is here to be found.
        adrb .t 0000        ; search backward for 1111 -> ax = my own first cell
        pushA               ; keep it
        adrf .t 0001        ; search forward for 1110 -> ax = my END marker
        popB                ; bx = my start
        subCAB              ; cx = end - start
        incC incC incC incC ; + the four cells of the END marker = my length
```

Note what is *not* here: any number saying "64". The creature does not know its
own length; it measures it, every time, by finding two patterns and subtracting
their addresses. That is why a descendant of a different length still works.

### Phase 2 — ask for room

```
        pushB               ; stack: [start]
        pushC               ; stack: [start, length]
        mal                 ; allocate cx cells; ax = where the daughter will live
        pushA               ; stack: [start, length, daughter]
        popB                ; bx = daughter
        popC                ; cx = length
        popA                ; ax = start
```

Three pushes and three pops to load the copy loop's three arguments — source in
`ax`, destination in `bx`, count in `cx`. This shuffling is pure overhead, and
it is exactly the sort of thing evolution later rearranges away.

### Phase 3 — copy

```
        call .t 0011        ; search for 1100: the copy procedure
        ...
copy:   .t 1100             ; the procedure's name
loop:   .t 1010             ; the loop's name
        movii               ; daughter[bx] = self[ax]
        decC                ; one fewer to go
        incA                ; next source cell
        incB                ; next destination cell
        ifz                 ; when the count hits zero, fall through to ret
        ret
        jmpb .t 0101        ; otherwise search backward for 1010 and go round
```

Six instructions per cell copied. Every evolved descendant in this repository is
measured against that number.

The `call` is important beyond its function: because it finds the copy procedure
by *searching for a pattern*, a creature whose own copy procedure has been
destroyed will find a neighbour's and run it. Parasitism is not a feature that
was added; it is what template addressing does when a genome is damaged.

### Phase 4 — divide, and again

```
        divide              ; the daughter becomes an independent creature
        jmpb .t 0000        ; search backward for 1111 -> back to the start
```

### The whole cycle as a trace

Real output from `python3 -m soup trace`, with the copy loop folded into one
line:

```
      0  nop1     ax=0      bx=0      cx=0      daughter=None     the START marker,
      1  nop1     ax=0      bx=0      cx=0      daughter=None     executed as four
      2  nop1     ax=0      bx=0      cx=0      daughter=None     no-ops on the way
      3  nop1     ax=0      bx=0      cx=0      daughter=None     past
      4  adrb     ax=0      bx=0      cx=4      daughter=None     found itself at 0
      9  pushA    ax=0      bx=0      cx=4      daughter=None
     10  adrf     ax=60     bx=0      cx=4      daughter=None     END marker at 60
     15  popB     ax=60     bx=0      cx=4      daughter=None
     16  subCAB   ax=60     bx=0      cx=60     daughter=None     60 = 60 - 0
     17  incC     ax=60     bx=0      cx=61     daughter=None
     18  incC     ax=60     bx=0      cx=62     daughter=None
     19  incC     ax=60     bx=0      cx=63     daughter=None
     20  incC     ax=60     bx=0      cx=64     daughter=None     its true length
     21  pushB    ax=60     bx=0      cx=64     daughter=None
     22  pushC    ax=60     bx=0      cx=64     daughter=None
     23  mal      ax=64     bx=0      cx=64     daughter=(64, 64) 64 cells at 64
     24  pushA    ax=64     bx=0      cx=64     daughter=(64, 64)
     25  popB     ax=64     bx=64     cx=64     daughter=(64, 64) destination
     26  popC     ax=64     bx=64     cx=64     daughter=(64, 64) count
     27  popA     ax=0      bx=64     cx=64     daughter=(64, 64) source
     28  call     ax=0      bx=64     cx=64     daughter=(64, 64) into the copy loop
        ↺ 63 iterations of the loop at 48..54 (6 instructions each), cx 64 -> 2
     48  movii    ax=63     bx=127    cx=1      daughter=(64, 64) the last cell
     53  ret      ax=64     bx=128    cx=0      daughter=(64, 64)
*    33  divide   ax=64     bx=128    cx=0      daughter=None     a new creature
```

410 instructions from start to daughter, 407 for every replication after that,
and 6.4 instructions per cell copied. Those three numbers are the baseline for
every result in the README.

## Living in the soup

**Time.** The scheduler gives every living creature a slice of instructions in
turn. The slice may be constant, or proportional to genome length raised to a
power — and which one you choose decides whether selection favours short
genomes or is indifferent to length (finding 10).

**Death.** When the soup fills past 80%, or when an allocation cannot be
satisfied, the reaper kills from the head of a queue. Creatures enter at the
tail, climb one place toward the head each time they cause an error, and drop
one place back each time they successfully divide. Nothing else in the world
resembles a fitness function.

**Errors** are what a creature does wrong, and they cost it: a failed template
search, a write outside its own memory, an allocation it cannot have, a
`divide` with nothing to divide. None of them stop execution — the instruction
simply does nothing and the creature moves closer to the reaper.

**Noise.** Cosmic rays flip a random bit in the soup every so often, and the
copy instruction occasionally miscopies. Both rates are settable; between them
they are the only intentional source of variation, though not the only actual
one (finding 2).

**Birth.** A successful `divide` reads the daughter block, gives its exact
instruction sequence a genotype name (`0064aaa` — length, then a letter code in
order of discovery), and enters it into the scheduler and the reaper queue as a
new creature with its own registers, all zeroed, and its instruction pointer at
its first cell.
