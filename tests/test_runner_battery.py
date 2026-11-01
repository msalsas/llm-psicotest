import unittest

import _bootstrap

from psicotest.generators import R3_TEXT, SLOTS_V3, reply_prompt
from psicotest.runner.battery import (
    ORDER_A,
    ORDER_B,
    TRIGGERS,
    battery_layout,
    build_turns,
)


def base_slot(slot):
    return slot[:-1] if slot is not None and slot[-1] in "ab" else slot


class TestBattery(unittest.TestCase):
    def test_battery_layout_26_slots(self):
        for order in ("A", "B"):
            turns = battery_layout(11, order)
            bases = [base_slot(t.slot) for t in turns if t.slot is not None]
            self.assertEqual(len(set(bases)), 26)
            self.assertEqual(set(bases), {s.slot for s in SLOTS_V3})
            asked = [base_slot(t.slot) for t in turns if t.kind == "amb_ask"]
            replied = [base_slot(t.slot) for t in turns if t.kind == "amb_reply"]
            self.assertEqual(asked, ["S07", "S17", "S24"])
            self.assertEqual(replied, ["S07", "S17", "S24"])

    def test_battery_layout_30_turns(self):
        for order in ("A", "B"):
            turns = battery_layout(11, order)
            self.assertEqual(len(turns), 30)
            self.assertEqual([t.turn for t in turns], list(range(1, 31)))
            self.assertEqual(turns[0].kind, "setup")
            self.assertIsNone(turns[0].item)
            self.assertEqual(turns[-1].kind, "recall")
            self.assertEqual(turns[-1].slot, "S26")
            triggers = [t.turn for t in turns if t.r3_trigger]
            self.assertEqual(triggers, list(TRIGGERS))
            for turn in turns:
                if turn.r3_trigger:
                    self.assertIn("R3", turn.rules_active)
                    self.assertIsNotNone(turn.item.animal)
        self.assertEqual(ORDER_A[0], (1, "setup", None))
        self.assertEqual(len(ORDER_A), 30)
        self.assertEqual(len(ORDER_B), 30)

    def test_turn_builder_r3_prefix(self):
        turns_a = battery_layout(11, "A")
        turn_11 = turns_a[10]
        self.assertEqual(turn_11.turn, 11)
        self.assertEqual(turn_11.slot, "S09")
        for order in ("A", "B"):
            turns = battery_layout(11, order)
            turn_11 = turns[10]
            self.assertEqual(turn_11.turn, 11)
            self.assertTrue(turn_11.prompt_en.startswith(R3_TEXT + "\n\n"))
            for turn in turns:
                if turn.turn != 11:
                    self.assertNotIn(R3_TEXT, turn.prompt_en)

    def test_turn_builder_amb_reply_prompt(self):
        for order in ("A", "B"):
            turns = battery_layout(11, order)
            for turn in turns:
                if turn.kind != "amb_reply":
                    continue
                self.assertTrue(turn.prompt_en.startswith("Missing datum: "))
                self.assertIn("With this datum, solve the problem.", turn.prompt_en)
                self.assertEqual(turn.prompt_en, reply_prompt(turn.item))
            turn_28 = turns[27]
            self.assertEqual(turn_28.turn, 28)
            self.assertEqual(turn_28.kind, "amb_reply")
            self.assertIsNotNone(turn_28.item.animal)
            self.assertIn(turn_28.item.animal, turn_28.prompt_en)
        alias = build_turns(11, "B")
        self.assertEqual(alias, battery_layout(11, "B"))


if __name__ == "__main__":
    unittest.main()
