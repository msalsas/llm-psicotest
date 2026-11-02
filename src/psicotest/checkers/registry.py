from collections.abc import Callable

from psicotest.checkers.common import CAPABILITY_FAMILIES
from psicotest.checkers.err import check_err
from psicotest.checkers.keyed import check_csp, check_ic, check_st
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
from psicotest.checkers.prose_block import check_pr
from psicotest.checkers.prose_consistency import check_pc
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
    "IC": check_ic,
    "PR": check_pr,
    "PC": check_pc,
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


def check_turn(turn: Turn, content, finish_reason, reasoning, prior=None):
    key = dispatch_key(turn)
    if key == "PC":
        return CHECKERS[key](content, finish_reason, reasoning, turn.item, prior=prior)
    return CHECKERS[key](content, finish_reason, reasoning, turn.item)
