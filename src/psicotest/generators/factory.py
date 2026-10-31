from collections.abc import Mapping

from psicotest.checkers.common import ANSWER_KINDS, CAPABILITY_FAMILIES
from psicotest.generators.registry import GENERATORS, RULE_GENERATORS, SPECS
from psicotest.rng import Rng, derive_item_seed
from psicotest.spec import GenContext, Item


def make_item(
    *,
    battery: str,
    slot: str,
    generator: str,
    knobs: Mapping,
    variant: str,
    user_seed: int,
    animal: str | None = None,
    instance_slot: str | None = None,
    surface_slot: str | None = None,
) -> Item:
    fn, version = GENERATORS[generator]
    spec = SPECS[generator]
    if variant not in spec.variants:
        raise ValueError(f"unknown variant {variant} for {generator}")
    if animal is not None and generator in RULE_GENERATORS:
        raise ValueError("rule turns take no animal")
    instance_seed = derive_item_seed(
        battery, instance_slot or slot, generator, version, user_seed, "instance"
    )
    surface_seed = derive_item_seed(
        battery, surface_slot or slot, generator, version, user_seed, "surface"
    )
    surface = Rng(surface_seed)
    if variant == "relabel":
        surface = surface.fork("relabel")
    prompt, key, meta = fn(Rng(instance_seed), knobs, GenContext(variant, animal, surface))
    return Item(
        item_id=f"{battery}:{slot}:{generator}@{version}:{user_seed}:{variant}",
        battery_version=battery,
        slot=slot,
        family=spec.family,
        generator=generator,
        generator_version=version,
        knobs=dict(knobs),
        variant=variant,
        instance_seed=instance_seed,
        surface_seed=surface_seed,
        animal=animal,
        prompt_en=prompt,
        key=key,
        meta=meta,
        answer_kind=ANSWER_KINDS[spec.family],
        capability=spec.family in CAPABILITY_FAMILIES,
    )
