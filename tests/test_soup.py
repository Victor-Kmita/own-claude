"""Tests for the soup machine.

The simulation's results are only worth reading if the machine underneath them
is exactly what the write-up claims it is, so these tests are mostly about
pinning down semantics that would otherwise drift: what a template search
returns, who may write where, when a division is allowed to succeed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soup import analysis
from soup.asm import AssemblyError, assemble, disassemble
from soup.isa import INSTRUCTIONS, NOP0, NOP1, OPCODE
from soup.vm import Creature, Memory, find_template, run_slice, STACK_DEPTH
from soup.world import GeneBank, ReaperQueue, World

ANCESTOR_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "soup", "ancestor.sm")


def ancestor():
    with open(ANCESTOR_SRC) as fh:
        return assemble(fh.read())


class TestIsa(unittest.TestCase):
    def test_opcode_space_is_saturated(self):
        # Every 5-bit pattern must decode, or mutation would be able to crash
        # the machine instead of merely changing the program.
        self.assertEqual(len(INSTRUCTIONS), 32)
        self.assertEqual(len(set(INSTRUCTIONS)), 32)

    def test_nop_encoding(self):
        self.assertEqual((NOP0, NOP1), (0, 1))


class TestAssembler(unittest.TestCase):
    def test_template_sugar(self):
        self.assertEqual(assemble(".t 1011"), [NOP1, NOP0, NOP1, NOP1])

    def test_comments_labels_and_whitespace(self):
        code = assemble("  loop:  incA ; comment\n\n  incB\n")
        self.assertEqual(code, [OPCODE["incA"], OPCODE["incB"]])

    def test_rejects_unknown_instruction(self):
        with self.assertRaises(AssemblyError):
            assemble("frobnicate")

    def test_rejects_bad_template(self):
        with self.assertRaises(AssemblyError):
            assemble(".t 1021")

    def test_disassembly_round_trips(self):
        code = ancestor()
        text = disassemble(code)
        stripped = "\n".join(line.split(None, 1)[1] for line in text.splitlines())
        self.assertEqual(assemble(stripped), code)


class TestMemory(unittest.TestCase):
    def test_first_fit_and_free(self):
        m = Memory(100)
        a = m.allocate(30)
        b = m.allocate(20)
        self.assertEqual((a, b), (0, 30))
        self.assertEqual(m.used, 50)
        m.free(a, 30)
        self.assertEqual(m.used, 20)
        self.assertIn((0, 30), list(m.gaps()))

    def test_allocation_fails_when_fragmented(self):
        m = Memory(100)
        m.allocate(40)
        m.allocate(20)
        m.free(0, 40)
        self.assertIsNone(m.allocate(80))
        # First fit resumes from the rotating cursor rather than from address 0,
        # so new creatures spread through the soup instead of piling up low.
        self.assertEqual(m.allocate(40), 60)

    def test_rejects_absurd_sizes(self):
        m = Memory(50)
        self.assertIsNone(m.allocate(0))
        self.assertIsNone(m.allocate(51))


class TestTemplateSearch(unittest.TestCase):
    def setUp(self):
        self.soup = [OPCODE["zero"]] * 40
        self.soup[10:12] = [NOP1, NOP1]
        self.soup[30:32] = [NOP1, NOP1]

    def test_backward_and_forward(self):
        want = [NOP1, NOP1]
        self.assertEqual(find_template(self.soup, 40, 20, want, -1, 40), 10)
        self.assertEqual(find_template(self.soup, 40, 20, want, +1, 40), 30)

    def test_outward_prefers_nearest(self):
        want = [NOP1, NOP1]
        self.assertEqual(find_template(self.soup, 40, 25, want, 0, 40), 30)
        self.assertEqual(find_template(self.soup, 40, 15, want, 0, 40), 10)

    def test_search_limit_is_respected(self):
        want = [NOP1, NOP1]
        self.assertIsNone(find_template(self.soup, 40, 20, want, -1, 3))

    def test_wraps_around_the_soup(self):
        soup = [OPCODE["zero"]] * 20
        soup[0:2] = [NOP1, NOP1]
        self.assertEqual(find_template(soup, 20, 18, soup[0:2], +1, 20), 0)

    def test_no_match_returns_none(self):
        self.assertIsNone(find_template(self.soup, 40, 20, [NOP0, NOP0, NOP0], 0, 40))


class _Harness(World):
    """A world with one creature at address 0 and nothing else going on."""

    def __init__(self, code, **kw):
        kw.setdefault("soup_size", 500)
        kw.setdefault("copy_mutation_rate", 0.0)
        kw.setdefault("cosmic_period", 10 ** 12)
        kw.setdefault("filler", OPCODE["zero"])
        super().__init__(**kw)
        self.creature = self.inject(code, address=0)

    def run(self, n):
        return run_slice(self, self.creature, n)


class TestInstructions(unittest.TestCase):
    def test_constant_building(self):
        h = _Harness(assemble("zero incC incC shl or1"))
        h.run(5)
        self.assertEqual(h.creature.cpu.cx, 5)          # ((0+1+1) << 1) ^ 1

    def test_ifz_skips_when_nonzero(self):
        h = _Harness(assemble("incC ifz incA incB"))
        h.run(3)
        self.assertEqual((h.creature.cpu.ax, h.creature.cpu.bx), (0, 1))

    def test_ifz_executes_when_zero(self):
        h = _Harness(assemble("ifz incA incB"))
        h.run(3)
        self.assertEqual((h.creature.cpu.ax, h.creature.cpu.bx), (1, 1))

    def test_subtraction_wraps_unsigned(self):
        h = _Harness(assemble("incB subCAB"))
        h.run(2)
        self.assertEqual(h.creature.cpu.cx, 0xFFFFFFFF)

    def test_stack_is_circular(self):
        h = _Harness(assemble("incA " + "pushA " * (STACK_DEPTH + 1) + "popB"))
        h.run(STACK_DEPTH + 3)
        self.assertEqual(h.creature.cpu.bx, 1)

    def test_adr_reports_address_and_template_length(self):
        h = _Harness(assemble(".t 1111 adrb .t 0000"))
        h.run(5)                                  # four nops, then the adrb
        self.assertEqual((h.creature.cpu.ax, h.creature.cpu.cx), (0, 4))

    def test_failed_search_is_an_error_not_a_crash(self):
        h = _Harness(assemble("adrf .t 0000"))
        h.run(1)
        self.assertEqual(h.creature.stats.errors, 1)

    def test_call_and_ret(self):
        h = _Harness(assemble("call .t 00 incA .t 11 incB ret"))
        #                      0    1-2 3     4-5  6    7
        h.run(1)
        self.assertEqual(h.creature.cpu.ip, 6)    # landed just past the target template
        h.run(1)
        self.assertEqual(h.creature.cpu.bx, 1)
        h.run(1)                                  # ret -> the instruction after the call
        self.assertEqual(h.creature.cpu.ip, 3)
        h.run(1)
        self.assertEqual(h.creature.cpu.ax, 1)

    def test_write_protection(self):
        h = _Harness(assemble("movii"), soup_size=500)
        cr = h.creature
        cr.cpu.ax, cr.cpu.bx = 0, 400            # outside its own block
        h.run(1)
        self.assertEqual(cr.stats.errors, 1)
        self.assertEqual(h.soup[400], OPCODE["zero"])

    def test_write_into_own_genome_is_allowed(self):
        h = _Harness(assemble("movii incA incB"))
        cr = h.creature
        cr.cpu.ax, cr.cpu.bx = 1, 2
        h.run(1)
        self.assertEqual(h.soup[2], h.soup[1])
        self.assertEqual(cr.stats.errors, 0)

    def test_mal_rejects_out_of_range_sizes(self):
        h = _Harness(assemble("mal"), min_daughter_size=8, max_daughter_size=100)
        h.creature.cpu.cx = 4
        h.run(1)
        self.assertEqual(h.creature.stats.errors, 1)
        self.assertIsNone(h.creature.daughter)

    def test_mal_allocates_and_reallocation_frees_the_old_block(self):
        h = _Harness(assemble("mal mal"), min_daughter_size=8, max_daughter_size=100)
        h.creature.cpu.cx = 16
        h.run(1)
        first = h.creature.daughter
        self.assertIsNotNone(first)
        used = h.memory.used
        h.run(1)
        self.assertEqual(h.memory.used, used)     # old daughter released
        self.assertIsNotNone(h.creature.daughter)

    def test_divide_requires_a_daughter(self):
        h = _Harness(assemble("divide"))
        h.run(1)
        self.assertEqual(h.creature.stats.errors, 1)

    def test_divide_refuses_a_mostly_uncopied_daughter(self):
        h = _Harness(assemble("divide"), min_daughter_size=8)
        h.creature.daughter = (200, 16)
        h.creature.daughter_writes = 3
        h.run(1)
        self.assertEqual(h.creature.stats.errors, 1)
        self.assertEqual(h.births, 0)

    def test_divide_releases_the_daughter(self):
        h = _Harness(assemble("divide"), min_daughter_size=8)
        h.memory.allocate(16)
        h.creature.daughter = (h.memory.blocks[-1][0], 16)
        h.creature.daughter_writes = 16
        h.run(1)
        self.assertEqual(h.births, 1)
        self.assertIsNone(h.creature.daughter)

    def test_every_opcode_executes_without_raising(self):
        # Mutation will eventually put every opcode in front of every register
        # state; none of them may raise.
        for op in range(32):
            h = _Harness([op] + [OPCODE["nop1"], OPCODE["nop0"]])
            h.creature.cpu.ax = h.creature.cpu.bx = 3
            h.creature.cpu.cx = 16
            h.run(3)


class TestAncestor(unittest.TestCase):
    def test_length_and_shape(self):
        code = ancestor()
        self.assertEqual(len(code), 64)
        self.assertEqual(code[:4], [NOP1] * 4)

    def test_replicates_in_a_sterile_soup(self):
        result = analysis.isolation_assay(bytes(ancestor()))
        self.assertTrue(result["self_sufficient"])
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["foreign_calls"], 0)
        self.assertEqual(result["foreign_reads"], 0)

    def test_replication_costs_410_instructions(self):
        # The number every evolved descendant is measured against.  It is here
        # so that a change to the instruction set or the scheduler that makes
        # replication cheaper or dearer cannot pass unnoticed.
        self.assertEqual(analysis.describe(bytes(ancestor()))["cost"], 410)

    def test_daughter_is_an_exact_copy(self):
        code = ancestor()
        w = World(soup_size=2000, copy_mutation_rate=0.0, cosmic_period=10 ** 12,
                  filler=OPCODE["zero"])
        mother = w.inject(code, address=0)
        while w.births == 0:
            w.step_generation()
        child = [c for c in w.creatures if c.cid != mother.cid][0]
        self.assertEqual(w.read_genome(child.start, child.size), bytes(code))
        self.assertEqual(child.genotype, mother.genotype)
        self.assertEqual(child.generation, 1)

    def test_fills_the_soup_and_stabilises(self):
        code = ancestor()
        w = World(soup_size=8000, copy_mutation_rate=0.0, cosmic_period=10 ** 12)
        w.inject(code, address=0)
        while w.clock < 1_000_000:
            w.step_generation()
        self.assertGreater(w.alive_count(), 20)
        self.assertLessEqual(w.memory.load, w.reap_threshold + 0.05)
        self.assertEqual(w.population().most_common(1)[0][0], "0064aaa")

    def test_two_housekeeping_policies_decide_whether_mutation_is_optional(self):
        # Both mutation switches are off in all three worlds below.  What
        # differs is only housekeeping, and only the third world evolves.
        code = ancestor()

        def outcome(lazy, errors_kill):
            w = World(soup_size=4000, copy_mutation_rate=0.0,
                      cosmic_period=10 ** 18, reap_on_alloc_failure=not lazy,
                      errors_hasten_death=errors_kill)
            w.inject(code, address=0)
            while w.clock < 3_000_000:
                w.step_generation()
            return w.alloc_failures, len(w.genebank.genome)

        failures, seen = outcome(lazy=False, errors_kill=True)
        self.assertEqual((failures, seen), (0, 1))     # reaper keeps room: no mutagen

        failures, seen = outcome(lazy=True, errors_kill=True)
        self.assertGreater(failures, 0)                # the mutagen fires
        self.assertEqual(seen, 1)                      # ... and is reaped every time

        failures, seen = outcome(lazy=True, errors_kill=False)
        self.assertGreater(failures, 0)
        self.assertGreater(seen, 1)                    # now it founds lineages

    def test_failed_allocation_makes_the_ancestor_damage_itself(self):
        # The mechanism, in isolation.  ``mal`` leaves ax alone when it fails,
        # and ax happens to be holding the address of the creature's own END
        # marker at that moment.  The copy loop then dutifully writes the START
        # marker over the END marker -- a write into its own genome, which is
        # permitted -- and the creature can no longer measure itself.
        code = ancestor()
        w = World(soup_size=len(code) + 40, copy_mutation_rate=0.0,
                  cosmic_period=10 ** 12, filler=OPCODE["zero"])
        cr = w.inject(code, address=0)
        run_slice(w, cr, 40)              # self-inspection, then the failing mal
        run_slice(w, cr, 40)              # the copy loop, aimed at itself
        self.assertEqual(list(w.read_genome(60, 4)), [NOP1] * 4)
        self.assertGreater(cr.stats.errors, 0)


class TestReaperQueue(unittest.TestCase):
    def make(self, n):
        q = ReaperQueue()
        crs = [Creature(i, i * 10, 10) for i in range(n)]
        for c in crs:
            q.append(c)
        return q, crs

    def test_head_is_the_oldest(self):
        q, crs = self.make(3)
        self.assertIs(q.head(), crs[0])

    def test_errors_move_a_creature_toward_death(self):
        q, crs = self.make(3)
        q.move_toward_head(crs[2])
        self.assertEqual(q.order_cids(), [0, 2, 1])

    def test_reproduction_moves_a_creature_away_from_death(self):
        q, crs = self.make(3)
        q.move_toward_tail(crs[0])
        self.assertEqual(q.order_cids(), [1, 0, 2])

    def test_removal_preserves_the_order_of_everyone_else(self):
        # The point of the linked list: taking one creature out must not
        # teleport the youngest to the front of the death queue.
        q, crs = self.make(5)
        q.remove(crs[1])
        self.assertEqual(q.order_cids(), [0, 2, 3, 4])
        q.remove(crs[0])
        self.assertEqual(q.order_cids(), [2, 3, 4])
        self.assertIs(q.head(), crs[2])
        self.assertEqual(len(q), 3)

    def test_moving_at_the_ends_is_a_no_op(self):
        q, crs = self.make(3)
        q.move_toward_head(crs[0])
        q.move_toward_tail(crs[2])
        self.assertEqual(q.order_cids(), [0, 1, 2])

    def test_append_after_removals_still_lands_at_the_tail(self):
        q, crs = self.make(3)
        q.remove(crs[2])
        extra = Creature(9, 900, 10)
        q.append(extra)
        self.assertEqual(q.order_cids(), [0, 1, 9])


class TestGeneBank(unittest.TestCase):
    def test_names_are_length_plus_letters(self):
        gb = GeneBank()
        self.assertEqual(gb.name(b"\x01\x02", 0, None), "0002aaa")
        self.assertEqual(gb.name(b"\x01\x03", 0, None), "0002aab")
        self.assertEqual(gb.name(b"\x01\x02", 0, None), "0002aaa")

    def test_modal_parent_is_the_usual_route_not_the_first_one(self):
        gb = GeneBank()
        gb.name(b"\x01\x02", 0, "0008aaa")        # freak first appearance
        for _ in range(5):
            gb.name(b"\x01\x02", 0, "0064aaa")    # the route it actually travels
        self.assertEqual(gb.origin["0002aaa"], "0008aaa")
        self.assertEqual(gb.modal_parent("0002aaa"), "0064aaa")

    def test_fidelity_separates_lineages_from_accidents(self):
        gb = GeneBank()
        for _ in range(10):
            gb.name(b"\x01\x02", 0, "0002aaa")       # breeds true
        for _ in range(10):
            gb.name(b"\x01\x03", 0, "0064aaa")       # produced by something else
        self.assertEqual(gb.fidelity("0002aaa"), 1.0)
        self.assertEqual(gb.fidelity("0002aab"), 0.0)


class TestDeterminism(unittest.TestCase):
    def run_once(self):
        w = World(soup_size=6000, seed=42, copy_mutation_rate=1 / 800,
                  cosmic_period=1500)
        w.inject(ancestor(), address=0)
        while w.clock < 300_000:
            w.step_generation()
        return w.births, w.deaths, sorted(w.population().items())

    def test_same_seed_same_world(self):
        self.assertEqual(self.run_once(), self.run_once())


class TestAnalysis(unittest.TestCase):
    def test_truncated_fragment_is_inert(self):
        fragment = bytes(ancestor()[:11])
        self.assertEqual(analysis.classify(fragment), "inert")

    def test_dividing_is_not_the_same_as_reproducing(self):
        # Asks for the smallest legal block, scribbles in half of it, divides.
        # It reproduces *something* in a few dozen instructions, but never
        # itself -- and a classifier that counts divisions rather than copies
        # would rank this junk above every real replicator in the soup.
        junk = assemble("zero " + "incC " * 8 + "mal movBA "
                        + "movii incB " * 5 + "divide")
        result = analysis.isolation_assay(bytes(junk))
        self.assertTrue(result["divided"])
        self.assertFalse(result["self_sufficient"])
        what = analysis.describe(bytes(junk))
        self.assertNotEqual(what["kind"], "replicator")
        self.assertTrue(what["divides_without_copying"])

    def test_a_truncated_creature_reproduces_its_neighbour_not_itself(self):
        # Cut the ancestor's copy procedure off but leave the 1100 marker that
        # names it.  Its `call` still finds that marker, jumps to where the copy
        # loop used to be, runs off the end of its own genome and into whatever
        # lies next -- the top of the neighbour's body.  The neighbour's
        # self-inspection then runs on the neighbour's coordinates, so the
        # daughter is a copy of the *host*.  The creature spends its whole CPU
        # allowance reproducing somebody else.
        code = ancestor()
        truncated = bytes(code[:45])
        out = analysis.coculture_assay(truncated, bytes(code), budget=150_000)
        self.assertEqual(dict(out["with_host"]["offspring"]), {"host": 1})
        self.assertGreater(out["with_host"]["guest_foreign_calls"], 0)
        self.assertEqual(analysis.interaction(truncated, bytes(code),
                                              budget=150_000), "hijacked")

    def test_a_host_that_loses_the_template_loses_the_parasite(self):
        # The mechanism behind the resistant replicator in baseline-s2, built by
        # hand so that the causation is not in doubt.
        #
        # A parasite is a creature that has lost its own copy loop *and* the
        # marker that names it, so its `call` searches outward and lands in
        # somebody else's.  What it seeks is the four-cell pattern 1100.  A host
        # that still has a working copy loop but no longer has 1100 anywhere in
        # its genome is invisible to that search -- immunity by receptor loss,
        # at no cost to the host's own replication.
        code = ancestor()
        parasite = list(code[:45])              # copy procedure gone
        parasite[40] = NOP0                     # and its own 1100 marker with it
        parasite = bytes(parasite)

        resistant = list(code)
        resistant[43] = NOP1                    # copy-loop marker 1100 -> 1101
        resistant[32] = NOP0                    # its own call now seeks 1101
        resistant = bytes(resistant)

        self.assertEqual(analysis.classify(parasite, budget=150_000),
                         "host-dependent")
        self.assertEqual(analysis.describe(resistant)["kind"], "replicator")
        self.assertEqual(analysis.describe(resistant)["cost"],
                         analysis.describe(bytes(code))["cost"])

        # 150k instructions is ~350 replication times for a healthy creature,
        # so a genotype that has not reproduced by then is not going to.
        beside_ancestor = analysis.coculture_assay(parasite, bytes(code),
                                                   budget=150_000)
        beside_resistant = analysis.coculture_assay(parasite, resistant,
                                                    budget=150_000)
        self.assertTrue(sum(beside_ancestor["with_host"]["offspring"].values()))
        self.assertFalse(sum(beside_resistant["with_host"]["offspring"].values()))

    def test_genome_diff_reports_substitutions_and_length(self):
        a = bytes([1, 2, 3])
        b = bytes([1, 5, 3, 4])
        text = analysis.genome_diff(a, b)
        self.assertIn("->", text)
        self.assertEqual(len(text.splitlines()), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
