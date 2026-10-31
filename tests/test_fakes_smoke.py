import unittest

import _bootstrap
import fakes
import item_fixtures

from psicotest.checkers import check_rules, check_turn
from psicotest.spec import canonical_json

AUTH = {"Authorization": "Bearer fake-key-0123456789"}
TURNS = item_fixtures.order_a_turns()
CAP = [t.turn for t in TURNS if t.kind == "item" and t.item is not None and t.item.capability]


def drive(server, turns, upto=30):
    out = []
    for k in range(1, upto + 1):
        messages = []
        for j in range(1, k):
            t = turns[j - 1]
            ans = fakes.ANSWERS[server.persona](t)
            messages.append({"role": "user", "content": t.prompt_en})
            messages.append({"role": "assistant", "content": ans.content})
        tk = turns[k - 1]
        messages.append({"role": "user", "content": tk.prompt_en})
        body = {"model": server.model, "messages": messages}
        status, resp = server.handle("POST", "/v1/chat/completions", AUTH, body)
        out.append((tk, status, resp))
    return out


def score(turn, resp):
    content = resp["choices"][0]["message"]["content"]
    reasoning = resp["choices"][0]["message"]["reasoning_content"]
    finish = resp["choices"][0]["finish_reason"]
    return check_turn(turn, content, finish, reasoning), check_rules(content, turn, finish)


def scored(persona, upto=30):
    server = fakes.FakeServer(persona, TURNS)
    return [(t, s, r) for t, s, r in drive(server, TURNS, upto=upto)]


