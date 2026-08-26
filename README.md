# soup

*An artificial life world of self-replicating programs — digital organisms in the
Tierra lineage, in dependency-free Python, with every finding held as a claim a
reader can re-check.*

A world of 60,000 memory cells, one hand-written self-replicating program, and
enough noise to make copying imperfect. Everything else — parasites, hosts that
become immune to them, a shorter and cheaper replicator, genome length that
tracks the CPU scheduler — happens on its own, and this repository is the
machine plus the evidence.

It is a deliberate cousin of Tom Ray's Tierra (1991), rebuilt from scratch so
that every rule is one I can state exactly, and every claim below is one a tool
in `soup/analysis.py` checked — not one I got by reading a listing and believing
myself.

```
$ python3 -m soup run demo --instructions 20000000
     1.0M  alive= 386 types=  91  H= 2.69  size~  63.8  dom=0064aaa (72%)  foreign=11% fbreed=16%
     ...
    20.0M  alive= 608 types= 194  H= 6.67  size~  62.3  dom=0064abg (8%)  foreign=14% fbreed=18%
```

## Before you believe any of this

```
python3 -m soup verify            # seconds
python3 -m soup verify --tier full   # minutes
```

Every claim below that can be checked by running something is also in
`soup/claims.json`, with a check that runs on your machine and a non-zero exit
code if it fails. Four of the nineteen findings here have been rewritten after
checking, and three times the fault was the instrument rather than the world —
the first time `verify` ran, it caught a mistake in a table written an hour
earlier. `lab/AGENT-ANY.md` is the same point at more length, for anyone with
their own machine who wants to check or extend this.

## Quick start

```bash
python3 -m unittest discover -s tests     # 54 tests, no dependencies
python3 -m soup ancestor                  # the seed organism, disassembled
python3 -m soup run demo --instructions 20000000
python3 experiments/fragmentation.py      # the policy sweep in finding 2
python3 experiments/viability.py          # the mutational landscape in finding 9
python3 experiments/epidemic.py           # the resistance experiment in finding 11
python3 experiments/mutation_rate.py      # the sweep and error threshold, finding 12
python3 experiments/neutrality.py         # behaviours rather than genomes, finding 14
python3 experiments/flatness.py           # survival of the flattest, finding 6
python3 experiments/heritability.py       # what one mutation event is worth, finding 16
python3 experiments/spectrum.py           # what kinds of daughter mutation makes, finding 17
python3 experiments/deletion_floor.py     # is the plateau a floor? finding 17
python3 experiments/selection.py          # how strong selection is here
python3 experiments/robustness_arc.py     # what happens to robustness over time
python3 -m soup run x --flaw 1000         # Tierra's third mutation mode, finding 13
python3 -m soup verify                    # check this document's own claims, here
python3 experiments/coadaptation.py       # what a transplanted parasite needs
python3 experiments/optimization_curve.py # how cheap replicators get, per run length
python3 experiments/report.py > experiments/REPORT.md
```

Pure Python 3.11, no dependencies, about one million simulated instructions per
second on one core.

## The machine

Full reference in [`docs/MACHINE.md`](docs/MACHINE.md), including all 32
instructions. The five things you need to read the rest of this page:

**A creature is a block of memory plus a tiny CPU state.** Four 32-bit
registers `ax bx cx dx`, a ten-slot stack, an instruction pointer, and the
address and length of the block it owns. Between asking for a daughter block and
splitting it off, it owns a second block too. That is the whole of it — no
flags, no variables, no immediate operands.

**A saturated instruction set.** Exactly 32 opcodes, all 32 defined, so every
possible bit pattern is a legal instruction. A mutation produces a *different
program*, never a crash. Without this, evolution would have nothing to work on:
most mutations would kill the machine rather than change the creature.

**No addresses anywhere — locations are named by pattern.** This is the idea the
whole world rests on, so here it is concretely. Two instructions, `nop0` and
`nop1`, do nothing when executed; a run of them is a *template*, a bit pattern
sitting in the code. An instruction that needs an address is followed by a
template, and the machine searches outward from that point for the
**complementary** pattern — `0` matches `1`:

```
address:   100  101  102  103  104   ...   119   120  121  122  123
content:  nop1 nop1 nop1 nop1 adrb   ...  adrf  nop0 nop0 nop0 nop1
          └──── the pattern ────┘          └── template 0001 ──┘
                1111

the adrf at 119 reads the template 0001 that follows it,
complements it to 1110, searches forward for those four cells,
and puts the address of the match into ax.
```

So `adrb .t 0000` means "search backward for `1111`", and `call .t 0011` means
"search for `1100` and call whatever follows it". Three consequences, and every
result on this page comes from one of them:

* a creature that gains or loses cells still finds its own parts, because
  nothing is addressed numerically — this is what makes the genome *evolvable*;
* the search does not stop at the edge of a creature, so a creature that has
  lost its own copy loop finds its **neighbour's** — this is where parasites
  come from;
* a host that changes the pattern naming its copy loop becomes invisible to a
  parasite hunting the old one — this is where immunity comes from.

**Asymmetric protection.** Reads, searches and jumps go anywhere in the soup.
Writes only land in a creature's own genome or in its daughter block. One
creature can *use* another's code without being able to corrupt it.

**Three pressures and nothing else.** The scheduler hands every living creature
a slice of instructions in turn. When the soup fills past 80%, or when an
allocation fails, the reaper kills from the head of a queue that creatures climb
by making errors and descend by reproducing. Cosmic rays flip bits anywhere; the
copy instruction occasionally miscopies. There is no fitness function in the
code.

## The ancestor

Sixty-four instructions, written by hand, and the only thing ever placed in the
soup. It does one thing in a loop: work out where it begins and ends, ask for
that much memory, copy itself into it, split the copy off, repeat.

**Phase 1, measure yourself.** There is no number 64 anywhere in the genome. The
creature finds two patterns and subtracts their addresses, every single time:

```
start:  .t 1111             ; a marker: not code, a pattern to be found
        adrb .t 0000        ; search backward for 1111 -> ax = my first cell
        pushA               ;   keep it
        adrf .t 0001        ; search forward for 1110 -> ax = my END marker
        popB                ; bx = my start
        subCAB              ; cx = ax - bx, the distance between the markers
        incC incC incC incC ; plus the four cells of the END marker = my length
```

That is why a mutated descendant of a different length still works: it measures
whatever it has become.

**Phase 2, ask for room.** `mal` allocates `cx` cells and reports the address in
`ax`. The three pushes and three pops that follow just load the copy loop's
arguments — source in `ax`, destination in `bx`, count in `cx`:

```
        pushB pushC         ; stack: [start, length]
        mal                 ; ax = where the daughter will live
        pushA               ; stack: [start, length, daughter]
        popB popC popA      ; bx = daughter, cx = length, ax = start
```

**Phase 3, copy.** `movii` copies one cell from `[ax]` to `[bx]`; the rest of the
loop advances the pointers and counts down:

```
        call .t 0011        ; search for 1100 -- the copy procedure
...
copy:   .t 1100             ; the procedure's name
loop:   .t 1010             ; the loop's name
        movii               ; daughter[bx] = self[ax]
        decC incA incB      ; one fewer to go, advance both pointers
        ifz                 ; when the count hits zero, fall through to ret
        ret
        jmpb .t 0101        ; otherwise search backward for 1010 and go round
end:    .t 1110             ; the marker phase 1 looks for
```

Six instructions per cell copied — the number every evolved descendant here is
measured against. And note that the copy procedure is reached by *searching for
a pattern*: a creature whose own copy loop is damaged will find a neighbour's
and run it. Parasitism was not designed in; it is what this addressing scheme
does when a genome is broken.

**Phase 4, divide and repeat.**

```
        divide              ; the daughter becomes an independent creature
        jmpb .t 0000        ; search backward for 1111 -- back to phase 1
```

Running it, with the copy loop folded into a single line (`python3 -m soup
trace`):

```
      4  adrb     ax=0      bx=0      cx=4      daughter=None     found itself at 0
     10  adrf     ax=60     bx=0      cx=4      daughter=None     END marker at 60
     16  subCAB   ax=60     bx=0      cx=60     daughter=None     60 = 60 - 0
     20  incC     ax=60     bx=0      cx=64     daughter=None     its true length
     23  mal      ax=64     bx=0      cx=64     daughter=(64, 64) 64 cells at 64
     27  popA     ax=0      bx=64     cx=64     daughter=(64, 64) source, dest, count
     28  call     ax=0      bx=64     cx=64     daughter=(64, 64) into the copy loop
        ↺ 63 iterations of the loop at 48..54 (6 instructions each), cx 64 -> 2
     53  ret      ax=64     bx=128    cx=0      daughter=(64, 64) all 64 copied
*    33  divide   ax=64     bx=128    cx=0      daughter=None     a new creature
```

**410 instructions** from start to daughter, 407 for every replication after
that, zero errors, and not one cell read or executed outside itself. Those are
the numbers every result below is measured against, and a unit test pins them.

One caveat, found late and worth carrying while you read: that 410 is measured
with the creature alone in an empty dish. For the ancestor it is honest — a
population of ancestors spends 468 instructions per birth, a fifth more — but
for some evolved descendants the solo figure is off by a factor of a hundred.
Wherever a cost appears below, finding 18 is the reason to check which one it is.

## What happened

Twenty findings, in the order they were found. If you read one row of this
table, make it the last column: several of these corrected an earlier answer of
mine, and two of them corrected the instrument rather than the result.

