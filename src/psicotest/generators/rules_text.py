from collections.abc import Mapping

from psicotest.rng import Rng
from psicotest.spec import GenContext

R1_TEXT = "The last line of every reply must be exactly `ANSWER: <value>`, written once."
R2_TEXT = (
    "Write decimals with a decimal point, with no thousands separator and no units "
    "on the ANSWER line."
)
PROTO_TEXT = (
    "If a problem is missing an essential datum, reply only with one line "
    "`CLARIFICATION: <one question>`, with no ANSWER line and without assuming the datum."
)
SETUP_TEXT = (
    "We are going to do a series of exercises. Rules for the whole conversation:\n\n"
    f"1. {R1_TEXT}\n2. {R2_TEXT}\n3. {PROTO_TEXT}\n\n"
    "If you have understood, reply `ANSWER: OK`."
)
R3_TEXT = (
    "New rule from now on: if the problem mentions an animal, add another line "
    "`ANIMAL: <name of the animal, in the singular>` immediately before the ANSWER line."
)
RCL_TEXT = "List the format rules currently in force, one per line, as a list."


def _fixed(text: str, ctx: GenContext) -> tuple[str, dict, dict]:
    if ctx.animal is not None:
        raise ValueError("rule turns take no animal")
    return text, {}, {"instance": {}, "realized": {"level": 0}}


def setup_rules(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    return _fixed(SETUP_TEXT, ctx)


def rules_recall(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    return _fixed(RCL_TEXT, ctx)
