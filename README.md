# soup

A world of 60,000 memory cells, one hand-written self-replicating program, and
enough noise to make copying imperfect. Everything else — parasites, a
shortened and cheaper replicator, a genotype whose CPU gets captured by its
neighbours — is emergent, and this repository is the machine plus the evidence.

It is a deliberate cousin of Tom Ray's Tierra (1991), rebuilt from scratch so
that every rule is one I can state exactly and every claim below is one I
checked with a tool in `soup/analysis.py` rather than by reading a listing and
believing myself.

```
$ python3 -m soup run demo --instructions 20000000 --soup 60000
    1.0M  alive= 536 types=  76  H= 1.95  size~  60.5  dom=0064aaa (78%)  foreign=18% fbreed=20%
    ...
   20.0M  alive= 474 types= 188  H= 5.92  size~  56.0  dom=0009aaa (13%)  foreign=65% fbreed=70%
```

## Quick start

```bash
python3 -m unittest discover -s tests     # 47 tests, no dependencies
python3 -m soup ancestor                  # the seed organism, disassembled
python3 -m soup run demo --instructions 20000000
python3 experiments/fragmentation.py      # the sweep in finding 2
python3 experiments/report.py > experiments/REPORT.md
```

Pure Python 3.11, no dependencies, about 1M simulated instructions per second
on one core.

## The machine

**A saturated instruction set.** There are exactly 32 opcodes and all 32 are
defined, so every possible bit pattern is a legal instruction. A mutation
produces a *different program*, never a crash. This is the precondition for
everything else: if most mutations killed the machine rather than the creature,
selection would have nothing to work on.

**No absolute addresses.** Nothing can name a location numerically. Control
flow and self-inspection work by *template matching*: an addressing instruction
is followed by a run of `nop0`/`nop1`, and the machine searches outward from the
instruction pointer for the complementary run. A creature that gets longer or
shifts in memory still finds its own parts. It can also find *someone else's*
parts, because the search does not stop at the boundary of a creature — and
that is the crack through which the whole ecology comes in.

**Asymmetric protection.** Reads and jumps go anywhere; writes only land in a
creature's own genome or in the daughter block it has allocated. So one
creature can *use* another's code without being able to corrupt it.

**Three pressures and nothing else.** The scheduler hands every living creature
a slice of CPU. When the soup fills past 80% the reaper kills from the head of
a queue that creatures climb by making errors and descend by reproducing.
Cosmic rays flip bits anywhere; the copy instruction occasionally miscopies.
There is no fitness function anywhere in the code — the closest thing to one is
that a creature which reproduces faster than it is reaped persists.

## The ancestor

Sixty-four instructions, written by hand, and the only thing placed in the soup:

```
start:  .t 1111             ; START marker
        adrb .t 0000        ; ax <- my own start   (search backward for 1111)
        pushA
        adrf .t 0001        ; ax <- my END marker  (search forward for 1110)
        popB                ; bx <- my start
        subCAB              ; cx <- end - start
        incC incC incC incC ; cx = my length
        pushB pushC
        mal                 ; ax <- a daughter block of cx cells
        pushA popB popC popA
        call .t 0011        ; copy loop (search for 1100)
        divide              ; the daughter becomes an independent creature
        jmpb .t 0000        ; and again, forever
copy:   .t 1100
loop:   .t 1010
        movii               ; dest[bx] <- source[ax]
        decC incA incB
        ifz                 ; when the count hits zero, fall into ret
        ret
        jmpb .t 0101
end:    .t 1110
```

It divides in **420 instructions** with zero errors and without touching a
single cell outside itself — verified, not assumed:

```
$ python3 -m soup assay experiments/results/baseline.json ancestor
alone={'self_sufficient': True, 'births': 1, 'instructions': 420, 'errors': 0,
       'foreign_calls': 0, 'foreign_reads': 0}
```

## What happened

### 1. With mutation off, nothing ever happens

100M instructions, no copy errors, no cosmic rays: **240,205 births, exactly one
genotype, mean genome length 64.0 forever**. Population sits at ~375. That is
the control, and it matters — every result below has to be measured against a
world that is provably capable of doing nothing.

### 2. Memory fragmentation is a mutagen

The control above is a *large* soup. In a small one the monoculture breaks up
with both mutation switches still off, and the reason is a chain of five
mechanical steps:

1. the soup fragments, so no free gap is large enough;
2. `mal` fails, and leaves `ax` holding what it already held — the address of
   the creature's own END marker;
3. the copy loop runs anyway, writing to that address;
4. the START marker gets copied over the END marker — a write into its own
   genome, which is permitted;
5. the creature can no longer measure itself. Its `adrf` now finds the *next*
   creature's END marker, it computes twice its true length, and its daughters
   come out as double-length organisms.

Same seed, mutation fully off, soup size varied (`experiments/fragmentation.py`):

