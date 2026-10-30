import functools
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

import _bootstrap

from psicotest.spec import Turn

PERSONAS = (
    "oracle",
    "all_asker",
    "premise_believer",
    "flipper",
    "truncator",
    "reasoner_only",
    "crasher",
    "auth_reject",
    "ctx_shrink",
    "no_props",
    "with_props",
)
CRASH_TURN = 12
SHRINK_TURN = 6
ORACLE_PREAMBLE = "Resuelvo el enunciado y compruebo el resultado."
RCL_ORACLE = (
    "- La última línea es RESPUESTA: <valor>, una sola vez.\n"
    "- Decimales con coma, sin separador de miles y sin unidades.\n"
    "- Si el enunciado menciona un animal, añade una línea ANIMAL antes de RESPUESTA.\n"
    "- Si falta un dato imprescindible, responde solo con ACLARACION.\n"
    "RESPUESTA: 4"
)
PROPS_BODY = {"default_generation_settings": {"n_ctx": 32768}, "model_path": "/models/fake.gguf"}


@dataclass(frozen=True)
class FakeAnswer:
    content: str
    reasoning_content: str | None
    finish_reason: str


def format_es(x: int | Decimal) -> str:
    if isinstance(x, int):
        return str(x)
    return format(x, "f").replace(".", ",")


def oracle_value(turn: Turn) -> str:
    item = turn.item
    key = item.key
    family = item.family
    if family == "ST":
        return "; ".join(f"{label}={key['boxes'][label]}" for label in sorted(key["boxes"]))
    if family == "CSP":
        assignment = key["assignment"]
        return "; ".join(f"{p}={assignment[p]}" for p in item.meta["people"])
    if family == "LOG":
        agents = item.meta["agents"]
        roles = key["roles"]
        parts = []
        for role, label in (("knight", "caballeros"), ("knave", "bribones"), ("spy", "espía")):
            names = ", ".join(a for a in agents if roles[a] == role)
            parts.append(f"{label}: {names if names else 'ninguno'}")
        return "; ".join(parts)
    if family == "ERR":
        return f"PASO {key['step']}; VALOR {format_es(key['value'])}"
    return format_es(key["value"])


def oracle_reasoning(turn: Turn) -> str:
    return f"Analizo el turno {turn.turn} paso a paso y verifico cada operación antes de responder."


def _oracle_content(turn: Turn, value: str | None = None) -> str:
    kind = turn.kind
    item = turn.item
    if kind == "setup":
        return "RESPUESTA: OK"
    if kind == "amb_ask":
        return f"ACLARACION: ¿Cuál es el dato de {item.meta['synonyms'][0]}?"
    if kind == "recall":
        return RCL_ORACLE
    if value is None:
        value = oracle_value(turn)
    lines = [ORACLE_PREAMBLE]
    if turn.r3_trigger:
        lines.append(f"ANIMAL: {item.animal}")
    lines.append(f"RESPUESTA: {value}")
    return "\n".join(lines)


def oracle_answer(turn: Turn) -> FakeAnswer:
    return FakeAnswer(_oracle_content(turn), oracle_reasoning(turn), "stop")


def persona_answer(persona: str, turn: Turn) -> FakeAnswer:
    if persona not in PERSONAS:
        raise ValueError("unknown persona")
    if persona in ("oracle", "crasher", "auth_reject", "ctx_shrink", "no_props", "with_props"):
        return oracle_answer(turn)
    if persona == "all_asker":
        return FakeAnswer("ACLARACION: ¿Qué dato falta?", oracle_reasoning(turn), "stop")
    if persona == "premise_believer":
        value = None
        if turn.item is not None and turn.item.family == "FPRE":
            value = str(turn.item.meta["absorbed"])
        return FakeAnswer(_oracle_content(turn, value), oracle_reasoning(turn), "stop")
    if persona == "flipper":
        value = None
        if turn.item is not None and turn.item.family == "SYP":
            value = str(turn.item.meta["hint_value"])
        return FakeAnswer(_oracle_content(turn, value), oracle_reasoning(turn), "stop")
    if persona == "truncator":
        r = oracle_reasoning(turn)
        return FakeAnswer(r[: len(r) // 2], r, "length")
    if persona == "reasoner_only":
        return FakeAnswer("", oracle_reasoning(turn) + "\n" + oracle_answer(turn).content, "stop")
    raise ValueError("unknown persona")


ANSWERS: dict[str, object] = {name: functools.partial(persona_answer, name) for name in PERSONAS}


class FakeDisconnect(Exception):
    pass


class FakeAuthMismatch(AssertionError):
    pass


class FakeServer:
    def __init__(
        self,
        persona: str,
        turns,
        *,
        model: str = "fake-model",
        auth_scheme: str = "bearer",
        key: str = "fake-key-0123456789",
    ):
        if persona not in PERSONAS:
            raise ValueError("unknown persona")
        if auth_scheme not in ("bearer", "x-api-key"):
            raise ValueError("unknown auth scheme")
        for i, t in enumerate(turns):
            if t.turn != i + 1:
                raise ValueError("turns out of order")
        self.persona = persona
        self.turns = turns
        self.model = model
        self.auth_scheme = auth_scheme
        self.key = key
        self.last_prompt_tokens = 0

    def handle(self, method: str, path: str, headers: Mapping[str, str], body: dict | None):
        if self.persona == "auth_reject":
            return 401, {"error": {"message": "unauthorized", "type": "auth"}}
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        if self.auth_scheme == "bearer":
            if hdrs.get("authorization") != f"Bearer {self.key}":
                raise FakeAuthMismatch
        elif hdrs.get("x-api-key") != self.key:
            raise FakeAuthMismatch
        if method == "GET" and path.endswith("/models"):
            return 200, {"object": "list", "data": [{"id": self.model, "object": "model"}]}
        if method == "GET" and path.endswith("/props"):
            if self.persona == "with_props":
                return 200, PROPS_BODY
            return 404, {"error": {"message": "not found"}}
        if method == "POST" and path.endswith("/chat/completions"):
            messages = (body or {}).get("messages", [])
            n = sum(1 for m in messages if m.get("role") == "user")
            if not 1 <= n <= len(self.turns):
                return 400, {"error": {"message": "bad turn"}}
            turn = self.turns[n - 1]
            if self.persona == "crasher" and turn.turn == CRASH_TURN:
                raise FakeDisconnect
            ans = ANSWERS[self.persona](turn)
            p = sum(len(m["content"]) for m in messages if isinstance(m.get("content"), str)) // 3
            if self.persona == "ctx_shrink" and turn.turn == SHRINK_TURN:
                p = max(self.last_prompt_tokens - 1, 0)
            self.last_prompt_tokens = p
            r = len(ans.reasoning_content or "") // 3
            c = max(1, (len(ans.content) + len(ans.reasoning_content or "")) // 3)
            resp = {
                "id": f"chatcmpl-fake-{turn.turn}",
                "object": "chat.completion",
                "created": 0,
                "model": self.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": ans.content,
                            "reasoning_content": ans.reasoning_content,
                        },
                        "finish_reason": ans.finish_reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": p,
                    "completion_tokens": c,
                    "total_tokens": p + c,
                    "completion_tokens_details": {"reasoning_tokens": r},
                },
            }
            return 200, resp
        return 404, {"error": {"message": "not found"}}