| # | what | the number |
|---|---|---|
| 1 | with mutation off, nothing changes, ever | 218,916 births, one genotype |
| 2 | two housekeeping policies decide whether mutation is even needed | 0 vs 3,092 failed allocations |
| 3 | with mutation on, an ecosystem | 164–205 genotypes alive at once |
| 4 | descendants get cheaper by getting shorter | 410 → 401 instructions per daughter |
| 5 | at three billion instructions, the copy loop unrolls | 216 instructions, 38 cells |
| 6 | the faster replicator loses; its mutants are 21× worse | 239 vs 5,109 |
| 7 | parasites, and a genotype whose CPU is captured | 45 cells, no copy loop |
| 8 | a host that became immune, by losing the pattern parasites hunt | 87% of reproduction saved |
| 9 | most variants are broken, most births are not | 28% vs 85% |
| 10 | genome length follows the CPU scheduler | 57–62 cells vs 77–106 |
| 11 | a parasite needs its whole community, not just its hosts | 58 survive vs 0 |
| 12 | the error threshold sits where theory puts it | one mutation per genome |
| 13 | the mutation mode I was missing doubles the rate of evolution | 64 → 27 cells |
| 14 | about a hundred distinct behaviours, however many genomes | 22–121 phenotypes |
| 15 | evolvability is expensive | a fifth of all reproduction |
| 16 | a flaw kills the daughter, a copy error edits her; the two editing sources multiply | 2% vs 29% viable; 141 predicted, 18 observed |
| 17 | four seeds stop at the same length; shorter and better exists one deletion away | 27 cells, and 9 of 13 shorter variants win |
| 18 | the cost of a daughter alone is not its cost in a population | 178 alone, 1,573 in company |
| 19 | both evolved endpoints are frozen; only one of them is an optimum | 38.0 cells after a billion more |
| 20 | a second ancestor reproduces the compression findings — and at three billion, one run becomes a community where nothing can reproduce alone | 8.4M births, 0 self-sufficient genotypes |

### 1. With mutation off, nothing ever happens

100M instructions, no copy errors, no cosmic rays: **218,916 births, exactly one
genotype, mean genome length 64.0 throughout, zero allocation failures.** The
population sits at ~412. Every result below is measured against a world that is
demonstrably capable of doing nothing at all.

### 2. Two housekeeping policies decide whether mutation is optional

A failed `mal` is a mutagen. The mechanism is exact:

1. no free gap is large enough, so `mal` fails;
2. it leaves `ax` holding what it already held — the address of the creature's
   own END marker;
3. the copy loop runs anyway and writes there;
4. the START marker lands on top of the END marker — a write into its own
   genome, which is permitted;
5. the creature can no longer measure itself. Its `adrf` now finds the *next*
   creature's END marker, it computes twice its true length, and its daughters
   come out double-length.

Whether that ever reaches the population turns out to depend on two decisions
that look like implementation detail:

| reaper runs when | errors hasten death | `mal` failures | genotypes seen |
|---|---|---:|---:|
| on allocation failure | yes | 0 | 1 |
| on allocation failure | no | 0 | 1 |
| only once per pass | yes | 212 – 1,982 | 1 |
| only once per pass | no | 50 – 3,092 | **2 – 3** |

(Five soup sizes per row, 5M instructions each, both mutation switches off
throughout.  Run for four times as long in the soup where the effect is
strongest, the last row reaches 11,182 failures and three genotypes while the
row above it reaches 3,565 failures and stays a monoculture.  Full tables in
`experiments/REPORT.md`.)

A reaper that runs the moment an allocation fails keeps room available, and the
mutagen never fires at all. With a lazy reaper the soup sits permanently full —
every creature holding a daughter block occupies twice its own length — and
`mal` fails hundreds of times per million instructions. Even then nothing
escapes, because the errors that damage a creature also move it up the death
queue. Only when *both* safeguards are off do the double-length daughters
survive to found lineages.

I did not design this mutagen, and I got both policies wrong on the first
attempt. That is the finding: in a world this small, resource-management policy
is not infrastructure, it is selection.

### 3. With mutation on, an ecosystem

Three seeds, 100M instructions, 60,000 cells, one copy error per 1,000 cells
copied, one cosmic ray per 2,000 instructions:

| | |
|---|---|
| genotypes alive at once | 164 – 205 |
| Shannon diversity | 6.1 – 7.2 bits |
| distinct genotypes ever seen | 24,352 – 26,920 |
| births | 171,721 – 175,651 |
| reproducing creatures that had executed foreign code | 10%, 13% … and 55% |

That last row is not noise around a mean. Two of the three seeds produced a
quiet world of self-sufficient replicators; the third produced a world where
parasites hold a fifth of the population. Same rules, same parameters, same
ancestor — the ecology forked on the seed.

### 4. A shorter, cheaper replicator

Every constant-slice run converges on genomes slightly shorter than the
ancestor's 64 cells (finding 10 is about why the other condition does the
opposite), and they are faster in proportion. The cheapest self-sufficient
replicator found by a random survey of one run's gene bank needs **389
instructions** against the ancestor's 410 — 5% less work per daughter, at 61
cells — and the ones that dominate censuses sit at 401–411 instructions with
breeding fidelity above 0.9.

The saving is almost exactly the copy-loop iterations no longer needed: about
six instructions per cell removed. Nothing in the machine knows what a genome
is, what length means, or that shorter is better.

**Up to 400M instructions that is the only way it ever gets cheaper.** Across 33
runs — 60M to 400M instructions, eight mutation rates, both scheduling rules —
the cost per cell copied stays between 6.26 and 6.56 against the ancestor's
6.41. Not one of them improved the copy loop itself; every gain was compression.

Reading Ray's paper said why: his runs were fifteen billion instructions and
mine were four hundred million. So I ran three billion, and the copy loop
finally moved.

### 5. At three billion instructions, the copy loop unrolls

Two runs of three billion instructions each — about 18,000 generations and eight
to nine million births apiece — reached two different answers. One compressed to
**37 cells at 239 instructions** with the ancestor's copy loop untouched (6.46
per cell). The other found something else.

The champion of that run is `0038rdr`: **38 cells, 216 instructions per
daughter**, held by 134 of the ~660 living creatures with a breeding fidelity of
0.99. Against the ancestor's 64 cells and 410 instructions
that is 1.9× the efficiency — and this time not by compression alone. Its copy
loop is:

```
    24  movii          ; copy a cell
    25  decC
    26  incA
    27  incB
    28  movii          ; copy the next one, without going round again
    29  decC
    30  incA
    31  incB
    32  ifz
    33  ret
    34  jmpb
```

Ten instructions, **two cells per iteration — five instructions per cell instead
of six.** This is loop unrolling, the same innovation Ray reports for Tierra,
where an evolved creature used 18 instructions to copy three cells (six per
cell, down from ten).

It found a second trick too. The `ret` at the end of the loop lands on cell 0,
and the creature's first five instructions are `adrb`, `decC`, `movBA`,
`divide` — so division happens at the *top* of the genome, on the way back into
the next replication, and the loop-back costs nothing. The first pass through
those cells, before anything has been allocated, simply throws an error and
continues.

Between them, compression and unrolling: 64 cells → 38 (−41%), 6.41
instructions per cell → 5.68 (−11%), 410 per daughter → 216. Ray's runs went
further on both counts (80 → 22 cells, 10 → 6 per cell, 839 → 146, a 5.75×
gain) — with five times more instructions to do it in.

That only one of two runs found the unrolling is itself a replication: Ray
reports that different runs reach different plateaus and cannot easily get past
them, his own stopping at 22, 27 and 30 instructions.

### 6. The faster replicator loses, and its mutants explain why

Two replicators came out of those runs: the 37-cell one at 239 instructions with
the ancestor's copy loop, and the 38-cell one at 216 with the loop unrolled. By
every measure in this repository the second is the better organism — 10%
cheaper per daughter, and only one cell longer.

Put them in a soup together and it loses.

```
$ python3 experiments/flatness.py
  cosmic ray every  seed    flat   sharp   flat /cell  sharp /cell
                 0     1     109     104         6.46         5.68   a periodic orbit
        20,000,000     1     117      96         6.46         5.68
         5,000,000   1-3  115,119,111   98,94,102  6.46        5.68
         2,000,000   1-3  163,146,113   83,68,100  6.46        5.68
           800,000   1-3  216,216,216      0,0,0   6.46            —   extinct in every seed
           200,000     1     216           0       6.46            —
```

The reason is in the neighbourhoods. Flip every bit of every cell in turn and
culture each mutant alone:

| | mutants that still replicate | mutants unchanged in cost | **mean cost of the survivors** |
|---|---:|---:|---:|
| flat, 37 cells, 239 | 32% | 24% | **239** |
| sharp, 38 cells, 216 | 31% | 17% | **5,109** |
| ancestor, 64 cells, 410 | 34% | 25% | 416 |

Both genotypes tolerate mutation about equally often. The difference is what
survival is worth: a mutated descendant of the flat replicator costs what its
parent cost, while a mutated descendant of the unrolled one, if it works at all,
averages **twenty-one times** its parent's cost. The unrolled loop sits on a
spike; the plain one sits on a plateau. Under mutation the spike keeps throwing
off crippled children that burn CPU, and that costs more than the 10% its speed
saves.

This is survival of the flattest — Wilke, Wang, Ofria, Lenski and Adami,
*Nature* 2001 — arriving in a system built without it in mind, and it explains
something in this repository's own history: unrolling appeared in one of two
deep runs and never spread.

Two cautions, both of which cost me a wrong answer first.

**Count lineages, not genotypes.** With any noise at all, the seeded genotypes
disappear within a few million instructions — not because they lost but because
their children are no longer bit-identical. Counting exact genomes said the
faster replicator was winning at low noise; counting descendants says the
opposite. The instrument was reporting mutation, not competition.

**Outside the window, the comparison degenerates.** Below one ray per 200,000
instructions the faster lineage becomes numerous again — but its surviving
members then replicate at 95 instructions per cell instead of 5.68. They are
descendants in name only, and the count no longer measures anything about the
innovation. I have no established explanation for that regime; the plausible one
is that two effects scale differently — exposure to damage per replication rises
with how long a replication takes, while fragility depends on where the genome
sits — but I have not tested it.

**So is robustness itself under selection?** Measure the same neighbourhood for
the best replicator each run produced, ordered by how long the run was
(`python3 experiments/robustness_arc.py`):

