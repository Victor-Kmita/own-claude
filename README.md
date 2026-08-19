# soup

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

## Quick start

```bash
python3 -m unittest discover -s tests     # 54 tests, no dependencies
python3 -m soup ancestor                  # the seed organism, disassembled
python3 -m soup run demo --instructions 20000000
python3 experiments/fragmentation.py      # the policy sweep in finding 2
python3 experiments/viability.py          # the mutational landscape in finding 9
python3 experiments/epidemic.py           # the resistance experiment in finding 11
python3 experiments/mutation_rate.py      # the sweep and error threshold, finding 12
python3 experiments/neutrality.py         # behaviours rather than genomes, finding 13
python3 experiments/flatness.py           # survival of the flattest, finding 6
python3 experiments/selection.py          # how strong selection is here
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

## What happened

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

This is the clearest open question the project leaves.

### 12. Mutation rate: an optimization peak, and an error threshold exactly where theory puts it

Ray reports two things about Tierra that pull against each other: optimization
is best "at the highest mutation rate that does not cause instability", while
ecology is richer at slightly lower rates. Quasispecies theory adds a third
expectation — above about one mutation per genome per replication a population
can no longer hold onto its information and melts.

Twenty-four runs, eight rates, three seeds each, 60M instructions apiece. Both
of this world's mutation rates are multiplied by the same factor *k*, so k=1 is
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

**The ecology claim I cannot support.** Averaged over seeds the parasite
indicator is highest at the lowest rates, which is the direction Ray describes.
But the within-condition spread is 0.12 to 0.85 at the same rate — as large as
the effect. Three seeds are not enough to say anything here, and I am not going
to pretend otherwise.

### 13. About a hundred distinct behaviours, however many genomes there are

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

### 14. Evolvability is expensive

The same 100M instructions bought 218,916 births with mutation off and
171,721 – 175,651 with it on: a fifth of the world's reproductive output goes on
variants that do not work. The noise that produced everything above is also the
reason the population is a fifth less productive.

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

`python3 -m unittest discover -s tests` runs 54 tests covering instruction
semantics, the allocator, template search, write protection, the division rules,
determinism under a fixed seed, the reaper's ordering, the mutagen of finding 2,
the division-versus-reproduction distinction, and the receptor-loss immunity of
finding 8 built by hand.

## Limitations

* One ancestor, one instruction set. Nothing here shows the results are general
  rather than particular to this 64-cell program.
* The longest runs are 400M instructions and the population is still churning at
  the end. Nothing has converged.
* A genotype is exact genome identity, so one silent bit flip is a new species.
  Read the diversity numbers with that in mind.
* The interaction matrix tests one guest against one host. Real neighbourhoods
  have several, and the outcome depends on which template is nearest.
* Classification uses a fixed instruction budget; a very slow replicator would
  be filed as host-dependent or inert.
* The ecology half of finding 12 is not supported by its own data; see the
  paragraph that says so.
* Findings 7 and 8 rest on one seed's ecology — the seed that produced parasites
  at all. Two of three did not.
* Finding 11 is a null result at 20M instructions with one parasite genotype and
  one hand-built resistant host. It bounds nothing: a longer run, a different
  parasite, or resistance evolving in place rather than being transplanted
  could all show the sweep it failed to find.

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
python3 experiments/reclassify.py         # redo the assays after a classifier change
python3 experiments/report.py > experiments/REPORT.md

python3 -m soup interactions experiments/results/baseline-s2.json
python3 -m soup resistance   experiments/results/baseline-s2.json
python3 -m soup trace        experiments/results/baseline-s2.json 0045adk
python3 -m soup show         experiments/results/baseline-s2.json 0070aea --against ancestor
```
