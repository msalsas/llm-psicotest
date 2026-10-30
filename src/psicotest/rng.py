import hashlib
from collections.abc import Iterable, MutableSequence, Sequence
from typing import TypeVar

MASK64 = (1 << 64) - 1
GOLDEN_GAMMA = 0x9E3779B97F4A7C15
SEP = "\x1f"
ITEM_STREAMS = ("instance", "surface")

T = TypeVar("T")


def splitmix64(state: int) -> tuple[int, int]:
    if isinstance(state, bool) or not isinstance(state, int):
        raise TypeError("state must be an int")
    if state < 0 or state > MASK64:
        raise ValueError("state out of range")
    new_state = (state + GOLDEN_GAMMA) & MASK64
    z = new_state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return new_state, z ^ (z >> 31)


class Rng:
    __slots__ = ("_state",)

    def __init__(self, seed: int):
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an int")
        self._state = seed & MASK64

    def next_u64(self) -> int:
        self._state, out = splitmix64(self._state)
        return out

    def below(self, n: int) -> int:
        if isinstance(n, bool) or not isinstance(n, int):
            raise TypeError("n must be an int")
        if n < 1 or n > 1 << 64:
            raise ValueError("n out of range")
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            x = self.next_u64()
            if x < limit:
                return x % n

    def randint(self, lo: int, hi: int) -> int:
        if hi < lo:
            raise ValueError("hi < lo")
        return lo + self.below(hi - lo + 1)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self.below(len(seq))]

    def shuffle(self, lst: MutableSequence) -> None:
        for i in range(len(lst) - 1, 0, -1):
            j = self.below(i + 1)
            lst[i], lst[j] = lst[j], lst[i]

    def sample(self, seq: Iterable[T], k: int) -> list[T]:
        lst = list(seq)
        if k < 0 or k > len(lst):
            raise ValueError("k out of range")
        for i in range(k):
            j = i + self.below(len(lst) - i)
            lst[i], lst[j] = lst[j], lst[i]
        return lst[:k]

    def fork(self, label: str) -> "Rng":
        if not isinstance(label, str):
            raise TypeError("label must be a str")
        return Rng(derive_seed(self.next_u64(), label))


def derive_seed(*parts: str | int) -> int:
    if not parts:
        raise ValueError("at least one part required")
    for part in parts:
        if isinstance(part, bool) or not isinstance(part, (str, int)):
            raise TypeError("parts must be str or int")
        if isinstance(part, str) and SEP in part:
            raise ValueError("part contains separator")
    text = SEP.join(str.__str__(p) if isinstance(p, str) else int.__repr__(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def derive_item_seed(
    battery: str,
    slot: str,
    generator: str,
    generator_version: int,
    user_seed: int,
    stream: str,
) -> int:
    if stream not in ITEM_STREAMS:
        raise ValueError("unknown stream")
    return derive_seed("psicotest", battery, slot, generator, generator_version, user_seed, stream)