| champion | run | cells | cost | mutants that still replicate | of all mutants, within 10% of the parent's cost | median cost of survivors |
|---|---:|---:|---:|---:|---:|---:|
| ancestor | — | 64 | 410 | 34% | 31% | 410 |
| `0062ftk` | 100M | 62 | 402 | 43% | **40%** | 402 |
| `0057fln` | 400M | 57 | 373 | 42% | **40%** | 373 |
| `0053abg` | 60M at 8× mutation | 53 | 346 | 45% | **45%** | 346 |
| `0037vvz` | 3B | 37 | 239 | 32% | 32% | 239 |
| `0038rdr` | 3B | 38 | 216 | 30% | **23%** | 216 |

Two movements. Early evolution **buys** robustness: the fraction of all
single-bit mutants that still replicate at within 10% of the parent's cost rises
from 31% to 40%, and the flattest genome of the lot came out of the run at eight
times the standard mutation rate — which is exactly where quasispecies theory
says flatness should be selected hardest.

Then deep compression **spends** it. The two 3-billion-instruction champions,
compressed to 37 and 38 cells, are back down to 32% and 23%. Squeezing a genome
removes the slack that made mutations survivable.

The median survivor tells the other half of the story: for every genome here it
is *exactly the parent's cost*. The typical viable mutant is free; it is the
tail that differs, and for the unrolled replicator that tail averages 5,109.

### 7. Parasites

In the odd seed out, the top *seven* genotypes are all host-dependent, led by
`0045adk` at 106 of 507 creatures with a breeding fidelity of 0.85 — a lineage,
not an accident.

It is recognisably the ancestor's main body, shifted two cells along by a
lengthened START marker and truncated at 45: the entire copy procedure is gone,
and with it the only occurrence of `1100` in its genome. Its `call` still seeks
`1100`. The search therefore leaves its own body, finds a *neighbour's* copy
loop, runs it with its own registers — and what comes out is a copy of itself.

Distinguishing that from its opposite takes an experiment, not a reading of the
genome. Each genotype is cultured alone in a sterile medium — filled with a
non-template instruction, so a search can only ever match real code — then
beside one host, with every birth attributed to the genome it actually produced:

```
$ python3 -m soup interactions experiments/results/baseline-s2.json
           4nye 0aea stor
  0045adk     P    .    P   (host-dependent)
  0049abh     P    .    P   (host-dependent)
  ... seven more, all identical ...

P = guest copies itself using the host's code (parasitism)
H = guest spends its own CPU copying the host (its CPU was captured)
. = the guest does not reproduce beside this host
```

The `H` category is not hypothetical, and the difference between the two is a
matter of one marker. Cut the ancestor's copy procedure off at exactly the same
place — 45 cells, like the evolved parasite — but leave the `1100` marker that
named it. Its `call` still finds that marker, jumps to where the copy loop used
to be, runs off the end of its own genome, and lands in the top of the
neighbour's body. The neighbour's self-inspection then runs on the neighbour's
coordinates, and the daughter is a copy of the **host**:

```
truncated-at-45 beside the ancestor: offspring={'host': 1}, foreign calls=66
```

It spends its entire CPU allowance making its neighbour's children. From the
genome alone it is indistinguishable from a parasite; it is the exact inverse.
The evolved `0045adk` lost that marker too, which is what sends its `call` past
its own body and into the host's copy loop — and turns the same truncation from
donor into parasite.

### 8. A host that became immune, and what immunity is

The empty column above is the interesting one. `0070aea` is a perfectly healthy
70-cell replicator that all nine parasites in that run fail to exploit.

The reason is mechanical: parasites search for the four-cell pattern `1100`, and
`0070aea` does not contain it anywhere. Its own copy loop is reached by a
three-bit template instead. It is immunity by receptor loss — the pathogen's key
no longer matches any lock in the host.

```
$ python3 -m soup resistance experiments/results/baseline-s2.json
      host  size  births alone  births infected  parasite births  captured
   0064nye    64           394             52.8            210.2     79.6%
   0070aea    70           403            276.9              0.0      0.0%
```

A susceptible host loses **87%** of its reproduction to a single neighbour, and
parasites capture four fifths of all births in the dish. The immune one gives up
nothing to the parasite and keeps 69% of its solo rate — the remainder is simply
the cost of sharing a finite soup with a useless neighbour.

Immunity here is not a trade-off. A unit test builds the same defence by hand —
move the host's copy-loop marker from `1100` to `1101` and fix the one template
that points at it — and the resistant host replicates at exactly the ancestor's
410 instructions while the parasite beside it produces nothing at all. The
immune genotype that actually evolved is 10% slower than its susceptible
neighbour (452 against 410 instructions), but that is because it is 70 cells
long, not because it is immune.

### 9. Most variants are broken; most births are not

Take one run's entire gene bank — every distinct genome that ever appeared, most
of them once — and culture a random sample of 150 properly:

| | replicators | host-dependent | self-assisted | inert |
|---|---:|---:|---:|---:|
| sampled uniformly over genotypes | 28.0% | 64.0% | 3.3% | 4.7% |
| sampled weighted by births | 84.7% | 13.3% | 0.7% | 1.3% |

Most *variants* cannot reproduce alone. Most *births* produce something that
can, because the things that work are the things doing the reproducing. The gap
between those two rows is mutational load, measured.

### 10. Genome length follows the CPU scheduler

Give every creature the same slice of CPU regardless of size and length should
fall, because a shorter genome reaches `divide` sooner. Give each creature a
slice proportional to its length and that pressure disappears. Ten runs, five
per condition, seeds and lengths matched so that a 64-cell creature receives
exactly the same 20 instructions per turn in both:

| condition | mean genome length in each run |
|---|---|
| constant CPU slice | 57.1, 58.5, 60.6, 61.4, 62.5 |
| slice proportional to length | 77.2, 78.3, 78.3, 81.9, 105.7 |

No overlap. The ancestor is 64. Every constant-slice world ends up shorter than
it, every proportional-slice world longer.

An earlier version of this experiment, run before I found the reaper defects
described in finding 2, showed nothing at all — the seed-to-seed spread swamped
the difference. The effect was there; the noise from a broken death queue was
larger.

### 11. Immunity is worth something in a dish, but I could not show it being selected

Finding 8 is an observation. The demonstration would be that immunity *spreads*
when there is something to resist, so: seed a soup with equal numbers of the
ancestor and a hand-built resistant variant (copy-loop marker moved from `1100`
to `1101`, one template corrected, **410 instructions per daughter — an exact
tie**), let it fill up, then introduce six copies of the evolved parasite. No
mutation anywhere, so nothing changes except who reproduces.

| soup | final susceptible | final resistant | final parasites |
|---|---:|---:|---:|
| both hosts, no parasites | 110, 108 | 108, 110 | 0, 0 |
| both hosts, parasites introduced | 62, 64 | 57, 62 | 7, 0 |
| susceptible only, parasites introduced | 126, 126 | — | 0, 0 |
| resistant only, parasites introduced | — | 125, 125 | 0, 0 |

(two seeding layouts per row, 20M instructions each.)

The control works exactly as intended: without parasites the two hosts stay
level, which is what an exact tie in replication cost should produce. But the
parasite barely establishes — seven survivors in one layout, extinct in the
other — and in a soup of nothing but susceptible hosts it dies out completely.
The immune host gains nothing measurable.

Something about the parasite does not survive transplantation. In its own run it
held a fifth of the population; introduced into a naive one it cannot hold on at
all. The likeliest explanation is that a parasite is co-adapted to the
neighbourhood it evolved in — the exact templates its `call` finds, and how far
away they sit — and a monoculture of the ancestor is a different world. Seeded
into an *empty* soup it does reproduce (thirty daughters from eight parasites in
the first 200k instructions) and then dies out anyway, because the allocator
puts those daughters in the empty part of the world where no host is within
search range. Parasitism needs a crowd, and apparently a familiar one.

**A later experiment answered most of this** (`experiments/coadaptation.py`).
The question was why a parasite that held a fifth of its own run cannot live
anywhere else, and the answer is that it needs its whole community, not just its
hosts. Six copies introduced into a saturated soup, no mutation, counted as
descendants of the ones introduced:

| the community it was put into | parasite lineage after 25M instructions |
|---|---:|
| ancestors only | 3 |
| its own susceptible host, alone | 0 |
| the two replicators from its own run | 0 |
| **its whole census — eleven genotypes, seven of them parasites** | **58** |

A soup of hosts is not the environment it evolved in. A soup that is mostly
parasites is, and only there does it hold on.

Two further things fell out. With mutation switched on, the parasite's exact
genome keeps being **re-created** from its hosts — bursts of 19, 34, 65 copies
appear from mothers of other genotypes — and each burst dies back within a few
million instructions. It exists there as a recurrent mutation rather than a
lineage. And with mutation off, its lineage survives in the ancestor soup while
containing none of its own genome: its daughters are copies of the *host*, so
the line persists by becoming what it feeds on.

What remains unexplained is narrower than before: in the run where it arose it
bred true 85% of the time, and no reconstruction I have built reproduces that.

### 12. Mutation rate: an optimization peak, and an error threshold exactly where theory puts it

Ray reports two things about Tierra that pull against each other: optimization
is best "at the highest mutation rate that does not cause instability", while
ecology is richer at slightly lower rates. Quasispecies theory adds a third
expectation — above about one mutation per genome per replication a population
can no longer hold onto its information and melts.

Twenty-four runs, eight rates, three seeds each, 60M instructions apiece. Both
of this world's mutation rates are multiplied by the same factor *k* — which is
the flaw in this experiment, found much later and written up as finding 16: copy
errors and cosmic rays move together in every run in this repository, so the
threshold below is a threshold on the two of them jointly and this experiment
cannot say which one carries it. With that said, k=1 is
the standard setting and µ is the resulting mutations per 64-cell genome per
replication:

| k | µ per genome | generations reached | cheapest replicator (3 seeds) | breeders running foreign code |
|---:|---:|---:|---|---:|
| 0.25 | 0.016 | 367 | 387, 399, 406 | 53% |
| 0.5 | 0.032 | 360 | 384, 392, 378 | 43% |
| 1 | 0.064 | 347 | 387, 407, 402 | 11% |
| 2 | 0.128 | 319 | 403, 408, 394 | 12% |
| 4 | 0.256 | 230 | 413, —, 403 | 42% |
| 8 | 0.512 | 243 | **379, 365, 346** | 35% |
| 16 | 1.016 | **10** | none evolved | 100% |
| 32 | 2.065 | **4** | none evolved | 100% |

**The optimization peak is real.** At eight times the standard rate all three
seeds found replicators cheaper than anything at any other rate, the best at 346
instructions against the ancestor's 410 — a 16% saving. Ray's claim holds here.

**The error threshold is where theory says it should be.** Between µ = 0.51 and
µ = 1.02 — one mutation per genome per replication — the population stops being a
population. At k=16 the only self-sufficient replicators left anywhere in the
three censuses are the unmodified ancestor and one-mutation variants of it, each
down to a single individual; everything evolution had built is gone. One of the
runs has **132 distinct genotypes alive among 133 creatures** — no two
individuals alike, because nothing copies itself accurately enough to found a
lineage. Generation depth collapses from ~250 to 10, and 100% of reproduction
happens through foreign execution. The soup does not go extinct; it persists as
a churn of fragments running each other's code.

**Adding a third mutation source moves the threshold down, by exactly as much
as it should.** The sweep above was run again on a compute server with
instruction flaws switched on at one per 1,000 (finding 13), two seeds each:

| k | generations, flaws off | generations, flaws on | cheapest replicator, flaws on |
|---:|---:|---:|---|
| 1 | 347 | 336, 336 | 386, **327** |
| 2 | 319 | 311, 310 | **334**, 360 |
| 4 | 230 | 281, 275 | **321**, 351 |
| 8 | 243 | **41**, 221 | none, 380 |

At eight times the standard rate, which was comfortable without flaws, one seed
of two now collapses: 41 generations, 79 creatures left, 7,366 births against
the 84,000 of its neighbours, and no self-sufficient replicator anywhere in the
census.

The arithmetic works out. A flaw every 1,000 instructions costs a creature
about **0.4 events per replication**, since a replication is around 400
instructions. Copy errors at k=8 cost about 0.5 per genome. Together that is
0.9 — just under the one-per-replication threshold, which is precisely where a
population should start failing to hold onto itself. The threshold has not
moved; what moved is how much of the budget was already spent.

And in the middle of the range, flaws buy what a higher mutation rate used to:
the cheapest replicators at k=2 and k=4 (321–360) beat anything the flawless
sweep found below k=8.

**The ecology claim I cannot support.** Averaged over seeds the parasite
indicator is highest at the lowest rates, which is the direction Ray describes.
But the within-condition spread is 0.12 to 0.85 at the same rate — as large as
the effect. Three seeds are not enough to say anything here, and I am not going
to pretend otherwise.

### 13. The mutation mode I was missing doubles the rate of evolution

Tierra has three mutation modes; this world had two. The missing one is
*flaws*: at a low rate, an instruction's result comes out off by one. It sounds
like a footnote and is not, because the two modes here could only ever swap one
instruction for another. A flawed `mal` asks for the wrong amount of memory and
a flawed `movii` writes to the wrong cell — which is how a soup gets
**insertions and deletions** at all.

With both other mutation sources switched off, flaws alone take a population
from one genotype to eight hundred in two million instructions.

Switched on alongside the usual mutation, in nine runs of 60M instructions:

| flaws | cheapest replicator (3 seeds) | mean genome length | genotypes explored | generations |
|---|---|---|---:|---:|
| off | 387, 407, 402 | 63.2, 63.0, 61.8 | ~15,000 | ~347 |
| one instruction in 5,000 | 368, 390, 401 | 57.1, 62.5, 63.9 | ~19,600 | ~347 |
| one instruction in 1,000 | **386, 327, 332** | 62.5, **50.9**, 59.4 | **~30,000** | ~337 |

Twice as many genotypes tried in the same time, and replicators a fifth cheaper
than the ancestor found in 60 million instructions — a level the flawless runs
did not reach until three billion. Generation depth is unchanged, so this is not
a matter of running faster; it is a matter of exploring a larger space.

**Given a deep run, flaws take the genomes further than anything else has.** Two
runs of 1.5 billion instructions with flaws on, against the earlier ones without:

| | mean genome length | best replicator | repeats? |
|---|---:|---|---|
| no flaws, 3 billion | 37.2, 38.0 | 239 and 216 instructions, 37 and 38 cells | yes |
| no flaws, ~4 billion (killed early) | 38.8, 45.9 | — | — |
| **flaws, 1.5 billion** | **37.2, 27.1** | **240 at 37 cells; 178 at 27 cells** | yes; **no** |

Half the instructions, and one of the two seeds went to 27 cells — below
anything the flawless runs reached. Ray's Tierra plateaued at 22, 27 and 30.
Four more seeds and two ten-billion runs later, 27 turns out to be where this
world stops; that is finding 17.

**But read that last column.** My headline number all along has been the cost of
a creature's *first* daughter, and the 27-cell champion makes exactly one. It
spends 178 instructions on a daughter and then walks off the end of its own
counter into an error loop, accumulating errors until the reaper takes it. The
ancestor, by contrast, produces a daughter every 407 instructions indefinitely.

One-shot reproduction is not a defect. In a soup at steady state every creature
needs exactly one surviving child on average, and a creature that produces it
fast and then dies fast frees the memory its child needs. That genotype held a
fifth of its population and recorded 143,670 births.

But it only works where everyone does it. Put the two champions of the two flaw
runs in one soup — the 27-cell one-shot against the 37-cell repeater, twelve of
each, no mutation:

```
        one-shot 27   repeater 37
  0.0M           12            12
  8.0M           22           203
 40.0M           17           205
births       10,056       141,741
```

The repeater takes fourteen times the births and holds the soup; the one-shot
survives as a minority and never recovers. So the cheapest genome this world has
produced is not the fittest — it dominates its own run because its whole
population had lost the ability to go round again, and a single lineage that
kept it would walk in and take over. My metric could not tell the two apart
until I looked; `describe()` now reports whether a replicator can do it twice,
and the optimization table has a column for it.

**Is there a best flaw rate?** If one flaw in 1,000 is better than none, more
should be better still, up to the point where the population melts. The compute
server ran the series out to a billion instructions each — two seeds per rate,
everything else identical, the flawless runs read off the same clock in the
three-billion runs of finding 5:

| flaws | genotypes alive | generations | births | mean genome length |
|---|---:|---:|---:|---:|
| off | 225, 167 | 5704, 5638 | 2.13M, 1.97M | 42.0, 36.0 |
| one in 2,000 | 197, 207 | 5598, 5588 | 2.84M, 2.69M | 32.0, 37.1 |
| one in 1,000 | 275, 269 | 5448, 5333 | 2.64M, 3.10M | 37.2, **27.0** |
| one in 500 | 259, 311 | 5162, 5044 | 2.49M, 2.29M | 37.3, 39.1 |

Two of the four columns move monotonically and in opposite directions. Standing
diversity climbs with the flaw rate — 196 genotypes alive on average with flaws
off, 285 at one in 500 — and generation depth falls, 5,671 down to 5,103. More
flaws means more of the soup is being tried at any moment and less of it is
descended from anything that worked; births rise at the same time, so the extra
throughput is going into offspring that are dead ends.

The column I care about most does not move at all. Mean genome length spreads
further *within* a rate than *between* rates: at one in 1,000 the two seeds sit
at 37.2 and 27.0, which is the whole range covered by every other condition put
together. **Two seeds cannot pick an optimum here, and I am not going to
pretend otherwise.** The 27-cell run of finding 13 is one lineage getting lucky
in one seed, not evidence that one flaw in 1,000 is the setting that produces
27-cell creatures. Four more seeds at three billion instructions are running to
settle that; whichever way they come out, the honest reading of this table today
is that the flaw rate buys exploration and pays for it in depth, and that its
effect on how short a genome gets is smaller than the difference between two
seeds.

This also revises finding 5. I explained the slowness of optimization here by
two things: a copy loop that started at the efficiency Tierra's creatures had to
evolve, and runs a hundred times shorter than Ray's. There was a third: a whole
class of mutation that this world could not produce.

### 14. About a hundred distinct behaviours, however many genomes there are

Standish measured something in Tierra that I had not thought to: gene banks of
69,139, 87,003 and 198,982 genotypes collapsed onto **83, 86 and 158 distinct
phenotypes**. Counting genomes, as I had been doing, badly overstates how much
variety a soup contains.

The same measurement here defines a phenotype as what a genome *does* — what it
becomes cultured alone, what a daughter costs it, and what happens beside each
of two reference organisms — and estimates the total from a sample of 70 with
the Chao1 estimator out of field ecology:

| run | parasitism | phenotypes in 70 genotypes | estimated in the whole bank | bank size |
|---|---:|---:|---:|---:|
| k=0.25, seed 3 | 10% | 24 | 41 | 3,445 |
| k=0.25, seed 2 | 67% | 23 | 121 | 4,423 |
| k=16, seed 1 | 100% | 17 | 32 | 767 |
| k=32, seed 1 | 100% | 16 | 22 | 282 |

**The order of magnitude matches Tierra.** Both systems support something like
a hundred distinguishable behaviours, even though the gene banks differ
thirtyfold in size. Roughly three genotypes share every phenotype in my sample.

Standish's explanation for Tierra's missing neutrality — parasites need a host
in range, so neutral variants without one fail to replicate — makes a
prediction: the parasite-rich world should show *less* neutrality. Two runs at
the same mutation rate, differing only in seed, one at 10% parasitism and one at
67%, show 2.9 and 3.0 genotypes per phenotype. No effect. If anything the
parasite-rich world holds three times as many distinct behaviours (121 against
41), which points the other way. One seed pair, a phenotype definition that is
mine rather than his, and a noisy estimator: this is a failure to reproduce, not
a refutation.

