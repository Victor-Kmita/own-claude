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

    It is a doubly linked list rather than a list of creatures, because every
    operation the reaper needs is a splice: remove from the middle when
    something dies, swap with a neighbour on an error or a division, pop the
    head when the soup is full.  An array-backed version that filled the hole by
    moving the last element would take the *youngest* creature in the world and
    put it at the front of the death queue every time anything died, which is
    not a small distortion of who gets to live.
    """

    __slots__ = ("head_node", "tail_node", "nodes")

    def __init__(self):
        self.head_node = None          # [creature, prev, next]
        self.tail_node = None
        self.nodes: dict[int, list] = {}

    def __len__(self) -> int:
        return len(self.nodes)

    def append(self, cr: Creature) -> None:
        node = [cr, self.tail_node, None]
        if self.tail_node is None:
            self.head_node = node
        else:
            self.tail_node[2] = node
        self.tail_node = node
        self.nodes[cr.cid] = node

    def _unlink(self, node) -> None:
        prev, nxt = node[1], node[2]
        if prev is None:
            self.head_node = nxt
        else:
            prev[2] = nxt
        if nxt is None:
            self.tail_node = prev
        else:
            nxt[1] = prev

    def _link_after(self, node, prev) -> None:
        nxt = prev[2] if prev is not None else self.head_node
        node[1], node[2] = prev, nxt
        if prev is None:
            self.head_node = node
        else:
            prev[2] = node
        if nxt is None:
            self.tail_node = node
        else:
            nxt[1] = node

    def move_toward_head(self, cr: Creature) -> None:
        node = self.nodes.get(cr.cid)
        if node is None or node[1] is None:
            return
        before = node[1][1]
        self._unlink(node)
        self._link_after(node, before)

    def move_toward_tail(self, cr: Creature) -> None:
        node = self.nodes.get(cr.cid)
        if node is None or node[2] is None:
            return
        after = node[2]
        self._unlink(node)
        self._link_after(node, after)

    def remove(self, cr: Creature) -> None:
        node = self.nodes.pop(cr.cid, None)
        if node is not None:
            self._unlink(node)

    def head(self) -> Creature | None:
        return self.head_node[0] if self.head_node else None

    def next_after(self, cr: Creature) -> Creature | None:
        node = self.nodes.get(cr.cid)
        if node is None or node[2] is None:
            return None
        return node[2][0]

    def order_cids(self) -> list[int]:
        """Front-to-back order; for tests and debugging."""
        out = []
        node = self.head_node
        while node is not None:
            out.append(node[0].cid)
            node = node[2]
        return out


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

    def modal_parent(self, label: str) -> str | None:
        """The genotype that most often gives birth to this one.

        ``origin`` records who produced a genotype the very first time, which
        for a rare variant can be a freak event -- an eight-cell fragment that
        wandered into a neighbour's body once and came out with a daughter.  The
        modal parent is the route that actually carries the genotype, and it is
        what an ancestry chain should be built from.
        """
        best, best_n = None, 0
        for (child, parent), n in self.parent_births.items():
            if child == label and parent != label and parent is not None and n > best_n:
                best, best_n = parent, n
        return best

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
        reap_on_alloc_failure: bool = True,
        errors_hasten_death: bool = True,
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
        # Whether a creature that cannot allocate triggers the reaper.  With it
        # off, the soup sits permanently full and ``mal`` fails routinely --
        # which turns out to be a mutation source in its own right.  See
        # experiments/fragmentation.py.
        self.reap_on_alloc_failure = reap_on_alloc_failure
        # Whether making an error moves a creature one place toward the reaper.
        # This is the only thing in the world that resembles quality control,
        # and switching it off is the cleanest way to ask what it is doing.
        self.errors_hasten_death = errors_hasten_death

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

    def make_room(self, size: int, requester: Creature | None = None,
                  max_kills: int = 8) -> int | None:
        """Kill from the head of the reaper queue until an allocation fits.

        Reaping once per scheduler pass is not enough on its own: every creature
        holding a daughter block occupies twice its own length, so a soup at the
        threshold before a pass is comfortably over it by the end.  The moment a
        creature cannot allocate is exactly the moment the reaper exists for, so
        that is when it runs.

        The kill count is capped.  Without a cap a single mutant asking for the
        largest legal block would be able to clear a large part of the soup on
        every failed attempt -- a weapon, not a resource limit.  With the cap, a
        request that still cannot be met after ``max_kills`` deaths simply
        fails, which is what fragmentation looks like from inside a creature.
        """
        if not self.reap_on_alloc_failure:
            return None
        for _ in range(max_kills):
            if len(self.reaper) <= 1:
                break
            victim = self.reaper.head()
            if victim is requester:
                victim = self.reaper.next_after(victim)
            if victim is None:
                break
            self.kill(victim)
            addr = self.memory.allocate(size)
            if addr is not None:
                return addr
        return None

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
            if self.errors_hasten_death and cr.stats.errors > before_errors:
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
