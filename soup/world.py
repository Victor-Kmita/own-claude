"""The world: scheduling, death, mutation, and the record of who lived.

Three pressures act on a creature and nothing else does:

* **Time** -- the scheduler hands every living creature a slice of CPU.  How
  long that slice is (constant, or proportional to genome length) decides
  whether being short is an advantage.  It is the single most consequential
  knob in the whole simulation.
* **Space** -- the soup is finite.  When it fills past a threshold the reaper
  kills from the head of a queue that creatures climb by making errors and
  descend by successfully reproducing.  Nothing here selects for "fitness"
  directly; a creature that reproduces faster than it is reaped simply persists.
* **Noise** -- cosmic rays flip bits anywhere in the soup, and the copy
  instruction occasionally miscopies.  Without noise the population is a
  monoculture forever; with it, everything below happens on its own.
"""

from __future__ import annotations

import random
from collections import Counter

from .vm import Creature, Memory, run_slice
from .isa import INSTRUCTIONS


class ReaperQueue:
    """Death order.  Head dies first.

    A creature enters at the tail (newborns are safest), climbs one place toward
    the head every time it makes an error, and drops one place toward the tail
    each time it successfully divides.  Age therefore matters, but competence
    matters more -- exactly the property that lets a better replicator displace
    an older, sloppier one without any explicit fitness function.
    """

    def __init__(self):
        self.order: list[Creature] = []
        self.pos: dict[int, int] = {}

    def __len__(self) -> int:
        return len(self.order)

    def append(self, cr: Creature) -> None:
        self.pos[cr.cid] = len(self.order)
        self.order.append(cr)

    def _swap(self, i: int, j: int) -> None:
        a, b = self.order[i], self.order[j]
        self.order[i], self.order[j] = b, a
        self.pos[a.cid], self.pos[b.cid] = j, i

    def move_toward_head(self, cr: Creature) -> None:
        i = self.pos.get(cr.cid)
        if i is not None and i > 0:
            self._swap(i, i - 1)

    def move_toward_tail(self, cr: Creature) -> None:
        i = self.pos.get(cr.cid)
        if i is not None and i < len(self.order) - 1:
            self._swap(i, i + 1)

    def remove(self, cr: Creature) -> None:
        i = self.pos.pop(cr.cid, None)
        if i is None:
            return
        last = self.order.pop()
        if last.cid != cr.cid:
            self.order[i] = last
            self.pos[last.cid] = i

    def head(self) -> Creature | None:
        return self.order[0] if self.order else None


class GeneBank:
    """Names genomes.  A genotype is an exact sequence of instructions.

    Labels look like ``0062aaa``: length, then a letter code assigned in order of
    first appearance among genomes of that length.  This is Tierra's convention
    and it is a good one -- length is the fact you most want to see at a glance,
    because length is what selection visibly moves.
    """

    def __init__(self):
        self.by_key: dict[tuple[int, bytes], str] = {}
        self.genome: dict[str, bytes] = {}
        self.counters: dict[int, int] = {}
        self.births = Counter()
        self.parent_births: Counter = Counter()   # (child, mother) -> count
        self.first_seen: dict[str, int] = {}
        self.origin: dict[str, str | None] = {}

    @staticmethod
    def _letters(n: int) -> str:
        s = ""
        for _ in range(3):
            s = chr(ord("a") + n % 26) + s
            n //= 26
        return s

    def name(self, genome: bytes, tick: int, parent: str | None) -> str:
        key = (len(genome), genome)
        label = self.by_key.get(key)
        if label is None:
            n = self.counters.get(len(genome), 0)
            self.counters[len(genome)] = n + 1
            label = f"{len(genome):04d}{self._letters(n)}"
            self.by_key[key] = label
            self.genome[label] = genome
            self.first_seen[label] = tick
            self.origin[label] = parent
        self.births[label] += 1
        self.parent_births[(label, parent)] += 1
        return label

    def fidelity(self, label: str) -> float:
        """Fraction of this genotype's births that came from its own kind.

        A genotype can be numerous for two very different reasons: it is a
        lineage that breeds true, or it is a shape that damaged mothers of other
        genotypes keep producing by accident (truncated fragments, mostly).
        Fidelity separates the two.  Near 1.0 means a real lineage; near 0.0
        means a recurring accident that never reproduces itself.
        """
        total = self.births[label]
        if not total:
            return 0.0
        return self.parent_births[(label, label)] / total


