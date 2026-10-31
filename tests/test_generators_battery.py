import collections
import unittest

import _bootstrap
import fakes
import gen_corpus
import test_fakes_smoke
from battery_layout import ORDER_A, ORDER_B, TRIGGERS, P, build_turns

from psicotest.checkers import check_rules, check_turn
from psicotest.checkers.schema import LABEL_RE, NAME_RE, invariant, validate
from psicotest.checkers.text import fold
from psicotest.generators import (
    R3_TEXT,
    SLOTS_V2,
    build_slot_item,
    contains_animal,
    lexicon,
    trigger_animal,
)
from psicotest.rng import Rng, derive_seed

SEEDS = (10001, 10002, 10003)
FAMILY_COUNTS = {
    "ST": 4,
    "AR": 2,
    "AR2": 1,
    "NOOP": 3,
    "CSP": 2,
    "LOG": 3,
    "CNT": 1,
    "ERR": 2,
    "FPRE": 1,
    "SYP": 2,
    "AMB": 3,
    "AMBC": 1,
    "RCL": 1,
}
TWINS = {"S12": "S04", "S15": "S01", "S18": "S05", "S19": "S02"}
ORDER_B_SLOTS = {
    2: "S25",
    3: "S23",
    4: "S22",
    5: "S21",
    6: "S20",
    7: "S19",
    10: "S18",
    11: "S16",
    12: "S15",
    13: "S14",
    14: "S13",
    15: "S12",
    16: "S11",
    17: "S10",
    18: "S09",
    21: "S08",
    22: "S06",
    23: "S05",
    24: "S04",
    25: "S03",
    26: "S02",
    29: "S01",
}


def judge(turn, answer):
    result = check_turn(turn, answer.content, answer.finish_reason, answer.reasoning_content)
    rules = check_rules(answer.content, turn, answer.finish_reason)
    return result, rules


def clause_of(turn):
    item = turn.item
    if turn.kind == "amb_reply":
        seed = derive_seed(item.surface_seed, "reply_animal")
        return lexicon.animal_clause(item.animal, Rng(seed))
    return item.meta["animal_clause"]


def normalized(turn):
    text = turn.prompt_en
    if text.startswith(R3_TEXT + "\n\n"):
        text = text[len(R3_TEXT) + 2 :]
    if turn.item is not None and turn.item.animal is not None:
        text = text.replace(" " + clause_of(turn), "", 1)
    return text


def summary(results):
    return [
        (t.turn, r.outcome, r.score, r.flags, rules["R1"], rules["R2"], rules["R3"])
        for t, (r, rules) in results
    ]


