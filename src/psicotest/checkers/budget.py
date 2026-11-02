from collections.abc import Sequence

BUDGET_MARKER = "I have thought about this long enough; time to give my answer"
BUDGET_MARGIN = 448
BUDGET_BAND = 32
BUDGET_MIN_CLUSTER = 4
BUDGET_MIN_GAP = 256


def has_budget_marker(text: str | None) -> bool:
    return BUDGET_MARKER in (text or "")


def infer_budget_cap(completion_tokens: Sequence[int]) -> int | None:
    values = list(completion_tokens)
    if len(values) < BUDGET_MIN_CLUSTER:
        return None
    top = max(values)
    window = sorted(value for value in values if value >= top - BUDGET_MARGIN)
    cap = None
    for index, low in enumerate(window):
        count = sum(1 for value in window[index:] if value <= low + BUDGET_BAND)
        if count >= BUDGET_MIN_CLUSTER:
            cap = low
            break
    if cap is None:
        return None
    below = [value for value in values if value < cap]
    if not below or cap - max(below) < BUDGET_MIN_GAP:
        return None
    return cap


def budget_flags(completion_tokens: Sequence[int]) -> list[bool]:
    values = list(completion_tokens)
    cap = infer_budget_cap(values)
    return [cap is not None and value >= cap for value in values]
