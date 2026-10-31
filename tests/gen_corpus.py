import functools
import re
import unicodedata

import _bootstrap
from battery_layout import rules_for

from psicotest.checkers.text import has_phrase, words
from psicotest.generators import make_item, reply_prompt
from psicotest.spec import Turn

FILLER = ("as an ai", "certainly", "challenge", "good luck", "i hope", "of course", "tricky")
PROPERTY_SEEDS = range(1, 501)
ANIMAL_SEEDS = range(1, 51)
CAP_GENS = (
    "gen_state_boxes",
    "gen_mult_carry",
    "gen_chain_decimal",
    "gen_gsm_noop",
    "gen_csp_perm",
    "gen_knights_spy",
    "gen_count_cond",
    "gen_planted_error",
    "gen_false_premise",
    "gen_authority_hint",
    "gen_missing_datum",
    "gen_derivable_datum",
)


@functools.cache
def corpus(generator, level, variant="base", animal=None):
    return tuple(
        make_item(
            battery="v2",
            slot="PROP",
            generator=generator,
            knobs={"level": level},
            variant=variant,
            user_seed=seed,
            animal=animal,
        )
        for seed in PROPERTY_SEEDS
    )


def check_surface(test, prompt, msg=None):
    plain = prompt
    for sign in ("MULTIPLICATION SIGN", "MINUS SIGN", "DIVISION SIGN"):
        plain = plain.replace(unicodedata.lookup(sign), "?")
    test.assertTrue(plain.isascii(), msg=msg)
    test.assertNotIn("\t", prompt, msg=msg)
    test.assertNotIn("  ", prompt, msg=msg)
    for line in prompt.split("\n"):
        test.assertEqual(line, line.strip(), msg=msg)
    test.assertNotIn(" .", prompt, msg=msg)
    test.assertNotIn(" ,", prompt, msg=msg)
    test.assertIn(prompt[-1], "?.:", msg=msg)
    test.assertNotIn("!", prompt, msg=msg)
    tokens = words(prompt)
    for filler in FILLER:
        test.assertFalse(has_phrase(tokens, tuple(filler.split())), msg=filler)
    test.assertIsNone(re.search(r"\d,\d", prompt), msg=msg)
    test.assertIsNone(re.search(r"\d\.\d{3}\b", prompt), msg=msg)


def turn_for(item, kind="item"):
    prompt = reply_prompt(item) if kind == "amb_reply" else item.prompt_en
    rules = rules_for(kind, item.family, 12)
    return Turn(12, kind, item.slot, prompt, item, rules, item.animal is not None)
