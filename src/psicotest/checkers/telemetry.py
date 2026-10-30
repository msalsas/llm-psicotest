import re
import unicodedata

from psicotest.checkers.cjk import LEAK_CLASSES, count_cjk

LOOP_WIDTH = 64
LOOP_REPEATS = 5
SELFCORR = (
    ("espera", re.compile(r"(?<![^\W_])espera(?![^\W_])")),
    ("wait", re.compile(r"(?<![^\W_])wait(?![^\W_])")),
    ("corrijo", re.compile(r"(?<![^\W_])corrijo(?![^\W_])")),
    ("en_realidad", re.compile(r"(?<![^\W_])en\s+realidad(?![^\W_])")),
    ("me_equivoque", re.compile(r"(?<![^\W_])me\s+equivoqu[eé](?![^\W_])")),
    ("error_mio", re.compile(r"(?<![^\W_])error\s+m[ií]o(?![^\W_])")),
)


def has_loop(text: str | None) -> bool:
    if not text:
        return False
    seen: dict[str, tuple[int, int]] = {}
    for i in range(len(text) - (LOOP_WIDTH - 1)):
        w = text[i : i + LOOP_WIDTH]
        if w in seen:
            count, last = seen[w]
            if i - last >= LOOP_WIDTH:
                count += 1
                seen[w] = (count, i)
                if count >= LOOP_REPEATS:
                    return True
        else:
            seen[w] = (1, i)
    return False


def selfcorr_counts(text: str | None) -> dict[str, int]:
    t = unicodedata.normalize("NFKC", text or "").casefold()
    out = {}
    total = 0
    for name, rx in SELFCORR:
        n = len(rx.findall(t))
        out[name] = n
        total += n
    out["total"] = total
    return out


def _leak_counts(text: str | None) -> dict[str, int]:
    c = count_cjk(text)
    out = {cls: c[cls] for cls in LEAK_CLASSES}
    out["total"] = c["leak_total"]
    return out


def measure(content: str | None, reasoning: str | None) -> dict:
    return {
        "schema": 1,
        "chars": {"content": len(content or ""), "reasoning": len(reasoning or "")},
        "leak": {"content": _leak_counts(content), "reasoning": _leak_counts(reasoning)},
        "cjk_punct": {
            "content": count_cjk(content)["punct"],
            "reasoning": count_cjk(reasoning)["punct"],
        },
        "selfcorr": {
            "content": selfcorr_counts(content),
            "reasoning": selfcorr_counts(reasoning),
        },
        "loop": {"content": has_loop(content), "reasoning": has_loop(reasoning)},
    }
