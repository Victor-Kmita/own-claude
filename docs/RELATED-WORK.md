# What was already known, and how this soup compares

I built this system first and read the literature afterwards, which is the wrong
order. This document is the correction: an independent read of the published
work on digital organisms, a parameter-by-parameter calibration of my world
against Tierra, and an honest accounting of which of my findings are
replications of known results, which are mechanistic explanations the primary
sources do not give, and which are contradicted.

Everything attributed below was read directly. The two PDFs were extracted with
a small text extractor written for the purpose (`pdftext.py` in the session
scratchpad), so quotations are paraphrased rather than reproduced verbatim where
the extraction lost word spacing.

## Sources

| what | where |
|---|---|
| Ray, *Evolution, Ecology and Optimization of Digital Organisms* — the primary Tierra paper, read in full | [PDF](https://faculty.cc.gatech.edu/~turk/bio_sim/articles/tierra_thomas_ray.pdf) |
| Tierra summary with the long-run result | [TalkOrigins archive](https://talkorigins.org/faqs/tierra.html) |
| Standish, *Tierra's missing neutrality: case solved* (2004) | [arXiv nlin/0404012](https://arxiv.org/pdf/nlin/0404012) |
| Wilke, Wang, Ofria, Lenski & Adami, *Evolution of digital organisms at high mutation rates leads to survival of the flattest*, Nature 412 (2001) | [Nature](https://www.nature.com/articles/35085569) |
| Lenski, Ofria, Pennock & Adami, *The evolutionary origin of complex features*, Nature 423 (2003) | [Nature](https://www.nature.com/articles/nature01568) |
| *Validating viral quasispecies with digital organisms: a re-examination of the critical mutation rate* (2005) | [BMC Ecol Evol](https://bmcecolevol.biomedcentral.com/articles/10.1186/1471-2148-5-5) |
| Dolson & Ofria, *Digital Evolution for Ecology Research: A Review* (2021) | [Frontiers](https://www.frontiersin.org/journals/ecology-and-evolution/articles/10.3389/fevo.2021.750779/full) |

## What Tierra established (Ray)

The parameters, from the paper:

* soup of about 60,000 instructions (300,000 bits);
* background "cosmic ray" mutation at about one bit flipped per 10,000
  instructions executed by the system;
* copy mutation at about one bit per 1,000–2,500 instructions moved;
* a third mutation mode, *flaws*: for most of the 32 instructions the result is
  off by ±1 at some low frequency;
* a slicer that may give each creature a slice proportional to genome size
  raised to a power — power 1 is size neutral, below 1 favours small creatures,
  above 1 favours large, and a constant slice selects for small;
* a reaper that kills from the top of a linear queue once memory fills to a
  specified level (e.g. 80%); errors move a creature one place up the queue,
  *provided the creature ahead has not accumulated more errors*, and two
  hard-to-execute instructions move it down on success under the mirror-image
  condition;
* an 80-instruction ancestor, of which 48 instructions are no-ops forming twelve
  four-cell templates.

The results:

* the ancestor executes **839 instructions in its first replication and 813 for
  each additional one** — 10.2 instructions per cell copied;
* a mutation in the low-order bit of instruction 42 makes a creature compute its
  size as 45, allocate 45 cells and copy only instructions 0–44, so the daughter
  lacks the copy procedure. That daughter, **0045aaa**, "is not able to
  self-replicate in isolated culture" but replicates in mixed culture with the
  ancestor by matching templates into the host's code. Parasites typically
  appear within the first few million instructions;
* some size-79 genotypes resist parasites. **0045aaa flanked on each side by
  0079aab is quickly eliminated; the same parasite beside the ancestor enters a
  stable cycle and both coexist indefinitely.** Runs dominated by size 79 see
  parasites appear repeatedly and fail to invade;
* immunity gets circumvented: **0051aao**, one step from 0045aaa with seven
  instructions inserted at position 39, coexists stably with the immune host,
  while fourteen sibling genotypes cannot;
* hyper-parasites appear (e.g. 0080gai, 19 instructions from the ancestor) whose
  copy procedure jumps back directly instead of returning, capturing the
  parasite's CPU;
* optimization: the smallest genome reached was **22 instructions replicating in
  146 instructions — 5.75× the ancestor's efficiency**, with other runs
  plateauing at 27 and 30. The gain is partly loop unrolling: 18 instructions to
  copy three cells, i.e. six per cell against the ancestor's ten. Different runs
  reach different plateaus, i.e. local optima;
* on mutation rate: "optimization of the algorithm is maximized at the highest
  mutation rate that does not cause instability", while "ecological interactions
  appear to be richer at slightly lower mutation rates";
* over a much longer run — fifteen billion instructions — a descendant of 36
  instructions appeared, whose copy loop uses 18 instructions per iteration to
  copy three cells.

## What Avida changed

Avida replaced the shared soup with a lattice in which each cell holds at most
one organism behind protected memory, and it pays CPU time for performing logic
tasks. The consequences are the ones the 2021 review draws out: parasitism is no
longer a free consequence of the architecture (it has to be implemented
deliberately), and there is an explicit, tunable fitness landscape. That
landscape is what made the 2003 *complex features* result possible — EQU evolves
when simpler logic functions on the way to it are also rewarded.

The review is also blunt about what Tierra-style systems do badly: the ecology
"tends to consist of only one type of parasite and one type of host at a time,
and the dynamics will often stagnate", and neither system achieves open-ended
evolution. It recommends disabling focal mechanisms to isolate them, reporting
runs deep enough in *generations* rather than in instructions, replicating
across substrates, and — pointedly for a project like this one — preferring
well-characterised platforms over novel custom implementations.

Standish's neutrality paper matters for how I count diversity. He generated
Tierra datasets of 69,139, 87,003 and 198,982 genotypes over about a billion
instructions and found they collapsed onto **83, 86 and 158 unique phenotypes**.
Neutral variants were rarer than expected, and his explanation is ecological:
parasites need a host within range, so a neutral variant that lands somewhere
without one fails to replicate, and neutrality is suppressed by host–parasite
competition.

## Calibration

| | Tierra (Ray) | this soup |
|---|---|---|
| soup size | ~60,000 instructions | 60,000 cells (same) |
| instruction set | 32, saturated | 32, saturated |
| addressing | complementary nop templates | same |
| protection | write-protected, read/execute open | same |
| mutation: cosmic | 1 bit per 10,000 instructions executed | 1 bit per 2,000 — **5× higher** |
| mutation: copy | 1 bit per 1,000–2,500 cells copied | 1 bit per 1,000 — top of Ray's range |
| mutation: flaws | yes, results off by ±1 | **absent** |
| slicer | slice ∝ size^power; power 1 = size neutral | same knob (`--slice-pow`), same semantics |
| reaper | linear queue, errors move up subject to an error-count guard | linear queue, errors move up unconditionally, division moves down |
| reaper trigger | memory fills to ~80% | 80%, **and on allocation failure** |
| ancestor | 80 instructions, 48 of them no-ops (60%) | 64 instructions, 36 no-ops (56%) |
| ancestor cost | 839 first replication, 813 thereafter (10.2 per cell) | **410 first, 407 thereafter (6.36 per cell)** |
| typical run length | 1–15 billion instructions | 100M–400M so far; 3B running |

The single most consequential row is the ancestor's cost. **My hand-written copy
loop already runs at 6.4 instructions per cell copied — the efficiency Ray's
creatures reached only after evolving loop unrolling.** His ancestor started at
10.2 and evolution found a 1.6× saving there before it touched genome length. In
my world that saving is not on the table, which is a large part of why my
descendants improve by 2–7% where his improved by 475%.

## Which of my findings are replications

**Parasites by loss of the copy procedure.** Ray's 0045aaa arises from a size
miscalculation that truncates the daughter before the copy procedure; my
`0045adk` arises the same way and is the same length by coincidence. Confirmed
independently in both systems, and in mine the additional requirement is
identified: the parasite must also lose its *own* copy of the `1100` marker, or
its call finds its own dead code and it becomes a donor rather than a parasite.

**Isolated versus mixed culture as the decisive test.** Ray's phrasing — "not
able to self-replicate in isolated culture" — is exactly the assay I arrived at
independently before reading him. Convergence on method is weak evidence that
the method is the right one, but it is evidence.

**Immunity, and its cost.** Ray reports resistant size-79 hosts that eliminate a
parasite flanking them on both sides; I find a resistant 70-cell replicator that
nine parasites cannot exploit. His paper reports the phenomenon without a
mechanism. Mine gives one — the host no longer contains the four-cell pattern
the parasite searches for — and that mechanism makes a prediction Tierra could
be checked against: an immune Tierran host should differ from a susceptible one
in the templates that name its copy procedure, not in its copy procedure itself.

**Slicer power controls genome length.** Ray states the design intent (constant
slice selects for small creatures; power 1 is size neutral). My ten runs measure
it: 57–62 cells under a constant slice, 77–106 under a proportional one, no
overlap. As far as I can tell from the paper, Ray asserts the direction rather
than measuring it.

**Ecology is richer at lower mutation rates.** My sweep reproduces the direction
of Ray's claim (see below), though with an important caveat about seed variance.

## Where my results differ

**Optimization is far weaker.** Ray: 80 → 22 instructions, 839 → 146
instructions per daughter. Mine: 64 → 59–62, 410 → 379–401. Three reasons, in
order of likely importance: my ancestor's copy loop is already at his optimized
efficiency, so the biggest prize is gone before the run starts; my longest runs
are 400M instructions against his 15 billion, i.e. **37× shorter**; and my
mutation model has no instruction flaws, so one of his three mutation modes is
missing entirely. The 3-billion-instruction runs now going are the first direct
test of the length explanation.

**Ecological stagnation is absent, or the metric is wrong.** The review says
Tierra tends toward one host and one parasite at a time. My runs hold 164–219
distinct genotypes at once with Shannon diversity near 7 bits. But Standish's
result is the caution: in Tierra, ~100,000 genotypes collapsed onto ~100
phenotypes. My genotype counts are exact genome identity and are therefore not
comparable to a phenotype count at all. Measuring the collapse in my own system
is now implemented (`phenotype_signature`) and is the next thing to run.

**Transplanted parasites die.** Ray reports 0045aaa and the ancestor entering a
stable cycle and coexisting indefinitely; my transplanted parasite goes extinct
in an all-susceptible soup. His flanked arrangement is now implemented as an
assay option (`coculture_assay(..., flank=True)`), since a guest with hosts on
both sides is in a different world from one with a host on one side and empty
medium on the other — a template search runs outward in both directions.

## What the reading produced

### Ray's mutation-rate claims, tested

Twenty-four runs, eight rates, three seeds each. Both mutation rates scale
together by a factor *k*; µ is mutations per 64-cell genome per replication.

| k | µ | generations | cheapest replicator | breeders on foreign code |
|---:|---:|---:|---|---:|
| 0.25 | 0.016 | 367 | 387, 399, 406 | 53% |
| 1 | 0.064 | 347 | 387, 407, 402 | 11% |
| 8 | 0.512 | 243 | **379, 365, 346** | 35% |
| 16 | 1.016 | **10** | none | 100% |
| 32 | 2.065 | **4** | none | 100% |

**Ray's optimization claim holds.** All three seeds at k=8 — the highest rate
that does not destabilise — produced the cheapest replicators in the whole
sweep, the best at 346 instructions against the ancestor's 410.

**The error threshold sits exactly at one mutation per genome per
replication**, between µ = 0.51 and µ = 1.02. At k=16 the census contains no
self-sufficient replicator, every fidelity is zero, generation depth falls from
~250 to 10, and 132 distinct genotypes are alive among 133 creatures — nothing
copies itself accurately enough to found a lineage. This is the classic
quasispecies result, reproduced without being aimed at.

**Ray's ecology claim I cannot test with three seeds.** The direction is right —
the parasite indicator is highest at the lowest rates — but the within-condition
spread (0.12 to 0.85 at the same rate) is as large as the effect.

### How optimization happens here, and why it is smaller

The cheapest replicator found, `0053abg` at 346 instructions, keeps the
ancestor's copy loop exactly: six instructions per cell copied, 6.53 against the
ancestor's 6.41. It is cheaper solely because it is shorter — 53 cells against
64. Tierra's optimized creatures won on both counts, unrolling the loop from ten
instructions per cell to six *and* shrinking the genome. Half of that prize does
not exist in my world, because my hand-written loop starts at six.

Unrolling would still pay here — copying two cells per iteration would cost five
instructions per cell rather than six — and nothing has found it in 60M
instructions.

### Standish's neutrality result, half reproduced

Standish counted phenotypes rather than genotypes and found Tierra gene banks of
69k–199k genotypes collapsing onto 83, 86 and 158 behaviours.  Measuring the
same thing here — a phenotype being what a genome does alone and beside two
reference organisms, with the total estimated from a sample of seventy by the
Chao1 estimator — gives 22 to 121 behaviours in banks of 282 to 4,423 genotypes.

**The order of magnitude agrees**: both systems support something like a hundred
distinguishable behaviours regardless of how many genomes pass through.  That is
the most direct quantitative agreement between this soup and Tierra that I have
found, and it was not aimed at.

**His explanation does not reproduce.**  Parasites needing a host in range should
suppress neutrality, so a parasite-rich world should show fewer genotypes per
phenotype.  Two runs at the same mutation rate differing only in seed, at 10%
and 67% parasitism, give 2.9 and 3.0 genotypes per phenotype — no effect — and
the parasite-rich one holds three times as many distinct behaviours.  One seed
pair and a phenotype definition of my own making: a failure to reproduce rather
than a refutation.

### Run length was the other missing factor, and the prediction paid off

Ray's descendants needed billions of instructions.  At 400M my genomes sat at
57–62 cells and not one of 33 runs had improved the copy loop.  The calibration
said the runs were simply too short, so I ran three billion.

The champion of that run, `0038rdr`, is **38 cells replicating in 216
instructions** against the ancestor's 64 and 410 — 1.9× the efficiency, held by
134 of about 640 creatures at fidelity 0.99, after roughly 18,000 generations.
And this time it is not compression alone: its copy loop copies **two cells per
iteration in ten instructions**, five per cell where the ancestor needs six.
That is loop unrolling, the same innovation Ray reports, found here once the run
was long enough and not before.

It also moved its division to the top of the genome, so the `ret` at the end of
the copy loop lands on the first cell and the next replication begins
immediately; the first pass through those cells throws a harmless error.

| | ancestor | this soup at 3B | Tierra at 15B |
|---|---|---|---|
| genome | 64 cells | 38 | 22 |
| instructions per daughter | 410 | 216 | 146 |
| per cell copied | 6.41 | 5.68 | 6 (from 10) |
| efficiency gain | — | 1.9× | 5.75× |

### Survival of the flattest, unlooked for

Wilke et al. (2001) showed in Avida that at high mutation rates selection favours
the genotype with the flattest neighbourhood rather than the fastest replicator.
I did not set out to test this; it turned up while asking whether the unrolled
replicator from the 3-billion-instruction run actually beats its compressed
sibling.

It does not.  From one cosmic ray per five million instructions down to one per
two hundred thousand, the slower and flatter lineage wins, and at the bottom of
that window the faster one goes extinct in every seed tried.  Measuring the two
neighbourhoods directly says why: both tolerate mutation about equally often
(32% and 31% of single-bit mutants still replicate), but the flat replicator's
surviving mutants cost what it costs -- 239 instructions -- while the unrolled
one's average 5,109.  Twenty-one times worse, for a genotype that is only 10%
cheaper to begin with.

Two methodological notes came out of it.  Counting exact genotypes rather than
lineages gave the opposite answer at low noise, because with any mutation the
seeded genotypes disappear into their own descendants within a few million
instructions.  And with mutation entirely off, this world is deterministic and
finite, so a two-genotype competition falls into a periodic orbit and sits there
-- which looks exactly like stable coexistence and is not.

Below the window the comparison degenerates rather than reversing cleanly: the
faster lineage becomes numerous again while its members' cost per cell rises
from 5.68 to 95, so they are descendants in name only.  I have no established
explanation for that tail.

### Robustness is under selection, and compression spends it

Measuring the mutational neighbourhood of the best replicator from runs of
increasing length gives a second, independent line of evidence for the same
thing.  The fraction of single-bit mutants that still replicate at within 10% of
the parent's cost rises from 31% for the hand-written ancestor to 40% after a
hundred million instructions, and reaches 45% in the run at eight times the
standard mutation rate -- the condition under which quasispecies theory says
flatness should be selected hardest.

The two three-billion-instruction champions, compressed to 37 and 38 cells, fall
back to 32% and 23%.  Compression removes the slack that made mutations
survivable, which is a trade-off Ray's paper does not discuss and which may bear
on why his runs plateaued at 22 to 30 instructions rather than going further.

### How strong is selection here at all

A companion measurement, since the flatness result depends on knowing what a 10%
advantage is worth.  The ancestor against a series of its own descendants of
known cost, forty million instructions each:

| advantage in instructions per daughter | outcome |
|---|---|
| 47%, 11%, 8.5% | the challenger sweeps to 100% |
| 7.1%, 4.9%, 3.7% | the challenger takes 87–96% |
| 2.2%, 1.2%, 0.2% | 50/50, no resolution |

Selection here resolves differences above about 4% within forty million
instructions and is blind to anything under 2%.  Running the three near-neutral
contests for ten times as long -- four hundred million instructions each --
leaves them at 51%, 51% and 50%: the advantage is not too small to act *yet*, it
is too small to act at all on this timescale.  That is the tempo everything else
in this repository runs at.

## Agenda

| experiment | why | status |
|---|---|---|
| runs of billions of instructions | Ray's optimization result needed 15B | 2 × 3B, in progress; already down to 42 cells at 1B |
| mutation-rate sweep with replicates | tests both of Ray's claims, locates the error threshold | done, 24 runs |
| phenotype signatures, not genotype counts | Standish: ~100k genotypes → ~100 phenotypes | done; order of magnitude agrees, his mechanism does not reproduce |
| report generation depth | the review's criterion for a credible experiment | now recorded in every sample |
| flanked co-culture | Ray demonstrated immunity with hosts on both sides | implemented |
| instruction flaws as a third mutation mode | Tierra has it, I do not | not started |
| hyper-parasites | Ray found them; I have not looked | not started |
| loop unrolling | the one optimization Tierra found that mine has not | found at 3B -- and then found to be selected against under noise |
| survival of the flattest | Wilke et al. 2001 | reproduced, with the neighbourhood measured directly |
| strength of selection | needed to interpret any competition result | measured: blind below 2%, decisive above 8% |

## Checked against the primary sources, August 2026

Three claims in this document and in the README rested on my reading of
secondary descriptions. I went back to the sources. Two came out better than I
expected and one came out worse.

### Ray reported my finding 19 in 1991, and I can now test what he assumed

Finding 19 says genome length here does not descend, it freezes: a run reaches a
length and sits at it for billions of instructions. Ray's own words, from
*Evolution, Ecology and Optimization of Digital Organisms*, section 3.1:

> Also, each run decreases to a size limit which it cannot proceed past even if
> it is allowed to run much longer. However, different runs reach different
> plateaus of efficiency. The smallest limiting genome size seen has been 22
> instructions, while other runs reached limits of 27 and 30 instructions.
> Evidently, the system can reach a local optima from which it cannot easily
> evolve to the global optima.

That is the same phenomenon, described thirty-five years earlier, down to the
spread of endpoints across seeds. So finding 19 is a replication, not a
discovery, and the README now says so.

What is new is the last sentence. Ray inferred *local optima* from the fact that
the runs stop. That inference is testable and I tested it: enumerate every
single-cell deletion of the champion and culture each one. For the 38-cell
plateau he is right — two of thirty-eight deletions survive, both are half as
fast, and both lose their head-to-head 214 to nothing. For the 27-cell plateau
he is wrong: nine of twenty-seven deletions replicate, five of them repeat, they
are cheaper, most of them beat the champion in a dish, and the soup manufactures
them every few thousand births. **A plateau in this kind of system is not
evidence of a local optimum, and the two cases are distinguishable with an
afternoon of assays.**

### Ray's cost numbers already had the column I spent a day adding

Finding 18 is that a cost measured with one creature alone is not what a daughter
costs a population, and that the tell is whether the creature makes a *second*
daughter. Ray's genotype records carry exactly that, and always did. From the
listing of his ancestor:

```
1st_daughter: flags:0 inst:839 mov_daught:80
2nd_daughter: flags:0 inst:813 mov_daught:80
```

and of his smallest creature:

```
genotype: 0022abn   parent genotype: 0022aak
1st_daughter: flags:1 inst:146 mov_daught:22 breed_true:1
2nd_daughter: flags:0 inst:142 mov_daught:22 breed_true:1
```

Two daughters, both costed, plus `breed_true` — which is my `fidelity` under
another name. His 22-instruction creature spends 146 instructions on its first
daughter and 142 on its second, so it is a genuine repeater and the 5.75-fold
optimization he reports is real by the standard I only started applying
yesterday. My `describe()` reported one daughter and called it the cost, which
is how a one-shot ended up as `short27.sm`. The 1991 paper had the column I was
missing.

**So the comparison of numbers is fair after all, and it is this:**

| | genome | instructions per daughter | per instruction copied |
|---|---:|---:|---:|
| Ray's ancestor | 80 | 839 | 10 |
| Ray's best | 22 | 146 | 6 |
| my ancestor | 64 | 410 | 6.4 |
| my best (seed 5, 27 cells) | 27 | 180 alone, 219 in a population | 6.7 |

His ancestor starts at ten instructions executed per instruction copied and
evolution takes it to six. Mine was hand-written at 6.4 and has not got below
6.4 except in the one run that unrolled its loop, which reached 5.68 and stayed
long. This is the sentence the README has carried from the beginning — "mine
starts where his finished" — and it is now checked rather than inferred.

### The two smallest creatures ever produced by the two systems are the same program

This one I did not expect. Ray's 22-instruction creature, from his Appendix D,
against my 27-cell one, from `experiments/ancestors/short27.sm`:

| | Tierra, 22 instructions | this world, 27 cells |
|---|---|---|
| leading template | `nop_0` | `.t 1` |
| find own start | `adrb` | `adrb` |
| a `divide` that errors on the first pass | `divide` — *"fails the first time it is executed"* | `divide` — with no daughter yet, an error |
| find own end | `adrf` | `adrf` |
| compute length | `sub_ac`, `sub_ab` | `subCAB` |
| allocate | `mal` | `mal` |
| save the return address on the stack | `push_bx` | `pushB` |
| copy loop | `mov_iab`, `dec_c`, `if_cz`, `inc_a`, `inc_b`, `jmpb` | `movii`, `decC`, `ifz`, `incA`, `incB`, `jmpb` |
| instructions executed per loop | **6** | **6** |
| how the loop exits | `ret` to the pushed address — a computed jump with no matching `call` | `ret` in seeds 5 and 10; seed 6 falls into `divide` and wraps |

Different instruction sets, different ancestors, different authors, thirty-five
years apart, and the same twenty-odd instruction architecture — including two
tricks I would have called quirks of my own soup if I had not gone and looked.
The dead `divide` at the top, which wastes an error on every first pass and is
kept anyway because it saves the cells a proper guard would cost. And `ret` used
as an indirect jump to an address pushed by hand, with no `call` anywhere in the
genome, which is the same idea as reusing the stack as a register.

I take this as the strongest evidence in this project that the results here are
about self-replicating programs under selection and not about my particular
sixty-four-cell ancestor.

### Lethal mutagenesis is a real distinction, and finding 16 is only half of it

Finding 16 says flaws kill the daughter while copy errors edit her, and that only
edits count toward the threshold. I suspected this mapped onto a known
distinction, and it does — but not as neatly as I hoped. Bull, Sanjuán and Wilke,
*Theory of Lethal Mutagenesis for Viruses* (J. Virol. 2007), separate the two:

> an error catastrophe is an evolutionary shift in genotype space, whereas
> extinction is a demographic process, a drop in the absolute abundance of
> individuals

with extinction when `e^(−Ud) × R_max < 1` — each genotype leaves fewer than one
successful descendant on average. Their lethal mutations *do* count, toward
extinction.

So the mapping is this, and it is a statement about my world's construction
rather than about mutation. **This soup cannot show lethal mutagenesis.**
Population size is set by memory and the reaper, not by fecundity: a daughter
that dies frees the block her successor needs, so killing offspring costs
throughput and not abundance. `R_max` is effectively unbounded here. What is
left is the other process — the evolutionary shift in genotype space — and that
one is driven by the viable mutants only, which is what the flaws-versus-copy
result measures. The observed collapse has the right signature for it too:
genomes bloating from 27 to 157 cells while the census fills with debris.

The 2007 paper also notes that an error catastrophe "can delay or even prevent
extinction by shifting the population to genotypes that are robust to mutation",
which is finding 6 here (survival of the flattest) arriving from the other
direction.

## Caveats about this document

I read one primary source in full (Ray), one methodological paper in full
(Standish), a review, and abstracts or summaries of the rest; the section above
went back to Ray's text and to Bull, Sanjuán and Wilke directly and quotes them,
so the four claims in it are the best-supported in this document. the Nature papers
are paywalled and I worked from their abstracts and from secondary descriptions.
Where a number appears above it came from the source named beside it, and where
I could not extract a number I have said so rather than filling it in from
memory. The comparison table is only as good as my reading of Ray's parameter
descriptions, which are prose rather than a table in the original.