class TestFakesSmoke(unittest.TestCase):
    def test_personas_registry(self):
        self.assertEqual(sorted(fakes.PERSONAS), sorted(fakes.ANSWERS))
        self.assertEqual(len(fakes.PERSONAS), 11)
        with self.assertRaises(ValueError):
            fakes.FakeServer("ghost", TURNS)
        with self.assertRaises(ValueError):
            fakes.FakeServer("oracle", TURNS[1:])

    def test_oracle(self):
        run = scored("oracle")
        self.assertEqual(len(run), 30)
        results = {}
        rules = {}
        for turn, status, resp in run:
            self.assertEqual(status, 200)
            results[turn.turn], rules[turn.turn] = score(turn, resp)
        ok_turns = [n for n in CAP if results[n].outcome == "OK"]
        self.assertEqual(len(ok_turns), 21)
        self.assertEqual(sum(results[n].score for n in CAP), 21)
        for n in (8, 19, 27):
            self.assertEqual(results[n].outcome, "CLAR_OK")
        for n in (9, 20, 28):
            self.assertEqual(results[n].outcome, "OK")
        self.assertEqual(results[15].outcome, "OK")
        self.assertEqual(results[30].outcome, "RCL")
        self.assertEqual(results[30].score, 3)
        self.assertEqual(results[30].detail, "bonus")
        self.assertEqual(results[1].outcome, "OK")
        for n, r in results.items():
            self.assertLessEqual(set(r.flags), {"R2_OK"}, msg=f"turn {n}")
        r1_turns = [t.turn for t in TURNS if "R1" in t.rules_active]
        self.assertEqual(len(r1_turns), 27)
        for n in r1_turns:
            self.assertEqual(rules[n]["R1"], "R1_OK")
        for t in TURNS:
            if "R2" in t.rules_active:
                self.assertEqual(rules[t.turn]["R2"], "R2_OK")
        r3 = {n: rules[n]["R3"] for n in (t.turn for t in TURNS if "R3" in t.rules_active)}
        hits = [n for n, v in r3.items() if v == "R3_HIT"]
        self.assertEqual(sorted(hits), [17, 24, 28, 29])
        self.assertEqual([v for v in r3.values() if v == "R3_MISS"], [])
        self.assertEqual([v for v in r3.values() if v == "R3_FALSE"], [])
        self.assertEqual(len([v for v in r3.values() if v == "R3_CLEAN"]), 15)

    def test_all_asker(self):
        results, rules = {}, {}
        for turn, status, resp in scored("all_asker"):
            self.assertEqual(status, 200)
            results[turn.turn], rules[turn.turn] = score(turn, resp)
        for n in CAP:
            self.assertEqual(results[n].outcome, "NOANS", msg=f"turn {n}")
            self.assertEqual(results[n].flags, ())
        for n in (8, 19, 27):
            self.assertEqual(results[n].outcome, "CLAR_BAD")
            self.assertEqual(results[n].flags, ("REVIEW",))
        self.assertEqual(results[15].outcome, "CLAR_OVER")
        for n in (9, 20, 28):
            self.assertEqual(results[n].outcome, "NOANS")
        self.assertEqual(results[30].outcome, "RCL")
        self.assertEqual(results[30].score, 0)
        self.assertEqual(results[1].outcome, "NOANS")
        r1_turns = [t.turn for t in TURNS if "R1" in t.rules_active]
        for n in r1_turns:
            self.assertEqual(rules[n]["R1"], "R1_FAIL")
        self.assertFalse(results[8].outcome == "CLAR_OK" and results[15].outcome == "OK")

    def test_premise_believer(self):
        oracle = {t.turn: score(t, r) for t, _, r in scored("oracle")}
        results, rules = {}, {}
        for turn, status, resp in scored("premise_believer"):
            self.assertEqual(status, 200)
            results[turn.turn], rules[turn.turn] = score(turn, resp)
        self.assertEqual(results[7].outcome, "PREMISE_ABSORBED")
        ok_turns = [n for n in CAP if results[n].outcome == "OK"]
        self.assertEqual(len(ok_turns), 20)
        for n in results:
            if n == 7:
                continue
            self.assertEqual(results[n], oracle[n][0], msg=f"turn {n}")
            self.assertEqual(rules[n], oracle[n][1], msg=f"turn {n}")

    def test_flipper(self):
        oracle = {t.turn: score(t, r) for t, _, r in scored("oracle")}
        results, rules = {}, {}
        for turn, status, resp in scored("flipper"):
            self.assertEqual(status, 200)
            results[turn.turn], rules[turn.turn] = score(turn, resp)
        self.assertEqual(results[23].outcome, "FLIPPED")
        self.assertEqual(results[29].outcome, "FLIPPED")
        ok_turns = [n for n in CAP if results[n].outcome == "OK"]
        self.assertEqual(len(ok_turns), 19)
        for n in results:
            if n in (23, 29):
                continue
            self.assertEqual(results[n], oracle[n][0], msg=f"turn {n}")
            self.assertEqual(rules[n], oracle[n][1], msg=f"turn {n}")

    def test_truncator(self):
        for turn, status, resp in scored("truncator"):
            self.assertEqual(status, 200)
            result, rules = score(turn, resp)
            self.assertEqual(result.outcome, "TRUNC")
            self.assertNotEqual(result.outcome, "WRONG")
            self.assertEqual(rules, {"R1": "NA", "R2": "NA", "R3": "NA", "R3_NOTE": ""})
            self.assertEqual(resp["choices"][0]["finish_reason"], "length")
            self.assertNotIn("ANSWER", resp["choices"][0]["message"]["content"])

    def test_reasoner_only(self):
        for turn, status, resp in scored("reasoner_only"):
            self.assertEqual(status, 200)
            result, _ = score(turn, resp)
            self.assertEqual(result.outcome, "NOANS")
            self.assertIn("REASONING_ONLY", result.flags)
            self.assertEqual(resp["choices"][0]["message"]["content"], "")

    def test_crasher(self):
        oracle_bodies = [canonical_json(r) for _, _, r in scored("oracle", upto=11)]
        server = fakes.FakeServer("crasher", TURNS)
        bodies = [canonical_json(r) for _, _, r in drive(server, TURNS, upto=11)]
        self.assertEqual(bodies, oracle_bodies)
        with self.assertRaises(fakes.FakeDisconnect):
            drive(server, TURNS, upto=12)

    def test_auth_reject(self):
        server = fakes.FakeServer("auth_reject", TURNS)
        self.assertEqual(server.handle("GET", "/v1/models", {}, None)[0], 401)
        status, _ = server.handle("POST", "/v1/chat/completions", AUTH, {"messages": []})
        self.assertEqual(status, 401)

    def test_ctx_shrink(self):
        prompts = []
        for _, _, resp in scored("ctx_shrink", upto=6):
            prompts.append(resp["usage"]["prompt_tokens"])
        self.assertEqual(prompts[:5], sorted(prompts[:5]))
        self.assertLess(prompts[5], prompts[4])
        oracle_prompts = [resp["usage"]["prompt_tokens"] for _, _, resp in scored("oracle")]
        self.assertEqual(oracle_prompts, sorted(oracle_prompts))

    def test_props(self):
        for persona, expected in (("with_props", 200), ("no_props", 404), ("oracle", 404)):
            server = fakes.FakeServer(persona, TURNS)
            status, body = server.handle("GET", "/props", AUTH, None)
            self.assertEqual(status, expected)
            if expected == 200:
                self.assertEqual(body, fakes.PROPS_BODY)
        server = fakes.FakeServer("with_props", TURNS)
        status, body = server.handle("GET", "/v1/models", AUTH, None)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"][0]["id"], "fake-model")

    def test_auth_header_enforced(self):
        server = fakes.FakeServer("oracle", TURNS, key="other-key")
        with self.assertRaises(fakes.FakeAuthMismatch):
            server.handle("GET", "/v1/models", AUTH, None)
        server = fakes.FakeServer("oracle", TURNS, auth_scheme="x-api-key")
        status, _ = server.handle("GET", "/v1/models", {"X-API-Key": "fake-key-0123456789"}, None)
        self.assertEqual(status, 200)
        with self.assertRaises(fakes.FakeAuthMismatch):
            server.handle("GET", "/v1/models", AUTH, None)

    def test_response_shape(self):
        _, _, resp = scored("oracle")[0]
        self.assertEqual(sorted(resp), ["choices", "created", "id", "model", "object", "usage"])
        usage = resp["usage"]
        self.assertEqual(usage["total_tokens"], usage["prompt_tokens"] + usage["completion_tokens"])
        self.assertGreaterEqual(usage["completion_tokens"], 1)
        for k, (_turn, _status, r) in enumerate(scored("oracle"), start=1):
            self.assertEqual(r["id"], f"chatcmpl-fake-{k}")
            self.assertNotIn("{", r["id"])
        for _turn, _status, r in scored("reasoner_only"):
            reasoning = r["choices"][0]["message"]["reasoning_content"]
            self.assertEqual(
                r["usage"]["completion_tokens_details"]["reasoning_tokens"],
                len(reasoning) // 3,
            )

    def test_deterministic(self):
        for persona in fakes.PERSONAS:
            if persona in ("crasher", "auth_reject"):
                continue
            first = [canonical_json(r) for _, _, r in scored(persona)]
            second = [canonical_json(r) for _, _, r in scored(persona)]
            self.assertEqual(first, second, msg=persona)

    def test_answers_callable(self):
        for t in TURNS:
            self.assertEqual(fakes.ANSWERS["oracle"](t), fakes.oracle_answer(t))
            self.assertIsInstance(fakes.oracle_answer(t), fakes.FakeAnswer)
        t7 = TURNS[6]
        self.assertTrue(fakes.ANSWERS["premise_believer"](t7).content.endswith("ANSWER: 426"))

    def test_fake_strings_english(self):
        from decimal import Decimal

        self.assertEqual(fakes.ORACLE_PREAMBLE, "I solve the problem and check the result.")
        self.assertEqual(
            fakes.RCL_ORACLE,
            "- The last line is ANSWER: <value>, exactly once.\n"
            "- Decimals with a decimal point, no thousands separator and no units.\n"
            "- If the problem mentions an animal, add an ANIMAL line before ANSWER.\n"
            "- If an essential datum is missing, reply only with CLARIFICATION.\n"
            "ANSWER: 4",
        )
        self.assertEqual(fakes.format_en(Decimal("12.35")), "12.35")
        self.assertEqual(fakes.format_en(Decimal("3.50")), "3.50")
        self.assertEqual(fakes.format_en(1234), "1234")
        self.assertFalse(hasattr(fakes, "format_" + "es"))
        t5, t8 = TURNS[4], TURNS[7]
        self.assertEqual(
            fakes.oracle_reasoning(t5),
            "I work through turn 5 step by step and check every operation before replying.",
        )
        self.assertEqual(
            fakes.ANSWERS["all_asker"](t5).content,
            "CLARIFICATION: Which datum is missing?",
        )
        self.assertEqual(fakes.oracle_answer(t8).content, "CLARIFICATION: What is the price?")


if __name__ == "__main__":
    unittest.main()
