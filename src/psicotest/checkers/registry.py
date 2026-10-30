from collections.abc import Callable

from psicotest.checkers.common import CAPABILITY_FAMILIES
from psicotest.checkers.err import check_err
from psicotest.checkers.keyed import check_csp, check_st
from psicotest.checkers.logic import check_log
from psicotest.checkers.numeric import (
    check_ambr,
    check_ar,
    check_ar2,
    check_cnt,
    check_fpre,
    check_noop,
    check_setup,
    check_syp,
)
from psicotest.checkers.protocol import check_amb, check_ambc, check_rcl
from psicotest.spec import Turn

CHECKERS: dict[str, Callable] = {
    "ST": check_st,
    "AR": check_ar,
    "AR2": check_ar2,
    "NOOP": check_noop,
    "CSP": check_csp,
    "LOG": check_log,
    "CNT": check_cnt,
    "ERR": check_err,
    "FPRE": check_fpre,
    "SYP": check_syp,
    "AMB": check_amb,
    "AMBR": check_ambr,
    "AMBC": check_ambc,
    "RCL": check_rcl,
    "SETUP": check_setup,
}


def dispatch_key(turn: Turn) -> str:
    if not isinstance(turn, Turn):
        raise TypeError("turn must be a Turn")
    kind = turn.kind
    if kind == "setup":
        return "SETUP"
    if turn.item is None:
        raise ValueError("turn without item")
    if kind == "amb_ask":
        return "AMB"
    if kind == "amb_reply":
        return "AMBR"
    if kind == "recall":
        return "RCL"
    if kind == "item":
        family = turn.item.family
        if family in CAPABILITY_FAMILIES or family == "AMBC":
            return family
        raise ValueError("bad family")
    raise ValueError("unknown kind")


def check_turn(turn: Turn, content, finish_reason, reasoning):
    return CHECKERS[dispatch_key(turn)](content, finish_reason, reasoning, turn.item)
