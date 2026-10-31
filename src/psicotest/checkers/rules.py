import re

from psicotest.checkers.extract import extract_answer
from psicotest.checkers.registry import check_turn
from psicotest.checkers.text import ARTICLES, fold
from psicotest.spec import Turn

ANIMAL_LINE_RE = re.compile(r"^\s*ANIMAL\s*:\s*(.*?)\s*\.?\s*$", re.IGNORECASE)
PLURAL_EXCEPTIONS = {
    "bison": "bison",
    "deer": "deer",
    "feet": "foot",
    "fish": "fish",
    "geese": "goose",
    "lice": "louse",
    "mice": "mouse",
    "moose": "moose",
    "octopi": "octopus",
    "oxen": "ox",
    "salmon": "salmon",
    "sheep": "sheep",
    "teeth": "tooth",
}


def singular_candidates(word: str) -> tuple[str, ...]:
    w = fold(word)
    out = []
    for cand in (
        w,
        w[:-1] if w.endswith("s") else None,
        w[:-2] if w.endswith("es") else None,
        w[:-3] + "y" if w.endswith("ies") else None,
        w[:-3] + "f" if w.endswith("ves") else None,
        w[:-3] + "fe" if w.endswith("ves") else None,
        PLURAL_EXCEPTIONS.get(w),
    ):
        if cand is not None and cand != "" and cand not in out:
            out.append(cand)
    return tuple(out)


def check_rules(
    content: str | None, turn: Turn, finish_reason: str | None = None
) -> dict[str, str]:
    if not isinstance(turn, Turn):
        raise TypeError("turn must be a Turn")
    if turn.r3_trigger and "R3" not in turn.rules_active:
        raise ValueError("trigger turn without R3")
    if turn.r3_trigger and (turn.item is None or turn.item.animal is None):
        raise ValueError("trigger turn without animal")
    ext = extract_answer(content)
    if finish_reason == "length":
        return {"R1": "NA", "R2": "NA", "R3": "NA", "R3_NOTE": ""}
    if "R1" in turn.rules_active:
        r1 = "R1_OK" if ext.n_resp == 1 and ext.last_line_ok else "R1_FAIL"
    else:
        r1 = "NA"
    if "R2" in turn.rules_active:
        r = check_turn(turn, content, None, None)
        if "R2_FAIL" in r.flags:
            r2 = "R2_FAIL"
        elif "R2_OK" in r.flags:
            r2 = "R2_OK"
        else:
            r2 = "NA"
    else:
        r2 = "NA"
    notes = set()
    if "R3" in turn.rules_active:
        animal_lines = [i for i, line in enumerate(ext.lines) if ANIMAL_LINE_RE.match(line)]
        if turn.r3_trigger:
            if not animal_lines:
                r3 = "R3_MISS"
            else:
                m = ANIMAL_LINE_RE.match(ext.lines[animal_lines[-1]])
                parts = fold(m.group(1)).split()
                if parts and parts[0] in ARTICLES:
                    parts = parts[1:]
                    notes.add("FMT")
                noun = " ".join(parts)
                if re.fullmatch(r"[a-z]+", noun) is None:
                    r3 = "R3_MISS"
                    notes.add("BAD_VALUE")
                else:
                    target = fold(turn.item.animal)
                    if noun == target:
                        r3 = "R3_HIT"
                    elif target in singular_candidates(noun):
                        r3 = "R3_HIT"
                        notes.add("FMT")
                    else:
                        r3 = "R3_MISS"
                        notes.add("WRONG_NOUN")
                if len(animal_lines) > 1:
                    notes.add("MULTI_ANIMAL")
                if r3 == "R3_HIT" and (
                    not ext.resp_lines or animal_lines[-1] + 1 != ext.resp_lines[-1]
                ):
                    notes.add("NOT_ADJACENT")
        else:
            r3 = "R3_FALSE" if animal_lines else "R3_CLEAN"
    else:
        r3 = "NA"
    return {"R1": r1, "R2": r2, "R3": r3, "R3_NOTE": ";".join(sorted(notes))}