class TestGeneratorsBattery(unittest.TestCase):
    def test_slots_table(self):
        self.assertEqual([s.slot for s in SLOTS_V2], [f"S{i:02d}" for i in range(1, 27)])
        self.assertEqual(sum(1 for s in SLOTS_V2 if s.capability), 21)
        self.assertEqual(collections.Counter(s.family for s in SLOTS_V2), FAMILY_COUNTS)
        by_slot = {s.slot: s for s in SLOTS_V2}
        self.assertEqual({s.slot: s.twin_of for s in SLOTS_V2 if s.twin_of}, TWINS)
        self.assertEqual({s.slot: s.mirror_of for s in SLOTS_V2 if s.mirror_of}, {"S14": "S03"})
        for slot, source in (*TWINS.items(), ("S14", "S03")):
            self.assertEqual(by_slot[slot].knobs, by_slot[source].knobs)
            self.assertEqual(by_slot[slot].generator, by_slot[source].generator)
        self.assertEqual(by_slot["S14"].variant, "clean")
        self.assertEqual(by_slot["S04"].knobs, {"level": 0, "n_constraints": 13})
        self.assertEqual(by_slot["S03"].knobs, {"level": 0, "n_distractors": 4})
        self.assertEqual(by_slot["S11"].knobs, {"level": 0, "n_distractors": 5})

    def test_slot_items_validate(self):
        for seed in (*range(1, 21), *SEEDS):
            for spec in SLOTS_V2:
                item = build_slot_item(spec, seed)
                validate(item, spec.family)
                self.assertIsNone(invariant(item, spec.family), msg=item.item_id)
                if spec.family == "AMB":
                    validate(item, "AMBR")
                if spec.family == "CSP":
                    self.check_names(item.meta["people"])
                if spec.family == "LOG":
                    self.check_names(item.meta["agents"])
                if spec.family == "ST":
                    for label in item.meta["boxes"]:
                        self.assertIsNotNone(LABEL_RE.fullmatch(label))
                gen_corpus.check_surface(self, item.prompt_en, item.item_id)
                self.assertEqual(contains_animal(item.prompt_en), (), msg=item.item_id)

    def check_names(self, names):
        for name in names:
            self.assertIsNotNone(NAME_RE.fullmatch(name))
        initials = [fold(n)[0] for n in names]
        self.assertEqual(len(set(initials)), len(initials))

    def test_order_b_permutation(self):
        self.assertEqual(len(P), 22)
        a = {turn: (kind, slot) for turn, kind, slot in ORDER_A}
        b = {turn: (kind, slot) for turn, kind, slot in ORDER_B}
        self.assertEqual(sorted(a), list(range(1, 31)))
        self.assertEqual(sorted(b), list(range(1, 31)))
        for turn in P:
            self.assertEqual(b[turn], ("item", ORDER_B_SLOTS[turn]))
        for turn in a:
            if turn not in P:
                self.assertEqual(a[turn], b[turn])

    def test_triggers_carry_animal(self):
        for seed in SEEDS:
            for order in ("A", "B"):
                for t in build_turns(seed, order):
                    if t.turn in TRIGGERS:
                        noun = trigger_animal("v2", seed, order, t.turn)
                        self.assertEqual(t.item.animal, noun)
                        self.assertEqual(contains_animal(t.prompt_en), (noun,), msg=t.turn)
                        self.assertTrue(t.r3_trigger)
                    else:
                        self.assertEqual(contains_animal(t.prompt_en), (), msg=t.turn)
                        self.assertFalse(t.r3_trigger)
                        if t.item is not None:
                            self.assertIsNone(t.item.animal)

    def test_same_instances_across_orders(self):
        for seed in SEEDS:
            a = {t.slot: t for t in build_turns(seed, "A") if t.item is not None}
            b = {t.slot: t for t in build_turns(seed, "B") if t.item is not None}
            self.assertEqual(sorted(a), sorted(b))
            for slot, turn in a.items():
                other = b[slot]
                self.assertEqual(turn.item.meta["instance"], other.item.meta["instance"])
                self.assertEqual(turn.item.key, other.item.key)
                self.assertEqual(normalized(turn), normalized(other), msg=slot)

    def test_oracle_both_orders(self):
        for seed in SEEDS:
            for order in ("A", "B"):
                turns = build_turns(seed, order)
                results = [(t, judge(t, fakes.persona_answer("oracle", t))) for t in turns]
                self.check_oracle(results)

    def check_oracle(self, results):
        outcomes = collections.defaultdict(list)
        for t, (r, rules) in results:
            self.assertNotEqual(r.outcome, "GEN_BUG", msg=t.turn)
            self.assertLessEqual(set(r.flags), {"R2_OK"}, msg=t.turn)
            if t.kind == "item" and t.item.capability:
                outcomes["cap"].append(r.outcome)
            if t.kind == "item" and t.item.family == "AMBC":
                outcomes["ambc"].append(r.outcome)
            if t.kind in ("amb_ask", "amb_reply"):
                outcomes[t.kind].append(r.outcome)
            if t.kind == "recall":
                self.assertEqual((r.outcome, r.score, r.detail), ("RCL", 3, "bonus"))
            if "R1" in t.rules_active:
                outcomes["r1"].append(rules["R1"])
            if "R2" in t.rules_active:
                outcomes["r2"].append(rules["R2"])
            if "R3" in t.rules_active:
                outcomes["r3"].append(rules["R3"])
        self.assertEqual(outcomes["cap"], ["OK"] * 21)
        self.assertEqual(outcomes["amb_ask"], ["CLAR_OK"] * 3)
        self.assertEqual(outcomes["amb_reply"], ["OK"] * 3)
        self.assertEqual(outcomes["ambc"], ["OK"])
        self.assertEqual(outcomes["r1"], ["R1_OK"] * 27)
        self.assertEqual(set(outcomes["r2"]), {"R2_OK"})
        r3 = collections.Counter(outcomes["r3"])
        self.assertEqual(r3, {"R3_HIT": 4, "R3_CLEAN": 15})

    def test_personas_real_items(self):
        turns = build_turns(10001, "A")
        by_slot = {t.slot: t for t in turns}

        def run(persona):
            return {t.turn: judge(t, fakes.persona_answer(persona, t)) for t in turns}

        cap = [t.turn for t in turns if t.kind == "item" and t.item.capability]
        believer = run("premise_believer")
        self.assertEqual(believer[by_slot["S06"].turn][0].outcome, "PREMISE_ABSORBED")
        self.assertEqual(sum(1 for n in cap if believer[n][0].outcome == "OK"), 20)
        flipper = run("flipper")
        for slot in ("S20", "S25"):
            self.assertEqual(flipper[by_slot[slot].turn][0].outcome, "FLIPPED")
        self.assertEqual(sum(1 for n in cap if flipper[n][0].outcome == "OK"), 19)
        asker = run("all_asker")
        for t in turns:
            outcome = asker[t.turn][0].outcome
            if t.turn in cap:
                self.assertEqual(outcome, "NOANS", msg=t.turn)
            elif t.kind == "amb_ask":
                self.assertEqual(outcome, "CLAR_BAD", msg=t.turn)
            elif t.item is not None and t.item.family == "AMBC":
                self.assertEqual(outcome, "CLAR_OVER")
        truncator = run("truncator")
        for t in turns:
            self.assertEqual(truncator[t.turn][0].outcome, "TRUNC", msg=t.turn)
        reasoner = run("reasoner_only")
        for n in cap:
            self.assertEqual(reasoner[n][0].outcome, "NOANS", msg=n)
            self.assertIn("REASONING_ONLY", reasoner[n][0].flags, msg=n)

    def test_fake_server_drive(self):
        for order in ("A", "B"):
            turns = build_turns(10001, order)
            server = fakes.FakeServer("oracle", turns)
            run = test_fakes_smoke.drive(server, turns)
            self.assertEqual(len(run), 30)
            driven = []
            for t, status, resp in run:
                self.assertEqual(status, 200)
                driven.append((t, test_fakes_smoke.score(t, resp)))
            direct = [(t, judge(t, fakes.persona_answer("oracle", t))) for t in turns]
            self.assertEqual(summary(driven), summary(direct))
            self.check_oracle(driven)


if __name__ == "__main__":
    unittest.main()
