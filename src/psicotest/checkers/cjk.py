from bisect import bisect_right

RANGES = (
    (0x1100, 0x11FF, "hangul"),
    (0x2E80, 0x2EFF, "han"),
    (0x2F00, 0x2FDF, "han"),
    (0x3000, 0x303F, "punct"),
    (0x3040, 0x309F, "kana"),
    (0x30A0, 0x30FF, "kana"),
    (0x3100, 0x312F, "bopomofo"),
    (0x3130, 0x318F, "hangul"),
    (0x31A0, 0x31BF, "bopomofo"),
    (0x31C0, 0x31EF, "han"),
    (0x31F0, 0x31FF, "kana"),
    (0x3200, 0x33FF, "punct"),
    (0x3400, 0x9FFF, "han"),
    (0xA960, 0xA97F, "hangul"),
    (0xAC00, 0xD7AF, "hangul"),
    (0xD7B0, 0xD7FF, "hangul"),
    (0xF900, 0xFAFF, "han"),
    (0xFE30, 0xFE4F, "punct"),
    (0xFF01, 0xFF65, "punct"),
    (0xFF66, 0xFF9F, "kana"),
    (0xFFA0, 0xFFDC, "hangul"),
    (0x1B000, 0x1B16F, "kana"),
    (0x20000, 0x3FFFF, "han"),
)

LEAK_CLASSES = ("han", "kana", "hangul", "bopomofo")

_LOS = tuple(r[0] for r in RANGES)


def cjk_class(ch: str) -> str | None:
    if not isinstance(ch, str) or len(ch) != 1:
        raise TypeError("expected a single character")
    i = bisect_right(_LOS, ord(ch)) - 1
    if i < 0:
        return None
    lo, hi, cls = RANGES[i]
    return cls if lo <= ord(ch) <= hi else None


def count_cjk(text: str | None) -> dict[str, int]:
    counts = {"han": 0, "kana": 0, "hangul": 0, "bopomofo": 0, "punct": 0}
    for ch in text or "":
        cls = cjk_class(ch)
        if cls is not None:
            counts[cls] += 1
    counts["leak_total"] = sum(counts[cls] for cls in LEAK_CLASSES)
    return counts


def has_leak(text: str | None) -> bool:
    return count_cjk(text)["leak_total"] > 0
