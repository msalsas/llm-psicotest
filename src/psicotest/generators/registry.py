from collections.abc import Callable

from psicotest.generators.authority_hint import gen_authority_hint
from psicotest.generators.chain_decimal import gen_chain_decimal
from psicotest.generators.count_cond import gen_count_cond
from psicotest.generators.csp_perm import gen_csp_perm
from psicotest.generators.derivable_datum import gen_derivable_datum
from psicotest.generators.false_premise import gen_false_premise
from psicotest.generators.gsm_noop import gen_gsm_noop
from psicotest.generators.knights_spy import gen_knights_spy
from psicotest.generators.missing_datum import gen_missing_datum
from psicotest.generators.mult_carry import gen_mult_carry
from psicotest.generators.planted_error import gen_planted_error
from psicotest.generators.rules_text import rules_recall, setup_rules
from psicotest.generators.state_boxes import gen_state_boxes
from psicotest.spec import GeneratorSpec, Item

GENERATORS: dict[str, tuple[Callable, int]] = {
    "gen_state_boxes": (gen_state_boxes, 1),
    "gen_mult_carry": (gen_mult_carry, 1),
    "gen_chain_decimal": (gen_chain_decimal, 1),
    "gen_gsm_noop": (gen_gsm_noop, 1),
    "gen_csp_perm": (gen_csp_perm, 1),
    "gen_knights_spy": (gen_knights_spy, 1),
    "gen_count_cond": (gen_count_cond, 1),
    "gen_planted_error": (gen_planted_error, 1),
    "gen_false_premise": (gen_false_premise, 1),
    "gen_authority_hint": (gen_authority_hint, 1),
    "gen_missing_datum": (gen_missing_datum, 1),
    "gen_derivable_datum": (gen_derivable_datum, 1),
    "setup_rules": (setup_rules, 1),
    "rules_recall": (rules_recall, 1),
}

_FAMILIES = {
    "gen_state_boxes": ("ST", ("base", "relabel"), (-1, 0, 1, 2)),
    "gen_mult_carry": ("AR", ("base",), (-1, 0, 1, 2)),
    "gen_chain_decimal": ("AR2", ("base",), (-1, 0, 1, 2)),
    "gen_gsm_noop": ("NOOP", ("base", "clean", "relabel"), (-1, 0, 1, 2)),
    "gen_csp_perm": ("CSP", ("base", "relabel"), (-1, 0, 1, 2)),
    "gen_knights_spy": ("LOG", ("base", "relabel"), (-1, 0, 1, 2)),
    "gen_count_cond": ("CNT", ("base", "relabel"), (-1, 0, 1, 2)),
    "gen_planted_error": ("ERR", ("base", "relabel"), (-1, 0, 1, 2)),
    "gen_false_premise": ("FPRE", ("base",), (-1, 0, 1, 2)),
    "gen_authority_hint": ("SYP", ("base", "relabel"), (-1, 0, 1, 2)),
    "gen_missing_datum": ("AMB", ("base", "relabel"), (0,)),
    "gen_derivable_datum": ("AMBC", ("base", "relabel"), (0,)),
    "setup_rules": ("SETUP", ("base",), (0,)),
    "rules_recall": ("RCL", ("base",), (0,)),
}

SPECS: dict[str, GeneratorSpec] = {
    name: GeneratorSpec(name, GENERATORS[name][1], family, variants)
    for name, (family, variants, _) in _FAMILIES.items()
}
LEVELS_OF: dict[str, tuple[int, ...]] = {name: levels for name, (_, _, levels) in _FAMILIES.items()}
START_KNOBS: dict[str, dict] = {name: {"level": 0} for name in GENERATORS}
GOLDEN_SEEDS = (1, 2, 3, 42, 1000)
GOLDEN_ANIMAL = "sheep"
RULE_GENERATORS = ("setup_rules", "rules_recall")


def golden_items() -> dict[str, Item]:
    from psicotest.generators.factory import make_item

    out = {}
    for name in sorted(GENERATORS):
        spec = SPECS[name]
        cases = [(seed, variant, None) for seed in GOLDEN_SEEDS for variant in spec.variants]
        if name not in RULE_GENERATORS:
            cases.append((1, "base", GOLDEN_ANIMAL))
        for seed, variant, animal in cases:
            out[spec.key(seed, variant, animal)] = make_item(
                battery="v2",
                slot="GOLD",
                generator=name,
                knobs=START_KNOBS[name],
                variant=variant,
                user_seed=seed,
                animal=animal,
            )
    return out
