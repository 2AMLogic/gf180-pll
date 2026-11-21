"""``pll_top``'s composed flat LVS reference (issues #237, #149).

The composer (:mod:`pll_top.top_level.reference`) is the mechanical path
from the five blocks' own ``reference_netlist()`` outputs plus
``design/netlist/pll_top.spice``'s instance lines to the one flat netlist
the foundry LVS deck needs against the flat assembled GDS. These tests pin
the composition's contract -- device completeness, the substrate merge, the
option-A loop-filter pin, and the port-map/wiring reading -- so a block
reference or schematic wiring change that silently desynchronises the
top-level reference fails here before it wastes an LVS run.

Run:

    python3 -m unittest discover -s layout/tests -t layout/tests \
        -p test_top_level_reference.py -v
"""

from __future__ import annotations

import unittest
from collections import Counter

from _env import HAVE_KLAYOUT, LAYOUT_DIR  # noqa: F401

from pll_top.top_level import netlist as NL  # noqa: E402
from pll_top.top_level import reference as REF  # noqa: E402


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (the block modules import it)")
class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REF.top_reference_netlist()
        cls.lines = cls.text.splitlines()
        cls.cards = [line for line in cls.lines if line.startswith(REF._DEVICE_CARD_PREFIXES)]
        cls.nl = NL.read()

    def test_header_is_the_schematic_pins(self):
        header = next(line for line in self.lines if line.startswith(".subckt"))
        self.assertEqual(header, f".subckt pll_top {' '.join(self.nl.pins)}")
        self.assertIn("GND_VCO", header)  # still a top-level *pin* (a metal net), see the merge test

    def test_device_count_is_the_sum_of_the_block_references(self):
        per_block = {}
        for inst in self.nl.instances:
            ref = REF._block_reference_text(inst.subckt)
            per_block[inst.subckt] = sum(
                1 for line in ref.splitlines() if line.startswith(REF._DEVICE_CARD_PREFIXES)
            )
        self.assertEqual(len(self.cards), sum(per_block.values()), per_block)

    def test_every_card_names_exactly_one_model(self):
        for card in self.cards:
            tokens = card.split()
            models = [t for t in tokens if t in REF.DEVICE_MODELS]
            self.assertEqual(len(models), 1, card)

    def test_device_names_are_unique(self):
        names = [card.split()[0] for card in self.cards]
        self.assertEqual(len(names), len(set(names)))

    def test_substrate_merge_removed_every_device_terminal_gnd_vco(self):
        # GND_VCO survives only as the .subckt pin; no device terminal may
        # carry it, or the deck's single substrate node could never match.
        for card in self.cards:
            self.assertNotIn("GND_VCO", card.split(), card)
        self.assertIn("GND_VCO", next(l for l in self.lines if l.startswith(".subckt")))

    def test_vdd_vco_stays_its_own_net(self):
        joined = "\n".join(self.cards)
        self.assertIn("VDD_VCO", joined)
        self.assertTrue(any(card.split()[0].startswith("C_XVCO_") for card in self.cards))

    def test_loop_filter_is_pinned_to_option_a(self):
        option_a = [c for c in self.cards if "cap_mim_2f0_m2m3_noshield" in c]
        option_b = [c for c in self.cards if "cap_mim_2f0_m4m5_noshield" in c]
        self.assertEqual(len(option_a), 1, option_a)
        self.assertEqual(option_b, [], "committed assembly is option A (DR-006); B is #753 follow-up")
        self.assertTrue(option_a[0].startswith("C_XLF_"), option_a)

    def test_port_maps_follow_the_schematic_instance_lines(self):
        # XPFD: its own B0/B1 land on pll_top's CPB0/CPB1; VOUT lands on VCTRL.
        pfd = next(inst for inst in self.nl.instances if inst.subckt == "pfd_cp")
        self.assertEqual(pfd.port_net()["B0"], "CPB0")
        self.assertEqual(pfd.port_net()["VOUT"], "VCTRL")
        pfd_cards = [c for c in self.cards if c.split()[0].startswith("M_XPFD_")]
        self.assertTrue(pfd_cards)
        self.assertFalse(any(" VOUT " in f" {c} " for c in pfd_cards), "VOUT must be renamed to VCTRL")
        # XDIV: its CKIN-equivalent port is named VCO and lands on CLK.
        div = next(inst for inst in self.nl.instances if inst.subckt == "divider_chain")
        self.assertEqual(dict(zip(div.ports, div.nets))["VCO"], "CLK")

    def test_internal_nets_are_path_qualified(self):
        bare_internals = ["NC", "NOFF", "NVI"]  # vco bias resistors' own nets
        for net in bare_internals:
            prefixed = [c for c in self.cards if f" XVCO_{net} " in f" {c} "]
            self.assertTrue(prefixed, net)
            for card in self.cards:
                tokens = card.split()
                self.assertNotIn(net, tokens[1:], f"bare internal net {net!r} leaked: {card}")

    def test_every_pll_top_net_reaches_at_least_one_device_or_is_the_vwin_input(self):
        # A top net that no device and no card carries would mean the wiring
        # reading dropped a port. VWIN is the one real exception: pll_top's
        # window-threshold input feeds only the lock detector's own gate
        # terminals, all of which carry VWIN.
        joined_tokens: Counter = Counter()
        for card in self.cards:
            joined_tokens.update(card.split())
        for pin in self.nl.pins:
            if pin in REF.SUBSTRATE_MERGE:
                # merged into the substrate node (VSS): no device terminal
                # carries it by design -- see reference.SUBSTRATE_MERGE.
                self.assertEqual(joined_tokens[pin], 0, pin)
            else:
                self.assertGreater(joined_tokens[pin], 0, pin)


if __name__ == "__main__":
    unittest.main()
