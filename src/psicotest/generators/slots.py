import dataclasses
from collections.abc import Mapping

from psicotest.checkers.common import CAPABILITY_FAMILIES
from psicotest.generators.factory import make_item
from psicotest.spec import Item


@dataclasses.dataclass(frozen=True)
class SlotSpec:
    slot: str
    family: str
    generator: str
    knobs: Mapping[str, int]
    variant: str
    twin_of: str | None
    mirror_of: str | None
    scoring: str
    capability: bool


def _row(
    slot: str,
    family: str,
    generator: str,
    scoring: str,
    level: int = 0,
    variant: str = "base",
    twin_of: str | None = None,
    mirror_of: str | None = None,
    **overrides: int,
) -> SlotSpec:
    return SlotSpec(
        slot,
        family,
        generator,
        {"level": level, **overrides},
        variant,
        twin_of,
        mirror_of,
        scoring,
        family in CAPABILITY_FAMILIES,
    )


SLOTS_V2 = (
    _row("S01", "ST", "gen_state_boxes", "exact_keys"),
    _row("S02", "AR", "gen_mult_carry", "exact_int"),
    _row("S03", "NOOP", "gen_gsm_noop", "exact_num", n_distractors=4),
    _row("S04", "CSP", "gen_csp_perm", "csp_verify", n_constraints=13),
    _row("S05", "LOG", "gen_knights_spy", "exact_roles"),
    _row("S06", "FPRE", "gen_false_premise", "premise3"),
    _row("S07", "AMB", "gen_missing_datum", "clar"),
    _row("S08", "ERR", "gen_planted_error", "err_step_value"),
    _row("S09", "ST", "gen_state_boxes", "exact_keys", level=1),
    _row("S10", "AR2", "gen_chain_decimal", "exact_2dp"),
    _row("S11", "NOOP", "gen_gsm_noop", "exact_num", n_distractors=5),
    _row("S12", "CSP", "gen_csp_perm", "csp_verify", twin_of="S04", n_constraints=13),
    _row("S13", "AMBC", "gen_derivable_datum", "exact_num"),
    _row(
        "S14",
        "NOOP",
        "gen_gsm_noop",
        "exact_num",
        variant="clean",
        mirror_of="S03",
        n_distractors=4,
    ),
    _row("S15", "ST", "gen_state_boxes", "exact_keys", twin_of="S01"),
    _row("S16", "LOG", "gen_knights_spy", "exact_roles", level=1),
    _row("S17", "AMB", "gen_missing_datum", "clar"),
    _row("S18", "LOG", "gen_knights_spy", "exact_roles", twin_of="S05"),
    _row("S19", "AR", "gen_mult_carry", "exact_int", twin_of="S02"),
    _row("S20", "SYP", "gen_authority_hint", "syco3"),
    _row("S21", "CNT", "gen_count_cond", "exact_int", level=1),
    _row("S22", "ERR", "gen_planted_error", "err_step_value", level=1),
    _row("S23", "ST", "gen_state_boxes", "exact_keys", level=2),
    _row("S24", "AMB", "gen_missing_datum", "clar"),
    _row("S25", "SYP", "gen_authority_hint", "syco3", level=1),
    _row("S26", "RCL", "rules_recall", "recall"),
)


def build_slot_item(
    spec: SlotSpec, user_seed: int, battery: str = "v2", animal: str | None = None
) -> Item:
    if spec.twin_of is not None:
        instance_slot, surface_slot = spec.twin_of, spec.slot
    elif spec.mirror_of is not None:
        instance_slot = surface_slot = spec.mirror_of
    else:
        instance_slot = surface_slot = spec.slot
    return make_item(
        battery=battery,
        slot=spec.slot,
        generator=spec.generator,
        knobs=spec.knobs,
        variant=spec.variant,
        user_seed=user_seed,
        animal=animal,
        instance_slot=instance_slot,
        surface_slot=surface_slot,
    )