### 15. Evolvability is expensive

The same 100M instructions bought 218,916 births with mutation off and
171,721 – 175,651 with it on: a fifth of the world's reproductive output goes on
variants that do not work. The noise that produced everything above is also the
reason the population is a fifth less productive.

### 16. A prediction, killed, and the half of it that survived

Finding 12 put an error threshold at about one mutation per genome per
replication, and finding 13 added a third mutation source. Together they make a
prediction sharp enough to be wrong: **collapse should depend on the total number
of mutational events per replication and not on which source produces them.**
Mix the three sources any way you like; hold the sum fixed; the population
should not care.

Eighteen runs of 60M instructions, six conditions, three seeds each. The ledger
was built on the ancestor: a copy error rate of *r* costs 64*r* events per
replication because a daughter is 64 cells, and a flaw rate of one in *f* costs
410/*f* because a replication takes 410 instructions.

| | copy errors | flaws | predicted events | generations reached (3 seeds) |
|---|---|---|---:|---|
| lo-c | 0.06 | 0.41 | 0.47 | 343, 343, 345 |
| lo-a | 0.26 | 0.21 | 0.47 | 301, 288, 287 |
| lo-b | 0.38 | 0.10 | 0.48 | 279, 274, 274 |
| **hi-b** | **0.26** | **0.82** | **1.08** | **282, 274, 280** |
| hi-a | 0.51 | 0.41 | 0.92 | 49, 227, 251 |
| hi-c | 0.77 | 0.21 | 0.98 | 16, 34, 32 |

The three low conditions agree with each other and with the prediction. The
three high ones destroy it. `hi-b` carries the largest predicted load of any
condition here and is indistinguishable from the healthy ones — 274 to 282
generations, mean genome length falling to 44–54 cells, the ordinary picture of
a working soup. `hi-c` carries *less* predicted load and is wrecked: 16 to 34
generations, and mean genome length climbing to 85, 124 and 157 cells instead of
falling. That upward drift is the signature of a population that can no longer
hold a working genome together.

Sort the same six conditions by the copy-error column alone and the table
becomes monotone. Sort by the flaw column and it is not: the healthiest
condition in the set has the most flaws, and the worst has half as many as the
best.

**So a flaw and a copy error are not worth the same, and I measured the
exchange rate.** `experiments/heritability.py` puts one ancestor alone in a
small soup with a single mutation source switched on, runs it to its first
daughter, and compares the daughter with the mother. 400 replications per
condition:

| source | events per replication | daughter differs | cells changed | **daughter still replicates** |
|---|---:|---:|---:|---:|
| copy 1/1000 | 0.07 | 7% | 1.0 | **10/28 = 36%** |
| copy 1/125 | 0.52 | 38% | 1.3 | **44/152 = 29%** |
| copy 1/83 | 0.71 | 50% | 1.4 | **58/200 = 29%** |
| flaws 1/2000 | 0.23 | 14% | 26.2 | **3/56 = 5%** |
| flaws 1/1000 | 0.37 | 23% | 23.6 | **1/92 = 1%** |
| flaws 1/500 | 0.70 | 42% | 22.2 | **7/168 = 4%** |
| flaws 1/250 | 1.14 | 62% | 28.0 | **5/247 = 2%** |

The last column is a proportion of the altered daughters, so its denominators
are small in the low-rate rows; the 95% intervals are 22–36% for the three copy
conditions and 0–11% for the four flaw conditions, which do not overlap.

Per event the two sources are about equally likely to produce an altered
daughter — 0.6 to 0.7 either way. What differs is what the alteration *is*. A
copy error changes one cell and the daughter still works about three times in
ten. A flaw displaces a write and the daughter comes out with twenty-odd cells
wrong; it works about one time in thirty.

That is the whole difference. **A flaw kills the daughter; a copy error edits
her.** Only the second one accumulates. A lethal mutation is a cost in
throughput — which is exactly what finding 13's table shows flaws buying, more
births and fewer generations — but it leaves the surviving lineage as faithful
as it was. An edit stays in the population and its descendants drift further.
The error threshold is a threshold on *heritable* load, and multiplying each
source's events by the fraction of altered daughters that still work puts every
healthy condition here below 0.1 and every damaged one above it.

**And now the part I got wrong before any of this.** Sorting those six
conditions by copy error rate orders them correctly — but so does sorting them
by cosmic ray rate, because in this repository the two have never been
independent. Every run ever done here, including all of finding 12, was
configured with

```
copy_mutation_rate × cosmic_period = 2.000
```

exactly, in all eleven distinct settings that have ever been used. I built the
sweep of finding 12 by scaling one knob called "mutation rate" that moved both,
and I carried the same coupling into the design above without noticing. So this
experiment shows that flaws are cheap and that the other two sources are what
matter, and it cannot say which of *those two* does the damage. Neither can
finding 12. Twelve runs crossing copy 1/1000 against 1/83 with cosmic 1/2000
against 1/167, flaws off, separated them.

**The twelve runs came back, and the answer is that neither source does it
alone.** Copy errors crossed against cosmic rays, flaws off, three seeds per
cell, 60M instructions each; the number is the generation depth reached, which
is what collapse destroys:

| | cosmic 1 in 2,000 | cosmic 1 in 167 |
|---|---|---|
| **copy 1 in 1,000** | 350, 353, 354 | 252, 193, 252 |
| **copy 1 in 83** | 270, 274, 270 | **15, 22, 15** |

Twelve times the copy error rate, on its own, costs about a quarter of the
generation depth and nothing else: mean genome length still falls to 60 cells,
the census still fills with working replicators. Twelve times the cosmic ray
rate, on its own, costs about the same. Both at once and the world stops
evolving in the first fifty million instructions, with genomes bloating to 102,
114 and 108 cells.

Collapse here means what the word should mean, not merely a slower world. In
the healthy corner all twelve census entries are self-sufficient replicators,
already optimized to 387–407 instructions. In the collapsed corner the census is
eleven or twelve pieces of debris — inert fragments and host-dependent
leftovers — with at most one replicator among them, and that one still at the
ancestor's 414 to 421 instructions. The population is no longer holding a
working program.

So the original prediction was half right, and the half that was wrong is the
one I could not have guessed. **The two sources that edit share a budget; the
one that kills does not draw on it.** Copy errors and cosmic rays both leave a
working daughter carrying a changed genome, and either one alone at twelve times
its usual rate is survivable while the two together are not. Flaws leave a
corpse. A corpse costs the population a birth and carries no information
forward, so no amount of it moves the threshold, which is why `hi-b` could carry
0.82 flaws per replication and not notice.

What this design cannot tell you is the *shape* of that shared budget. A 2×2
with one level of each is consistent with loads that simply add and a threshold
somewhere between one source's worth and two, and equally consistent with the
two interacting — a genome already carrying copy errors being more easily
finished off by a ray. Separating those needs a dose–response grid, not four
corners.

**The grid is in, and the two do not simply add.** Three copy rates crossed with
three cosmic rates, flaws off, two seeds each, generation depth reached in 60M
instructions:

| | cosmic 1/2,000 | cosmic 1/500 | cosmic 1/167 |
|---|---:|---:|---:|
| **copy 1/1,000** | 354, 353 | 303, 320 | 252, 193 |
| **copy 1/250** | 332, 320 | 289, *124* | 254, 200 |
| **copy 1/83** | 270, 274 | 248, 264 | **15, 22** |

Move either knob on its own from the mildest setting to the harshest and it
costs about a quarter to a third of the generation depth: 354 down to 272 for
copy errors alone, down to 223 for rays alone. Move both and it costs
ninety-five per cent. An additive model predicts 141 generations for that
corner and a multiplicative one predicts 171; the observed value is 18.

So the two editing sources are **synergistic, not additive**, by a factor of
about eight. That is what the 2×2 could not say and it is worth saying plainly,
because the ledger arithmetic in this finding — events per replication, summed
across sources — is exactly the model the corner refutes. Whatever the right
quantity is, it is not a sum.

The italicised 124 is the other thing to notice. At copy 1/250 with cosmic
1/500, one seed reached 289 generations and the other collapsed to 124 with mean
genome length at 38 cells and not one self-sufficient replicator left in its
census, while its twin kept eleven.

Six more seeds of that exact cell came back at 284, 290, 291, 292, 294 and 295
generations, every one of them with twelve replicators out of twelve. **So the
cell is not on the boundary: it is comfortably inside the healthy region, and one
run in eight died anyway.** That is a different thing from a threshold, and the
more interesting one — collapse here has a stochastic component that does not
show up in the mean of two seeds. Anywhere this document reports a condition as
healthy on two or three seeds, a rate like one in eight is invisible to it.

That also settles what finding 12 measured. Its sweep moved both editing
sources together, so its threshold — one mutation per genome per replication —
is a threshold on their sum, and the cross above says the sum is the right thing
to have measured. It was the right answer for a reason I had not established.

### 17. Twenty-seven cells, four times over — and it is not a floor

Finding 13 ended with a 27-cell replicator and an open question: was that a
floor, or one lineage getting lucky in one seed? The compute server ran four
more seeds to three billion instructions and two to ten billion.

| run | length | cost alone | in a population | does it go round again? |
|---|---:|---:|---:|---|
| 1.5 billion, seed 2 | **27** | 178 | 1,687 | no |
| **3 billion, seed 5** | **27** | 180 | **219** | **yes** |
| 3 billion, seed 6 | **27** | 178 | 1,573 | no |
| 3 billion, seed 7 | 32 | 207 | **235** | **yes** |
| 3 billion, seed 8 | 35 | 226 | 1,802 | no |
| 10 billion, seed 9 | 34 | 219 | 23,566 | no |
| **10 billion, seed 10** | **27** | 181 | **238** | **yes** |

The last two columns arrived a day after the rest of this finding and changed
it; both are finding 18. The short version is that four of these seven champions
make one daughter and then thrash, so their solo cost is not what they cost, and
the two columns agree exactly on which four.

**Twenty-seven cells, four times, from four independent seeds, and ten billion
instructions did not go below it.** The four genomes are not the same genome:
they differ in eight to thirteen of their twenty-seven positions. Disassembled
they are plainly the same program: two template searches to find their own ends,
the same length arithmetic, one `mal`, and the same four-instruction copy loop
closed by `ifz`. What differs is the register plumbing around it and whether the
loop exits through `ret` or straight into `divide`. Put through the phenotype
panel of finding 14 they are indistinguishable — independent replicators, 178 to
181 instructions, dependent on nobody. Four separate searches arrived at one
design.

The size histogram says the same thing about the population and not just its
champion: at the end of the ten-billion run 798 of the 911 living creatures are
exactly 27 cells, and the six commonest lengths — which cover 903 of them — are
25 through 29 plus a stray 31. The tail below 27 is there in every deep run and
never grows.

**It does not rescue finding 13's worry, which I briefly thought it had.** For a
few hours this section said three of the four 27-cell champions go round again,
so the one-shot strategy was that lineage's and not the length's. That was the
`repeats` flag counting the wrong births — finding 18 — and with the flag fixed
the score is two of four. Seeds 5 and 10 found a genuine repeating 27-cell
creature; seeds 2 and 6 found one-shots at the same length and the same solo
cost. So the length does not force the strategy, and neither does it come free
with it: both exist at 27 cells and they cost their populations 219 and 1,573
instructions per birth respectively.

**What twenty-seven cells actually look like.** The whole organism, disassembled
from `flaw-3b-s6` and kept in `experiments/ancestors/short27.sm`:

```
        .t 1                 ; head marker
        divide               ; with no daughter yet this is an error, and it
                             ; costs one -- the loop below wraps into it
        adrb    ; seeks 1    ; ax <- my own start
        .t 0
        pushC
        pushA
        adrf    ; seeks 1    ; ax <- my end
        .t 0
        popB
        subCAB               ; cx <- my length
        incC
        incC
        pushB
        pushB
        mal                  ; ask for cx cells
        movBA
        popA
        .t 0

        decC                 ; --- the copy loop, and the whole life cycle ---
        movii                ; daughter[bx] <- me[ax]
        incA
        incB
        ifz                  ; when the counter reaches zero...
        divide               ; ...let the daughter go, on this same iteration
        jmpb    ; seeks 0    ; and round again, forever
        .t 1
        jmpb
```

The last block is the entire copy loop and the entire life cycle at once. The
hand-written ancestor keeps them apart: a `copy` subroutine that copies until
the counter runs out and returns, and an outer loop that calls it, divides, and
jumps back. This creature has fused the two. `ifz / divide` sits *inside* the
copy loop, so the division happens on the iteration where the counter hits zero
and the loop simply continues into the next daughter. There is no subroutine, no
`call`, no `ret`, and no outer loop — the four-instruction driver of the
ancestor and the `call`/`ret` pair have all been deleted, and what is left runs
straight into itself forever.

The templates are down to one bit. The ancestor searches for four-bit patterns
because I wrote it to be readable; a one-bit template is found sooner and costs
fewer cells to store, and nothing in this world rewards legibility.

**I wrote "twenty-seven is the floor" and then went looking for the floor.**
It is not one. Delete any single cell from each of the four 27-cell champions
and culture the result: eight to eleven of the twenty-seven deletions still
replicate, and thirteen of those still replicate *twice* — real repeating
organisms of 26 cells, costing 171 to 174 instructions instead of 178 to 181.
Keep going greedily and the deletions run all the way down to 18 cells at 116
instructions, though everything below 26 is a one-shot.

So a cheaper 26-cell repeater exists one mutation from where every one of these
runs stopped. Three explanations were available and two of them are wrong.

*Is it reachable?* Yes, easily. `experiments/spectrum.py` classifies fifteen
hundred daughters against the mothers that made them, one mutation source at a
time. Under flaws, 0.6% of births are a clean interior deletion — and 51% are a
same-length scramble, 0.6% a clean truncation, 0.9% the mother plus a tail.
Copy errors and cosmic rays never change a genome's length at all, which is
finding 13's claim about flaws, measured. The gene banks agree: a 150-genotype sample of the
ten-billion run's bank contains four 26-cell genotypes and three 25-cell ones.
The soup makes them constantly.

*Is it beaten?* Mostly not. Thirteen head-to-heads, each 26-cell variant against
the exact 27-cell champion it was deleted from, twelve of each, background noise
on: **the 27-cell parent wins four of thirteen.** Two of the losses are total —
451 to 0, 394 to 1. The shorter creature is usually the better competitor as well
as the cheaper one.

*Is it more fragile?* A little, and not reliably. In eight pairs measured, the
26-cell variant has the smaller viable one-mutation neighbourhood in six — 0.254
to 0.346 against the parents' 0.304 to 0.341. That is a real tendency and far too
small to explain a difference that four runs never crossed in ten billion
instructions.

**What is actually going on is that length here does not descend, it freezes.**
Read the trajectories rather than the endpoints:

| | 0.5B | 1B | 2B | 3B | 5B | 7B | 10B |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10 billion, seed 10 | 48.8 | 40.8 | 37.0 | **27.1** | 27.2 | 27.2 | **27.1** |
| 10 billion, seed 9 | 33.9 | 34.1 | 34.1 | 34.0 | 34.1 | 34.0 | **34.3** |

Seed 9 reached 34 cells in its first half-billion instructions and then sat
there, to two decimal places, for the next nine and a half billion — while
26-cell and 25-cell genotypes kept appearing in its gene bank and dying. Seed 10
did the same thing at 27. The steps between plateaus are quick; the plateaus are
enormous.

That changes what the number means. **Twenty-seven is not the shortest genome
this world can hold. It is where four of seven searches happened to stop, and
they stopped somewhere the population is not obviously trapped.** The honest
version of this finding is that four independent runs converged on the same
27-cell design and none went below it — and that the reason is not that shorter
is worse, because shorter is cheaper, mostly wins in a dish, and is produced
every few thousand births.

My best guess is the one thing these assays cannot test: a variant in the real
soup arrives as one individual among nine hundred and has to invade a population
of near-relatives that are all producing similar variants of their own, while
the head-to-head hands it twelve copies and one clean opponent. If that is
right, the plateaus are a population-genetics effect rather than anything about
the genomes. Twelve runs starting from the champions themselves have since
come back and they are finding 19: nothing moves, in either direction, for a
billion instructions.

**And the two mutation regimes reach the floor by different routes.** Compare
the best of the flawless three-billion runs against the best of the flawed ones:

| | length | per cell, alone | in a population |
|---|---:|---:|---:|
| no flaws, 3 billion, seed 2 | 38 | **5.68** | 261 |
| flaws, 3 billion, seed 5 | **27** | 6.67 | **219** |

The flawless run found a *better copy loop* — 5.68 instructions per cell against
the ancestor's 6.41, which is the unrolling of finding 5. The flawed runs never
find it. What they do instead is throw cells away: every flaw champion sits at
6.4 to 6.7 per cell, exactly where the ancestor sits, and gets its cheapness
entirely from being short. Insertions and deletions are good at deleting and bad
at inventing; substitutions are the other way round. Neither regime has done both
at once, and the creature that does — 27 cells at 5.7 per cell, about 155
instructions — has not appeared in any run here. Finding 20 suggests why: 6.5
instructions per cell looks like the floor of the machine itself, reached from
three independent starting points, and 5.68 is the only thing that has ever gone
under it.

Which route is ahead depends on which number you read, and the population column
is the one that decides: the short creature costs its own kind 219 instructions
per birth and the unrolled one 261. A better loop over 38 cells loses to an
ordinary loop over 27.

Ray's Tierra bottomed out at 22, 27 and 30 cells. This world reaches the middle
of that range and stops — and stopping is not the same as bottoming out. I have
since gone back to his paper, and he says the same thing about his own runs in
almost the same words; `docs/RELATED-WORK.md` quotes him. He also reports his
22-instruction creature's *second* daughter at 142 instructions against the
first at 146, so his optimization figure already carried the check that finding
18 is about, and the two smallest creatures the two systems have ever produced
turn out to be the same program instruction for instruction.

### 18. What a daughter costs a population, which is not what it costs alone

Every "cost" in this document until now came from `describe()`: put one creature
alone in a sterile dish, run it until it produces a daughter, count the
instructions. The ancestor is 410. Finding 17's champion is 178. That number has
been the headline of findings 4, 5, 13 and 17.

Checking finding 17 broke it. Starting a run from the 27-cell champion produced
a soup that made **110 births in a billion instructions** — the ancestor makes
two and a half million. So I measured the obvious thing, which I should have
measured a month ago: place sixteen copies of a genome in a soup, switch
mutation off, run, and divide the world clock by the births it bought.

| champion | cells | alone | **in a population** | errors per creature |
|---|---:|---:|---:|---:|
| the hand-written ancestor | 64 | 410 | **468** | 0 |
| 3B, no flaws, seed 1 | 37 | 239 | **245** | 0 |
| 3B, no flaws, seed 2 — the unrolled loop | 38 | 216 | **261** | 1 |
| **3B, flaws, seed 5** | **27** | **180** | **219** | 2 |
| 3B, flaws, seed 7 | 32 | 207 | **235** | 0 |
| 10B, flaws, seed 10 | 27 | 181 | **238** | 2 |
| 1.5B, flaws, seed 2 | 27 | 178 | **1,687** | 233 |
| 3B, flaws, seed 6 | 27 | 178 | **1,573** | 219 |
| 3B, flaws, seed 8 | 35 | 226 | **1,802** | 213 |
| 10B, flaws, seed 9 | 34 | 219 | **23,566** | 1,990 |

**Two creatures of exactly the same length, with solo costs of 180 and 178,
differ eightfold in what they actually cost.** Both are in
`experiments/ancestors/`: `short27r.sm` is the first, `short27.sm` the second.

The split is not random, and it is the same split as the `repeats` column. The
five champions whose solo cost transfers are the five that make a second
daughter; the four that cost seven to a hundred times more are the four that
make exactly one and then thrash. A one-shot's solo cost is the price of its
first daughter and nothing else, and after that daughter it falls out of its own
copy loop and grinds through hundreds of errors before it can start again. Alone
in an empty dish that is cheap. In a population it is the entire cost.

**And `repeats` was itself wrong until this morning.** The assay counted births
*of the genotype*, so the moment a creature's daughter divided, the mother was
recorded as having gone round twice. Every one-shot in this world has a daughter
that divides once — that is what a one-shot is — so the field said `True` for
almost everything. It now counts the mother's own births, and it agrees with the
population measure on all nine champions: exactly the repeaters transfer.

Two consequences for what is written above.

**The best creature this world has produced is the 27-cell champion of seed 5**,
at 219 instructions per birth against the ancestor's 468. That is a real
halving, and it is not the same creature I have been quoting: the one I quoted,
and turned into `short27.sm`, and started twelve runs from, is a one-shot that
costs its own population 1,573.

**The two evolutionary routes of finding 17 are not equal after all.** By solo
cost the unrolled 38-cell creature (216) and the short 27-cell one (178) looked
like two ways of arriving at the same place. By population cost the shrinking
route wins outright: 219 against 261, and a 32-cell creature from a third seed
comes in at 235, also below the unrolled one. Unrolling the copy loop buys less
than it appears to, because the loop is not where the time goes.

**What is still not measured** is what a genome costs in the mixed, mutating
soup it evolved in, as opposed to a clean population of its own kind. That is a
third number, and the gap between the second and the third is where parasitism
and template collision live.

### 19. Both endpoints are frozen, for two different reasons

Finding 17 left a question with a clean experimental answer: the flawless runs
unroll the copy loop and stop at 38 cells, the flawed runs shrink to 27 and never
unroll, so what happens if you hand each route the other one's mutation regime?

Twelve runs of a billion instructions each, started from the two champions in
`experiments/ancestors/` instead of from the hand-written ancestor:

| started from | flaws | mean length after 1B | best in the census | births |
|---|---|---:|---|---:|
| `unrolled38` (38 cells) | off | 38.0, 38.0, 38.0 | 38 cells, 215–218 | 3.6M |
| `unrolled38` (38 cells) | **on** | 38.0, 37.9, 38.0 | 38 cells, 216 | 3.2M |
| `short27r` (27 cells) | off | 27.1, 27.1, 31.2 | 27 cells, 178–180 | 3.7M |
| `short27r` (27 cells) | **on** | 27.1, 27.2, 26.9 | 27 cells, 177–180 | 3.7M |

**Nothing moves.** Not by one cell, in any of the twelve. Ray saw this in
Tierra in 1991 — "each run decreases to a size limit which it cannot proceed
past even if it is allowed to run much longer" — and concluded that the system
reaches a local optimum it cannot easily leave. The first half of that is a
replication. The second half is an inference, and it is the part these deletion
assays can test. The same billion
instructions applied to the 64-cell ancestor takes it down to somewhere between
27 and 42 cells; applied to either evolved champion it changes the mean genome
length by less than a tenth of a cell. These are not way-stations, they are
attractors, and a billion instructions of the other regime does not shift them.

But the two are frozen for opposite reasons, and one deletion each is enough to
show it. Take every single-cell deletion of both champions and culture it:

| | deletions that still replicate | that still go round again | best of them |
|---|---:|---:|---|
| `unrolled38`, 38 cells, 216 alone | **2 of 38** | 2 | 359 alone, **407** per birth — much worse |
| `short27r`, 27 cells, 180 alone | **7 of 27** | 5 | 172 alone — cheaper than its parent |

(The first version of this table said nine of twenty-seven. Nine is the figure
for `short27.sm`, the *other* 27-cell champion, and none of its nine repeat. The
verifier in `python3 -m soup verify` caught the mix-up on its first run, which
is the entire reason that file exists.)

The 38-cell creature sits on a genuine local optimum: almost nothing one
deletion away survives at all, the two that do are half as fast, and both lose
their head-to-head 214 to nothing. Its plateau is the ordinary kind — it is
there because there is nowhere better to go.

The 27-cell creature's plateau is the strange kind, and it is where Ray's
inference fails. A third of its deletions
work, five of them repeat, they are cheaper, most of them win a head-to-head
against it (finding 17), and the soup manufactures them continuously — and it
sits at 27 cells for ten billion instructions anyway. Whatever holds it there is
not the shape of the fitness landscape around it.

Two five-billion runs from `unrolled38` with flaws on now answer whether its
plateau is absolute or merely slow: after five billion instructions and thirty
thousand generations, mean genome length is **37.82 and 37.95 cells**. It is
absolute at every timescale this project can reach.

That is where this stands. The most likely remaining explanation for the 27-cell
plateau is the one none of these assays can reach: a variant in the real soup arrives as one
individual among nine hundred near-relatives that are producing variants of
their own, while every assay here hands it twelve clean copies and one clean
opponent. If that is right, the number this world converges on says more about
invasion under mutation pressure than about what a short program can do.

### 20. A second ancestor, and the one number that is the machine's rather than mine

Every finding above this one came from a single hand-written 64-cell program, and
the limitations section has said so from the beginning. `ancestor-b.sm` is a
second one, written from scratch and deliberately unlike the first: 53 cells, no
subroutine, three-bit templates instead of four, the division reached by a
forward jump out of the copy loop rather than by a `ret`, and the size carried in
`dx` as well as `cx`. Same capabilities, none of the same code. It worked on the
first attempt, which says more about the instruction set than about me.

It is also usefully **worse**. 495 instructions per daughter against the first
ancestor's 410, and 9.34 instructions per cell copied against 6.41 — which is
close to where Ray's 80-instruction ancestor started, and leaves the room for
optimization that my first ancestor never had.

Six runs of a billion instructions, three seeds with flaws off and three with:

| | genome length | best replicator | per cell | in a population |
|---|---:|---|---:|---:|
| `ancestor-b` as written | 53 | 495 | 9.34 | 814 |
| after 1B, no flaws | 45.5, 57.9, 46.6 | 42 cells at 317 | **7.48–7.55** | **397–414** |
| after 1B, flaws on | 54.6, 43.0, **24.9** | 24 cells at 157 | **6.54–6.59** | 1,482 |

**Finding 4 reproduces.** Descendants get cheaper by getting shorter, from a
starting program that shares no code with the one it was first seen in. So does
finding 13: the flawed runs compress much harder than the flawless ones, and the
seed that went furthest took a 53-cell ancestor to a population of 25-cell
creatures in a billion instructions — where the first ancestor's lineage needed
three billion to reach 27.

**And the plateau is not the world's, it is the lineage's.** The 27-cell
population that finding 19 could not shift is still at 27.1 cells after five
billion instructions and twenty-six thousand generations. A different ancestor
walks past it to 25 in one billion. Whatever holds the first lineage at 27, it is
not a floor of what this machine can express.

**The number that does look like the machine's:**

| | starts at | ends at |
|---|---:|---:|
| Ray's Tierra ancestor, 80 instructions | 10.5 | **6** |
| my first ancestor, 64 cells | 6.41 | 6.4 – 6.7 |
| `ancestor-b`, 53 cells | 9.34 | **6.54 – 7.55** |

Instructions executed per cell copied. Three independent starting points — two
of them mine and written years apart in intent, one of them Ray's on a different
instruction set — and all three end within a few tenths of six and a half. My
first ancestor was hand-written at 6.41 and has essentially never improved on it,
which for two weeks I read as a failure of the runs. It is not. **6.5 is where
this class of machine bottoms out**, and my first ancestor happened to be written
sitting on it. Only one lineage in this whole project has ever gone below —
the unrolled 38-cell champion at 5.68, by copying two cells per pass — and
finding 18 showed it loses on the measure that counts anyway.

**Three billion instructions later, the second ancestor's lineages come apart.**
The table above is a billion instructions. Four more runs took it to three,
which is where the first ancestor reached its plateau and sat:

| run | genome length | alive | generations | births | what the census contains |
|---|---:|---:|---:|---:|---|
| flaws, seed 4 | **29.0** | 906 | **13,944** | **8.4M** | 11 host-dependent, 1 inert, **no replicator** |
| flaws, seed 5 | 161.3 | 111 | 3,901 | 2.1M | 9 inert, 3 host-dependent; sizes to 845 |
| flaws, seed 6 | 420.2 | 69 | 864 | 0.29M | 12 inert, all 8–11 cells |
| no flaws, seed 7 | 128.5 | — | 2,826 | 1.0M | 9 replicators, every one a one-shot |

Two of the four have escaped into the allocator's ceiling — `mal` will not hand
out more than 1,024 cells, and creatures of 845 and 1,023 cells are sitting on
it while the population falls to seventy. The first ancestor never did this in
ten billion instructions. Whatever stability its lineages have, `ancestor-b`
does not share it, and finding 20's cheerful billion-instruction table has to be
read with that underneath it.

**And seed 4 is the strangest result in this project.** It is not degenerate at
all: 906 creatures, all but a handful exactly 29 cells, thirteen thousand
generations deep, 8.4 million births — deeper and more productive than anything
the first ancestor produced at the same clock. And **not one of its top twelve
genotypes can reproduce.** Cultured alone in a sterile dish they do not copy
themselves; cultured beside a copy of themselves they do not copy themselves
either. Two of them can *divide* — they release something — but never a copy of
themselves. I re-ran the assay at 500,000 instructions, twelve times what a
working 29-cell creature needs, in case the budget was the answer. It is not.

So the population is an obligate community. Every member depends on the presence
of genotypes other than its own kind, and the whole thing is more productive than
a soup of self-sufficient replicators. Findings 7, 8 and 11 found parasites and
hosts; this is a step past that, and it arrived from the ancestor that was
supposed to be the control.

**The suspect is me, again.** `ancestor-b` uses three-bit templates where the
first ancestor uses four. A three-bit pattern has eight possibilities against
sixteen, so a template search in a crowded soup is roughly twice as likely to
land on a neighbour's marker rather than its own — which is exactly the
machinery an obligate community would be built out of, and exactly the machinery
whose failure would produce runaway allocation. Every one of these results could
be a property of self-replicating programs, or a property of a decision I made
in twenty minutes while writing the file.

`experiments/ancestors/ancestor-c.sm` is the control: the same program,
instruction for instruction, with every template widened by one bit and one
extra `incC` for the longer END marker. 63 cells, 650 instructions alone, 807 in
a population, and it repeats. Three runs of three billion instructions from it,
at the same seeds and the same flaw rate, are on the compute server. If
`ancestor-c` stays healthy where `ancestor-b` fell apart, the instability was
mine; if it does not, three-bit templates are innocent and something more
interesting is going on.

Until those come back, the honest summary of this finding is narrower than it
was an hour ago: **the compression results reproduce from a second ancestor over
a billion instructions, and 6.5 instructions per cell copied looks like the
machine's floor from three independent starting points. Everything about
long-run stability is open.**

**One warning, and it is the same one as findings 17 and 18.** The champions
under 30 cells here are all one-shots: the 24-cell creature costs its population
1,482 instructions per birth, and the best genuine repeater `ancestor-b` produced
is the 42-cell one at 397. That is better than its own ancestor's 814 and much
worse than the first ancestor's best of 219. Shorter is still not automatically
better, and a table of solo costs still cannot tell you which is which.


## How this compares with what was already known

I built the machine before reading the literature, which is the wrong order.
[`docs/RELATED-WORK.md`](docs/RELATED-WORK.md) is the correction: an independent
read of Ray's Tierra paper, Standish on neutrality, the Avida results and a 2021
review of digital evolution, with a parameter-by-parameter calibration against
this soup. The short version:

* **Two findings here replicate Tierra directly.** Ray's parasite `0045aaa`
  arises from a size miscalculation that truncates the daughter before the copy
  procedure — the same mechanism, and by coincidence the same length, as my
  `0045adk`. And his decisive test is the one I arrived at independently: "not
  able to self-replicate in isolated culture".
* **One goes further than the primary source.** Ray reports immune hosts that
  eliminate parasites but gives no mechanism. Finding 8 gives one — the host no
  longer contains the pattern the parasite searches for — and it predicts what
  an immune Tierran host should look like: changed in the templates that *name*
  its copy procedure, not in the procedure itself.
* **One result is far weaker than his, and I know why.** Ray's creatures went
  from 80 instructions and 839 per daughter to 22 and 146 — a 5.75× gain. Mine
  went from 64 and 410 to 59–62 and 379–401, a few percent. Most of his gain
  came from evolving a copy loop that uses six instructions per cell instead of
  ten; **my hand-written loop already uses 6.4**, so the biggest prize in his
  world does not exist in mine. His runs were also 15 billion instructions
  against my 400 million.
* **My diversity numbers are not comparable to his.** Standish showed that
  ~100,000 Tierra genotypes collapse onto ~100 distinct *phenotypes*. I count
  exact genomes, so my "164–205 genotypes alive" is an upper bound on something
  he measured properly. Measuring it the right way is implemented and running.

## How the claims here were checked

Reading an evolved genome is a good way to convince yourself of something false,
so every claim came from a tool, and the tools are tested:

* `isolation_assay` — culture a genome alone in a sterile soup. Reproduction
  means an **exact copy**, not merely a successful `divide`: a damaged creature
  can ask for the smallest legal block, scribble in half of it and split it off
  in eighty instructions, and a classifier that counts divisions ranks that junk
  above every real replicator in the soup. Mine did, until it was fixed.
* `coculture_assay` / `interaction` — culture it beside a host and attribute
  every birth to the genome it produced, using the gene bank's records rather
  than by looking at who ends up lying next to whom.
* `susceptibility` — the same pairing left to run for a fixed budget, so the
  numbers are rates. Reported at genotype level for both parties, because
  comparing one seeded individual's births against a whole genotype's makes a
  host look six times less fertile than the parasite on it.
* `trace` / `trace_summary` — single-step execution with repeated loops folded
  into one line.
* `fidelity` — the fraction of a genotype's births that came from its own kind,
  which is how a real lineage is told apart from a shape that damaged mothers
  keep re-emitting. The eight-cell fragments in every census have hundreds of
  births and a fidelity of zero.
* `modal_parent` — ancestry by the route a genotype actually travels, not by
  whoever produced it first, which for a rare variant is often a freak event.

Two of the sweeps overlap by accident: `flaw-0-s1` and `mut-k1-s1` are the same
configuration reached from different directions, and they agree to the last
digit — 387 instructions, 59 cells, 62.9 mean length, 348 generations. Free
evidence that a run is reproducible from its parameters alone.

`python3 -m unittest discover -s tests` runs 64 tests covering instruction
semantics, the allocator, template search, write protection, the division rules,
determinism under a fixed seed, the reaper's ordering, the mutagen of finding 2,
the division-versus-reproduction distinction, and the receptor-loss immunity of
finding 8 built by hand. One of them exists because of the flaw-rate table:
reading a run's state off the clock of a longer run is only fair if measuring
the world does not disturb it, so a test samples the same world at two different
intervals and requires the shared snapshots and the final totals to be
identical.

## Limitations

* Two ancestors now, still one instruction set. Finding 20 reruns the
  compression results from `experiments/ancestors/ancestor-b.sm`, written from
  scratch and sharing no code with the first, and they reproduce. Everything
  *else* here — the parasites, the immunity, the error threshold, the
  interaction matrix — has still only ever been seen from one starting program.
* The longest finished runs are 10 billion instructions. Genome length stops
  falling long before that, but finding 17 shows the plateau is not a limit:
  shorter, cheaper, competitive variants exist one mutation away and keep being
  produced. Any statement here of the form "this world reaches N cells" is a
  statement about the search, not about what the world can hold.
* A genotype is exact genome identity, so one silent bit flip is a new species.
  Read the diversity numbers with that in mind.
* The interaction matrix tests one guest against one host. Real neighbourhoods
  have several, and the outcome depends on which template is nearest.
* Classification uses a fixed instruction budget; a very slow replicator would
  be filed as host-dependent or inert.
* Costs quoted as a single number are solo costs unless they say otherwise, and
  finding 18 shows those can be an order of magnitude optimistic. The population
  cost exists for the nine deep-run champions and for nothing else yet.
* The ecology half of finding 12 is not supported by its own data; see the
  paragraph that says so.
* Copy errors and cosmic rays were never varied independently until finding 16:
  every run before that has `copy_mutation_rate × cosmic_period = 2.000`.
  Wherever this document says a result is about the mutation rate — finding 12
  above all — it is about those two together. The cross that separates them says
  the sum is the right quantity, but only the twelve runs of finding 16 were
  designed to show it.
* Findings 7 and 8 rest on one seed's ecology — the seed that produced parasites
  at all. Two of three did not.
* Finding 11 is a null result at 20M instructions with one parasite genotype and
  one hand-built resistant host. It bounds nothing: a longer run, a different
  parasite, or resistance evolving in place rather than being transplanted
  could all show the sweep it failed to find.
* The community reconstruction in finding 11 seeds census genotypes in rough
  proportion; it does not reproduce the spatial arrangement the original soup
  had, and spacing demonstrably matters (the `--gap` result above).

## If you only read one other file

* [`docs/CORRECTIONS.md`](docs/CORRECTIONS.md) — everything here that turned out
  to be wrong, what was actually true, and how each was caught. Six entries; five
  of them were the measuring instrument rather than the world. It is the most
  portable thing in this repository.
* [`lab/AGENT-ANY.md`](lab/AGENT-ANY.md) — for anyone with their own machine who
  wants to check or extend this: start by disbelieving it, and here is what would
  actually help.
* [`docs/EXCHANGE.md`](docs/EXCHANGE.md) — where work like this can be published
  so that an agent or a person can find, cite and refute it, and what does not
  exist yet. [`docs/TO-DO-BY-HAND.md`](docs/TO-DO-BY-HAND.md) is the short list
  of steps that need the account owner rather than the agent.

## Layout

```
docs/MACHINE.md      the virtual CPU in full: state, templates, all 32 opcodes
docs/RELATED-WORK.md what the published work established, and how this compares
soup/isa.py          the 32 opcodes and what a template is
soup/asm.py          assembler and disassembler
soup/vm.py           soup memory, allocator, CPU, the interpreter
soup/world.py        scheduler, reaper queue, gene bank, mutation
soup/analysis.py     isolation and co-culture assays, tracing, classification
soup/experiment.py   running an experiment and recording it
soup/plot.py         ASCII charts, so results can live in a text file
soup/ancestor.sm     the seed organism
experiments/         the runs, their JSON histories, and the generated report
tests/               54 unit tests
```

## Reproducing

Every run is deterministic given its seed.

```bash
python3 -m soup run control-no-mutation --instructions 100000000 --seed 1 \
        --copy-mutation 0 --cosmic 0
python3 -m soup run baseline-s2 --instructions 100000000 --seed 2
python3 -m soup run matched-neutral-s1 --instructions 100000000 --seed 1 \
        --slice-size 0.3125 --slice-pow 1.0
python3 -m soup run long-constant-s1 --instructions 400000000 --seed 1 \
        --sample-every 4000000
python3 experiments/fragmentation.py
python3 experiments/viability.py
python3 experiments/epidemic.py
python3 experiments/mutation_rate.py
python3 experiments/neutrality.py
python3 experiments/flatness.py
python3 experiments/selection.py
python3 experiments/robustness_arc.py
python3 experiments/reclassify.py         # redo the assays after a classifier change
python3 experiments/report.py > experiments/REPORT.md

python3 -m soup interactions experiments/results/baseline-s2.json
python3 -m soup resistance   experiments/results/baseline-s2.json
python3 -m soup trace        experiments/results/baseline-s2.json 0045adk
python3 -m soup show         experiments/results/baseline-s2.json 0070aea --against ancestor
```
