import itertools
import re
from decimal import Decimal
from fractions import Fraction

import _bootstrap

PERSON_COUNT = {
    "not_at": 1,
    "before": 2,
    "adjacent": 2,
    "not_adjacent": 2,
    "gap": 2,
    "offset": 2,
    "lt": 1,
    "gt": 1,
    "parity": 1,
    "in": 1,
    "between": 3,
}
ST_ADD = re.compile(r"^Add (\d+) marbles? to box ([A-Z])\.$")
ST_REMOVE = re.compile(r"^Take (\d+) marbles? out of box ([A-Z])\.$")
ST_MOVE = re.compile(r"^Move (\d+) marbles? from box ([A-Z]) to box ([A-Z])\.$")
ST_SWAP = re.compile(r"^Swap the entire contents of boxes ([A-Z]) and ([A-Z])\.$")
ST_COND = re.compile(
    r"^If box ([A-Z]) holds more marbles than box ([A-Z]), "
    r"move (\d+) marbles? from box ([A-Z]) to box ([A-Z]); otherwise do nothing\.$"
)
ST_START = re.compile(r"box ([A-Z]) holds (\d+) marbles?")
ERR_LINE = re.compile(
    r"^Step (\d+): (\d+) (\+|-|\N{MULTIPLICATION SIGN}) (\d+) = (\d+)\.$", re.MULTILINE
)
VOWELS = "aeiou"


def csp_holds(c, pos):
    op = c[0]
    if op == "not_at":
        return pos[c[1]] != c[2]
    if op == "before":
        return pos[c[1]] < pos[c[2]]
    if op == "adjacent":
        return abs(pos[c[1]] - pos[c[2]]) == 1
    if op == "not_adjacent":
        return abs(pos[c[1]] - pos[c[2]]) != 1
    if op == "gap":
        return abs(pos[c[1]] - pos[c[2]]) == c[3]
    if op == "offset":
        return pos[c[2]] - pos[c[1]] == c[3]
    if op == "lt":
        return pos[c[1]] < c[2]
    if op == "gt":
        return pos[c[1]] > c[2]
    if op == "parity":
        return pos[c[1]] % 2 == (0 if c[2] == "even" else 1)
    if op == "in":
        return pos[c[1]] in c[2]
    if op == "between":
        return min(pos[c[2]], pos[c[3]]) < pos[c[1]] < max(pos[c[2]], pos[c[3]])
    raise ValueError(op)


def csp_people(c):
    return list(c[1 : 1 + PERSON_COUNT[c[0]]])


def csp_scan(meta):
    people = meta["people"]
    constraints = meta["constraints"]
    solutions = []
    single = set()
    for perm in itertools.permutations(range(1, meta["n_slots"] + 1)):
        pos = dict(zip(people, perm, strict=True))
        failed = []
        for i, c in enumerate(constraints):
            if not csp_holds(c, pos):
                failed.append(i)
                if len(failed) > 1:
                    break
        if not failed:
            solutions.append(pos)
        elif len(failed) == 1:
            single.add(failed[0])
    return solutions, single


def csp_solutions(meta):
    return csp_scan(meta)[0]


def csp_hop2(meta):
    single = csp_scan(meta)[1]
    return sum(1 for i in sorted(single) if len(csp_people(meta["constraints"][i])) >= 2)


def csp_pins(c, n_slots):
    people = csp_people(c)
    seen = {p: set() for p in people}
    for slots in itertools.permutations(range(1, n_slots + 1), len(people)):
        pos = dict(zip(people, slots, strict=True))
        if csp_holds(c, pos):
            for p in people:
                seen[p].add(pos[p])
    return any(len(seen[p]) == 1 for p in people)


def log_truth(stmt, roles):
    op = stmt[0]
    if op == "role":
        return roles[stmt[1]] == stmt[2]
    if op == "same":
        return roles[stmt[1]] == roles[stmt[2]]
    if op == "diff":
        return roles[stmt[1]] != roles[stmt[2]]
    if op == "count":
        return sum(1 for r in roles.values() if r == "knight") == stmt[2]
    asked = roles[stmt[1]]
    if asked == "knight":
        return log_truth(stmt[2], roles)
    if asked == "knave":
        return not log_truth(stmt[2], roles)
    return True


