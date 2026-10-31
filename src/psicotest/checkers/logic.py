import re

from psicotest.checkers import schema
from psicotest.checkers.common import make_result, reasoning_flags, resolve
from psicotest.checkers.text import fold, words

ROLE_WORDS = {
    "knight": "knight",
    "knights": "knight",
    "knave": "knave",
    "knaves": "knave",
    "spy": "spy",
    "spies": "spy",
}
NONE_WORDS = ("none", "nobody", "no one")
SEG_RE = re.compile(r"^([^:]+):(.*)$")
SPLIT_NAMES_RE = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+")
ROLES = ("knight", "knave", "spy")


def check_log(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "LOG")
    if early is not None:
        return early
    if pre.ext.value is None:
        return make_result("NOANS", None, reasoning_flags(pre), "")
    value = pre.ext.value
    segments = [seg.strip() for seg in value.split(";") if seg.strip() != ""]
    matched = [SEG_RE.match(seg) for seg in segments]
    if all(m is None for m in matched):
        if any(tok in ROLE_WORDS for tok in words(value)):
            return make_result("AMBIG", value, pre.flags, "no_structure")
        return make_result("NOANS", None, reasoning_flags(pre), "")
    role_names = []
    names_by_role = {}
    for m in matched:
        if m is None:
            return make_result("AMBIG", value, pre.flags, "unknown_role")
        role = ROLE_WORDS.get(fold(m.group(1)))
        if role is None:
            return make_result("AMBIG", value, pre.flags, "unknown_role")
        if role in role_names:
            return make_result("AMBIG", value, pre.flags, "dup_role")
        role_names.append(role)
        parts = [p for p in SPLIT_NAMES_RE.split(fold(m.group(2)).strip()) if p != ""]
        if len(parts) == 1 and parts[0] in NONE_WORDS:
            parts = []
        names_by_role[role] = parts
    agents = list(item.meta["agents"])
    role_agents = []
    for role in role_names:
        for name in names_by_role[role]:
            person = resolve(name, agents)
            if person is None:
                return make_result("AMBIG", value, pre.flags, f"unknown_name:{fold(name)}")
            role_agents.append((role, person))
    mapping = {}
    for role, person in role_agents:
        if person in mapping:
            return make_result("AMBIG", value, pre.flags, f"conflict:{person}")
        mapping[person] = role
    details = []
    unassigned = [a for a in agents if a not in mapping]
    if unassigned:
        unnamed = [r for r in ROLES if r not in role_names]
        if len(unnamed) != 1:
            return make_result("AMBIG", value, pre.flags, "underdetermined")
        for a in unassigned:
            mapping[a] = unnamed[0]
        details.append("complement")
    result = {role: [a for a in agents if mapping.get(a) == role] for role in ROLES}
    detail = ";".join(details)
    key_roles = item.key["roles"]
    if all(mapping.get(a) == key_roles.get(a) for a in agents):
        return make_result("OK", result, pre.flags, detail)
    return make_result("WRONG", result, pre.flags, detail)