| soup cells | capacity | `mal` failures per birth | genotypes seen | mean length |
|-----------:|---------:|-------------------------:|---------------:|------------:|
|      1,000 |       15 |                     0.15 |              6 |        64.0 |
|      2,000 |       31 |                     1.18 |             59 |        68.9 |
|      4,000 |       62 |                     0.43 |            168 |        75.0 |
|      8,000 |      125 |                     0.18 |             15 |        96.0 |
|     16,000 |      250 |                     0.14 |             10 |        64.7 |
|     32,000 |      500 |                     0.01 |              5 |        64.0 |
|     60,000 |      937 |                     0.03 |              1 |        64.0 |

Allocation failures and genotype counts rise and fall together, and the largest
soup produces no variation at all. The smallest soup breaks the trend in the
other direction: only 15 creatures fit, so variants are reaped before they can
accumulate.

I did not design this mutagen. It is what an allocator that reports failure by
leaving a register alone does to a program that trusts it.

### 3. With mutation on, an ecosystem

100M instructions, 60,000 cells, one copy error per 1,000 cells copied, one
cosmic ray per 2,000 instructions, three seeds:

| | |
|---|---|
| genotypes alive at once | 225 – 271 |
| Shannon diversity | 6.8 – 7.3 bits |
| distinct genotypes ever seen | 11,893 – 15,621 |
| births | 52,548 – 68,490 |
| new genotype per birth | roughly 1 in 4 |
| reproducing creatures that had executed code outside their own genome | 50 – 67% |

The dominant genotype rarely holds more than a quarter of the population, and
the identity of the dominant changes several times per run.

### 4. Evolution rewrote the code that measures the genome

The winner of the baseline run, `0061aqz`, held 24% of the population at 100M.
It is **61 cells** and divides in **400 instructions** against the ancestor's 64
and 420. Nine substitutions and a three-cell truncation separate them, and they
are not independent damage — they are a repair:

* `nop1 -> or1` at cell 14 shortens the END-marker template from four bits to
  three, so `adrf` now seeks `111` instead of `1110`.
* `incC incC -> incA subCAB` at cells 17–18 rebuilds the arithmetic around the
  new marker, and `or1` disposes of the leftover template length.
* `nop1 -> shl` at 31 shortens the `call` template to two bits; the copy loop is
  now found by seeking `11`.
* Cells 55–57 shorten the loop's own `jmpb` template the same way.

The self-measurement machinery was rebuilt around shorter templates and a
shorter body, and it still computes exactly the right answer. The trace (loops
collapsed by the tool) is the proof:

```
$ python3 -m soup trace experiments/results/baseline.json 0061aqz
     10  adrf     ax=58     bx=0      cx=3      daughter=None
     14  or1      ax=58     bx=0      cx=2      daughter=None
     16  subCAB   ax=58     bx=0      cx=58     daughter=None
     17  incA     ax=59     bx=0      cx=58     daughter=None
     18  subCAB   ax=59     bx=0      cx=59     daughter=None
     19  incC     ax=59     bx=0      cx=60     daughter=None
     20  incC     ax=59     bx=0      cx=61     daughter=None      <- its true length
     23  mal      ax=61     bx=0      cx=61     daughter=(61, 61)
     28  call     ax=0      bx=61     cx=61     daughter=(61, 61)
        ↺ 60 iterations of the loop at 48..54 (6 instructions each), cx 61 -> 2
*    33  divide   ax=61     bx=122    cx=0      daughter=None
```

The saving is exactly the three copy-loop iterations it no longer needs. It is a
small optimisation, honestly — but nothing in the machine knows what a genome
is, what length means, or that shorter is better.

### 5. Parasites, and the opposite of parasites

A crowded soup makes "reproduces" a useless label, because a creature that
cannot reproduce alone reproduces perfectly well when it is packed between two
neighbours. So each genotype is cultured alone in a sterile medium — filled
with a non-template instruction, so that a search can only ever match real code
— and then beside one host, with every birth attributed to the genome it
actually produced.

That last step changed the answer. Six dependent genotypes from the baseline
run, crossed against every self-sufficient replicator in the same run plus the
ancestor:

```
           1aqz 1bbc 1aoq 9ajd 5ayi 9akb ancestor
  0036abh     H    H    H    H    H    H    H
  0057abf     P    P    P    P    P    P    P
  0060alp     P    P    P    P    P    P    P
  0062asz     P    P    P    P    P    P    P
  0119aax     P    P    P    P    P    P    P
  0069ahx     P    P    P    P    P    P    P

P = the guest copies itself using the host's code   (parasitism)
H = the guest spends its own CPU copying the host   (its CPU was captured)
```

Five of them are parasites in the plain mechanical sense: they carry no working
copy loop, they call into their neighbour's, and what comes out is a copy of
*them*. Universally, against every host tried, including the original ancestor.