def log_solutions(meta):
    agents = meta["agents"]
    out = []
    for spy in agents:
        others = [a for a in agents if a != spy]
        for combo in itertools.product(("knight", "knave"), repeat=len(others)):
            roles = dict(zip(others, combo, strict=True))
            roles[spy] = "spy"
            consistent = True
            for speaker, stmt in meta["statements"]:
                said = log_truth(stmt, roles)
                if (roles[speaker] == "knight" and not said) or (
                    roles[speaker] == "knave" and said
                ):
                    consistent = False
                    break
            if consistent:
                out.append(roles)
    return out


def st_replay(prompt):
    boxes = {label: int(v) for label, v in ST_START.findall(prompt)}
    for line in prompt.split("\n"):
        m = re.match(r"^\d+\. (.*)$", line)
        if m is None:
            continue
        text = m.group(1)
        if (g := ST_ADD.match(text)) is not None:
            boxes[g.group(2)] += int(g.group(1))
        elif (g := ST_REMOVE.match(text)) is not None:
            boxes[g.group(2)] -= int(g.group(1))
        elif (g := ST_MOVE.match(text)) is not None:
            boxes[g.group(2)] -= int(g.group(1))
            boxes[g.group(3)] += int(g.group(1))
        elif (g := ST_SWAP.match(text)) is not None:
            a, b = g.group(1), g.group(2)
            boxes[a], boxes[b] = boxes[b], boxes[a]
        elif (g := ST_COND.match(text)) is not None:
            a, b, k = g.group(1), g.group(2), int(g.group(3))
            if boxes[a] > boxes[b]:
                boxes[a] -= k
                boxes[b] += k
        else:
            raise ValueError(text)
    return boxes


def st_cond_lines(prompt):
    return sum(1 for line in prompt.split("\n") if ST_COND.match(re.sub(r"^\d+\. ", "", line)))


def st_op_lines(prompt):
    return sum(1 for line in prompt.split("\n") if re.match(r"^\d+\. ", line))


def err_lines(prompt):
    return [(int(i), int(x), op, int(y), int(z)) for i, x, op, y, z in ERR_LINE.findall(prompt)]


def chain_value(ops):
    v = Fraction(0)
    for op in ops:
        kind = op[0]
        if kind == "INIT":
            v = Fraction(op[1])
        elif kind == "ADD_GROUPS":
            v += op[1] * op[2]
        elif kind == "REMOVE_GROUPS":
            v -= op[1] * op[2]
        elif kind == "ADD":
            v += op[1]
        elif kind == "SUB":
            v -= op[1]
        else:
            v /= op[1]
    return v


def count_words(words, conditions):
    def holds(w, op, arg):
        if op == "start":
            return w.startswith(arg)
        if op == "end":
            return w.endswith(arg)
        if op == "contains":
            return arg in w
        if op == "not_contains":
            return arg not in w
        if op == "len_eq":
            return len(w) == arg
        if op == "len_ge":
            return len(w) >= arg
        return len([ch for ch in w if ch in VOWELS]) == arg

    return sum(1 for w in words if all(holds(w, op, arg) for op, arg in conditions))


def mult_density(a, b):
    rows = [(str(a * int(d))[::-1], j) for j, d in enumerate(reversed(str(b)))]
    width = max(j + len(s) for s, j in rows)
    carry = 0
    columns = 0
    carried = 0
    for i in range(width):
        digits = [int(s[i - j]) for s, j in rows if 0 <= i - j < len(s)]
        carry = (sum(digits) + carry) // 10
        if len(digits) >= 2:
            columns += 1
            carried += 1 if carry >= 1 else 0
    return Fraction(carried, columns)


def half_up(num, den):
    q = (2 * num * 100 + den) // (2 * den)
    return Decimal(f"{q // 100}.{q % 100:02d}")