class World:
    def __init__(
        self,
        soup_size: int = 60000,
        seed: int = 1,
        slice_size: float = 20,
        slice_pow: float = 0.0,
        copy_mutation_rate: float = 1 / 1500,
        cosmic_period: int = 3000,
        reap_threshold: float = 0.80,
        search_limit: int = 1024,
        min_daughter_size: int = 8,
        max_daughter_size: int = 1024,
        mutate_only_live: bool = False,
        filler: int = 0,
    ):
        self.soup_size = soup_size
        self.filler = filler
        self.soup = bytearray([filler]) * soup_size
        self.memory = Memory(soup_size)
        self.rng = random.Random(seed)
        self.slice_size = slice_size
        self.slice_pow = slice_pow
        self.copy_mutation_rate = copy_mutation_rate
        self.cosmic_period = cosmic_period
        self.reap_threshold = reap_threshold
        self.search_limit = search_limit
        self.min_daughter_size = min_daughter_size
        self.max_daughter_size = max_daughter_size
        self.mutate_only_live = mutate_only_live

        self.creatures: list[Creature] = []
        self.reaper = ReaperQueue()
        self.genebank = GeneBank()
        self.next_cid = 0
        self.clock = 0                 # instructions executed, world-wide
        self.next_ray = cosmic_period
        self.deaths = 0
        self.births = 0
        self.alloc_failures = 0
        self.history: list[dict] = []
        self.extinct = False
        self._pending_births: list[Creature] = []

    # -- genome helpers ----------------------------------------------------
    def read_genome(self, start: int, size: int) -> bytes:
        end = start + size
        if end <= self.soup_size:
            return bytes(self.soup[start:end])
        return bytes(self.soup[start:]) + bytes(self.soup[: end - self.soup_size])

    def write_genome(self, start: int, code) -> None:
        for i, op in enumerate(code):
            self.soup[(start + i) % self.soup_size] = op

    # -- population --------------------------------------------------------
    def inject(self, code, address: int | None = None) -> Creature:
        """Place a genome in the soup as a living creature."""
        size = len(code)
        addr = self.memory.allocate(size) if address is None else address
        if addr is None:
            raise RuntimeError("no room in the soup for the ancestor")
        if address is not None:
            self.memory.blocks.append((addr, size))
            self.memory.blocks.sort()
            self.memory.used += size
        self.write_genome(addr, code)
        label = self.genebank.name(bytes(code), self.clock, None)
        cr = Creature(self.next_cid, addr, size, genotype=label,
                      born_tick=self.clock, generation=0)
        self.next_cid += 1
        self.creatures.append(cr)
        self.reaper.append(cr)
        return cr

    def birth(self, mother: Creature) -> None:
        """Called by ``divide``: the daughter block becomes its own creature."""
        dstart, dsize = mother.daughter
        mother.daughter = None
        mother.daughter_writes = 0
        genome = self.read_genome(dstart, dsize)
        label = self.genebank.name(genome, self.clock, mother.genotype)
        child = Creature(self.next_cid, dstart, dsize, genotype=label,
                         mother=mother.cid, born_tick=self.clock,
                         generation=mother.generation + 1)
        self.next_cid += 1
        self.births += 1
        self._pending_births.append(child)
        self.reaper.move_toward_tail(mother)

    def kill(self, cr: Creature) -> None:
        if not cr.alive:
            return
        cr.alive = False
        self.memory.free(cr.start, cr.size)
        if cr.daughter is not None:
            self.memory.free(*cr.daughter)
            cr.daughter = None
        self.reaper.remove(cr)
        self.deaths += 1

    def reap(self) -> None:
        while self.memory.load > self.reap_threshold and len(self.reaper) > 1:
            victim = self.reaper.head()
            if victim is None:
                break
            self.kill(victim)

    # -- mutation ----------------------------------------------------------
    def cosmic_ray(self) -> None:
        if self.mutate_only_live and self.memory.blocks:
            start, size = self.memory.blocks[self.rng.randrange(len(self.memory.blocks))]
            addr = (start + self.rng.randrange(size)) % self.soup_size
        else:
            addr = self.rng.randrange(self.soup_size)
        self.soup[addr] ^= 1 << self.rng.randrange(5)

    # -- main loop ---------------------------------------------------------
    def slice_for(self, cr: Creature) -> int:
        if self.slice_pow == 0.0:
            return self.slice_size
        return max(1, int(self.slice_size * (cr.size ** self.slice_pow)))

    def step_generation(self) -> None:
        """One pass over every living creature."""
        self.reap()
        living = [c for c in self.creatures if c.alive]
        self.creatures = living
        if not living:
            self.extinct = True
            return
        for cr in living:
            if not cr.alive:
                continue
            before_errors = cr.stats.errors
            n = run_slice(self, cr, self.slice_for(cr))
            self.clock += n
            if cr.stats.errors > before_errors:
                self.reaper.move_toward_head(cr)
            if self.clock >= self.next_ray:
                self.cosmic_ray()
                self.next_ray = self.clock + self.cosmic_period
        if self._pending_births:
            for child in self._pending_births:
                self.creatures.append(child)
                self.reaper.append(child)
            self._pending_births.clear()

    def population(self) -> Counter:
        c = Counter()
        for cr in self.creatures:
            if cr.alive:
                c[cr.genotype] += 1
        return c

    def alive_count(self) -> int:
        return sum(1 for c in self.creatures if c.alive)