`0036abh` is the interesting one. It calls into its neighbour too — but it lands
at the *top* of the neighbour's body rather than in its copy routine, so the
neighbour's self-inspection runs on the neighbour's coordinates and what comes
out is a copy of the **host**. It spends its entire CPU allowance making its
neighbour's children. Had I classified it from its genome alone, or from "does
it reproduce", it would have been filed as a parasite; it is the exact inverse.

Both effects need physical contact. Set the two genomes 32 cells apart instead
of packing them, and infection stops dead — the guest's search finds a pattern
inside its own body before it reaches the host:

```
$ python3 -m soup coculture experiments/results/baseline.json 0036abh 0061aqz --gap 32
  with_host      guest births=0  foreign calls=0
$ python3 -m soup coculture experiments/results/baseline.json 0036abh 0061aqz
  with_host      guest births=1  foreign calls=64  offspring={'host': 1}
```

### 6. A prediction that did not survive contact

I expected the CPU scheduling rule to control genome length: give every creature
the same slice regardless of size and short genomes should win, because they
reach `divide` sooner. Six 100M runs — three seeds with a constant slice, three
with a slice proportional to length, matched so that a 64-cell creature gets
exactly the same 20 instructions per turn in both — say otherwise:

| condition | mean length over the last 30% of each run |
|---|---|
| constant slice | 56.2, 60.3, 72.0 |
| slice proportional to length | 51.9, 69.0, 64.1 |

The spread between seeds is larger than the difference between conditions. At
this scale the prediction is simply not supported, and the honest summary is
that genome length wanders between about 50 and 75 under both rules while the
population churns. Longer runs are in `experiments/REPORT.md`.

### 7. Evolvability is expensive

The same 100M instructions bought 240,205 births in the control and 52,548 –
68,490 in the mutating runs. Three quarters of the world's reproductive output
is spent on variants that do not work. Nothing here is free: the same noise that
produced a better replicator in finding 4 is the reason the population is a
third as productive.

## How the claims here were checked

Reading an evolved genome is a good way to convince yourself of something false,
so every claim above came from a tool, and the tools are tested:

* `isolation_assay` — culture a genome alone in a sterile soup. Answers "can it
  reproduce by itself" with no interpretation required.
* `coculture_assay` — culture it beside a host, and attribute every birth to the
  genome it produced, using the gene bank's own records rather than by looking
  at who ends up lying next to whom.
* `trace` / `trace_summary` — single-step execution with loops folded, which is
  where the register-by-register account in finding 4 comes from.
* `fidelity` — the fraction of a genotype's births that came from its own kind.
  This is how a real lineage is told apart from a shape that damaged mothers
  keep re-emitting: the eight-cell fragments that show up in every census have
  hundreds of births and a fidelity near zero.
* `modal_parent` — ancestry by the route a genotype actually travels, not by
  whoever produced it first, which for a rare variant is often a freak event.

`python3 -m unittest discover -s tests` runs 47 tests covering the instruction
semantics, the allocator, template search, write protection, the division rules,
determinism under a fixed seed, and the mutagen of finding 2 in isolation.

## Limitations

* One ancestor, one instruction set. Nothing here shows these results are
  general rather than particular to this 64-cell program.
* 100M instructions is a short evolutionary time; the longest runs here are
  400M and the population is still churning at the end.
* Genotypes are exact genome identity, so a single silent bit flip counts as a
  new species. Diversity numbers should be read with that in mind.
* The interaction matrix tests one guest against one host at a time. Real soup
  neighbourhoods have several, and the outcome depends on which template is
  nearest.
* `soup/analysis.py` classifies with a fixed instruction budget; a very slow
  replicator would be misfiled as inert.

## Layout

```
soup/isa.py          the 32 opcodes and what a template is
soup/asm.py          assembler and disassembler
soup/vm.py           soup memory, allocator, CPU, the interpreter
soup/world.py        scheduler, reaper queue, gene bank, mutation
soup/analysis.py     isolation and co-culture assays, tracing, classification
soup/experiment.py   running an experiment and recording it
soup/plot.py         ASCII charts, so results can live in a text file
soup/ancestor.sm     the seed organism
experiments/         the runs, their JSON histories, and the generated report
tests/               47 unit tests
```

## Reproducing

Every run is deterministic given its seed. The numbers quoted above come from:

```bash
python3 -m soup run control-no-mutation --instructions 100000000 --seed 1 \
        --copy-mutation 0 --cosmic 0
python3 -m soup run baseline --instructions 100000000 --seed 1
python3 -m soup run matched-neutral-s1 --instructions 100000000 --seed 1 \
        --slice-size 0.3125 --slice-pow 1.0
python3 experiments/fragmentation.py
python3 experiments/report.py > experiments/REPORT.md
```
