"""LLM client: OpenRouter -> Anthropic -> local template.

stdlib urllib only. SPEC section 6.
"""
from __future__ import annotations

import json
import logging
import os
import socket
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


log = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a clinical pharmacology writer. Your job is to translate drug "
    "interaction mechanisms into clear, calm, two-paragraph patient explanations. "
    "You never invent severity. You never give dosing advice. You always end with "
    "a one-sentence reminder to consult a pharmacist."
)


USER_PROMPT_TEMPLATE = (
    "Drugs: {drug_a_name} ({drug_a_class}) + {drug_b_name} ({drug_b_class})\n"
    "Interaction severity: {severity}\n"
    "Mechanism (clinical): {mechanism}\n"
    "\n"
    "Write a 2-paragraph patient-friendly explanation. Plain English, no jargon.\n"
    "Paragraph 1: what happens in the body when these two are combined.\n"
    "Paragraph 2: what symptoms to watch for, and when to call a doctor versus\n"
    "when it's a \"mention at next visit\" concern.\n"
    "No bullet lists, no emojis. End with one short sentence reminding the\n"
    "reader to consult their pharmacist if unsure.\n"
)


def _ai_timeout() -> float:
    try:
        return float(os.environ.get("AI_TIMEOUT_S", "12"))
    except ValueError:
        return 12.0


def _have_openrouter() -> bool:
    return bool((os.environ.get("OPENROUTER_API_KEY") or "").strip())


def _have_anthropic() -> bool:
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())


def _openrouter_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")


def _anthropic_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")


def next_engine() -> str:
    """Return the engine the next call would use, without calling it."""
    if _have_openrouter():
        return "openrouter"
    if _have_anthropic():
        return "anthropic"
    return "template"


def _post_json(url: str, headers: dict, payload: dict, timeout: float) -> Optional[dict]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read()
        if status < 200 or status >= 300:
            log.info("LLM POST %s returned status %s", url, status)
            return None
        return json.loads(raw.decode("utf-8"))
    except (URLError, socket.timeout, TimeoutError, json.JSONDecodeError, ValueError, OSError) as e:
        log.info("LLM POST %s failed: %s", url, e)
        return None


def _call_openrouter(user_prompt: str) -> Optional[tuple[str, str]]:
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None
    model = _openrouter_model()
    payload = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 450,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "HTTP-Referer": "https://medsafety.local",
        "X-Title": "MedSafety",
    }
    result = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        headers,
        payload,
        _ai_timeout(),
    )
    if not result:
        return None
    try:
        text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    return text.strip(), f"openrouter:{model}"


def _call_anthropic(user_prompt: str) -> Optional[tuple[str, str]]:
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        return None
    model = _anthropic_model()
    payload = {
        "model": model,
        "max_tokens": 450,
        "temperature": 0.4,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    result = _post_json(
        "https://api.anthropic.com/v1/messages",
        headers,
        payload,
        _ai_timeout(),
    )
    if not result:
        return None
    try:
        blocks = result.get("content") or []
        parts: list[str] = []
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "text":
                t = b.get("text")
                if isinstance(t, str):
                    parts.append(t)
        text = "\n".join(parts).strip()
    except (AttributeError, TypeError):
        return None
    if not text:
        return None
    return text, f"anthropic:{model}"


_BUCKET_PARA_2 = {
    "contraindicated": (
        "If you find yourself taking these two medicines together, stop and call "
        "your prescriber now. This combination is one that doctors specifically "
        "try to avoid because the risk of harm is meaningful even over a short "
        "stretch. Symptoms that warrant an emergency visit include severe "
        "drowsiness, slowed or shallow breathing, severe muscle pain, unusual "
        "bleeding or bruising, very slow heartbeat, fainting, or new confusion."
    ),
    "major": (
        "Call your doctor or pharmacist within the next 24 hours and describe "
        "the combination. Watch for new bleeding or bruising, severe stomach "
        "pain, very dark or bloody stools, unusual drowsiness, dizziness, fast "
        "or pounding heartbeat, muscle pain or weakness, or trouble breathing. "
        "Seek emergency care immediately for any chest pain, fainting, severe "
        "shortness of breath, or signs of stroke."
    ),
    "moderate": (
        "This is worth mentioning at your next visit so your prescriber can "
        "decide whether to adjust doses, time the medicines further apart, or "
        "switch one of them. In the meantime, take note of new symptoms such as "
        "dizziness, stomach upset, swelling, unusual tiredness, or anything "
        "that feels different after starting both. If a symptom is severe or "
        "persistent, call sooner rather than waiting."
    ),
    "minor": (
        "No action is needed for most people. It is useful to know in case you "
        "notice the medicine working differently than expected, for example a "
        "lab value that drifts a little or a slightly slower response. If "
        "anything stands out to you, raise it at the next routine visit."
    ),
}


def _template_paragraph_1(drug_a_name: str, drug_a_class: str,
                          drug_b_name: str, drug_b_class: str,
                          mechanism: str) -> str:
    return (
        f"When {drug_a_name} (a {drug_a_class}) and {drug_b_name} "
        f"(a {drug_b_class}) are taken together, the way each medicine "
        f"normally works in the body can change. Specifically: {mechanism}. "
        "In plain terms, the two medicines either push in the same direction "
        "and add up, or one of them changes how the body handles the other, "
        "so the active amount that reaches the bloodstream is different from "
        "what each pill is supposed to deliver on its own."
    )


REMINDER_SENTENCE = (
    "If you are unsure, ask your pharmacist - they will check this combination for you."
)


def _template_response(drug_a_name: str, drug_a_class: str,
                       drug_b_name: str, drug_b_class: str,
                       severity: str, mechanism: str) -> tuple[str, str]:
    sev = severity if severity in _BUCKET_PARA_2 else "moderate"
    p1 = _template_paragraph_1(drug_a_name, drug_a_class, drug_b_name, drug_b_class, mechanism)
    p2 = _BUCKET_PARA_2[sev]
    text = f"{p1}\n\n{p2} {REMINDER_SENTENCE}"
    return text, "template"


# ---------------------------------------------------------------------------
# Patient Q&A about a single drug.
# ---------------------------------------------------------------------------

ASK_SYSTEM_PROMPT = (
    "You are a careful patient-facing pharmacology educator. You explain in "
    "plain English, in 2 or 3 short sentences. You never recommend a dose, "
    "never diagnose, and you always close with a one-sentence reminder to "
    "consult a pharmacist if anything is unclear."
)


ASK_USER_PROMPT_TEMPLATE = (
    "Drug: {drug_name} (class: {drug_class}; generic: {generic_name})\n"
    "Patient question: {question}\n"
    "\n"
    "Write a patient-friendly answer in 2-3 short sentences plus the "
    "pharmacist reminder. Plain English, no jargon, no bullet points, no "
    "emojis, no dosing recommendations.\n"
)


def _call_openrouter_ask(prompt: str) -> Optional[tuple[str, str]]:
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None
    model = _openrouter_model()
    payload = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 320,
        "messages": [
            {"role": "system", "content": ASK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "HTTP-Referer": "https://medsafety.local",
        "X-Title": "MedSafety",
    }
    result = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        headers,
        payload,
        _ai_timeout(),
    )
    if not result:
        return None
    try:
        text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    return text.strip(), f"openrouter:{model}"


def _call_anthropic_ask(prompt: str) -> Optional[tuple[str, str]]:
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        return None
    model = _anthropic_model()
    payload = {
        "model": model,
        "max_tokens": 320,
        "temperature": 0.4,
        "system": ASK_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    result = _post_json(
        "https://api.anthropic.com/v1/messages",
        headers,
        payload,
        _ai_timeout(),
    )
    if not result:
        return None
    blocks = result.get("content") or []
    parts: list[str] = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            t = b.get("text")
            if isinstance(t, str):
                parts.append(t)
    text = "\n".join(parts).strip()
    if not text:
        return None
    return text, f"anthropic:{model}"


def _ask_fallback(drug_name: str, drug_class: str, question: str) -> tuple[str, str]:
    q_short = (question or "").strip().rstrip("?")[:120] or "this question"
    text = (
        f"For a specific answer about {drug_name} and {q_short}, the safest "
        f"step is to bring this question to your pharmacist. As a general "
        f"rule, medicines in the {drug_class} class can interact with food, "
        f"alcohol, and other drugs in ways that vary by individual.\n"
        "If you are unsure, ask your pharmacist - they will check your full "
        "list and answer this for you."
    )
    return text, "template:ask"


def answer_drug_question(
    drug_name: str,
    drug_class: str,
    generic_name: str,
    question: str,
) -> tuple[str, str]:
    """Return ``(answer_text, model_label)`` for the /api/drugs/{id}/ask flow."""
    prompt = ASK_USER_PROMPT_TEMPLATE.format(
        drug_name=drug_name or "this medicine",
        drug_class=drug_class or "unknown",
        generic_name=generic_name or "n/a",
        question=question.strip(),
    )

    if _have_openrouter():
        out = _call_openrouter_ask(prompt)
        if out is not None:
            return out

    if _have_anthropic():
        out = _call_anthropic_ask(prompt)
        if out is not None:
            return out

    return _ask_fallback(drug_name or "this medicine", drug_class or "unknown", question)


def explain_interaction(
    drug_a_name: str,
    drug_a_class: str,
    drug_b_name: str,
    drug_b_class: str,
    severity: str,
    mechanism: str,
) -> tuple[str, str]:
    """Return (explanation_text, model_label). Falls back to template on any error."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        drug_a_name=drug_a_name,
        drug_a_class=drug_a_class,
        drug_b_name=drug_b_name,
        drug_b_class=drug_b_class,
        severity=severity,
        mechanism=mechanism,
    )

    if _have_openrouter():
        out = _call_openrouter(user_prompt)
        if out is not None:
            return out

    if _have_anthropic():
        out = _call_anthropic(user_prompt)
        if out is not None:
            return out

    return _template_response(
        drug_a_name, drug_a_class, drug_b_name, drug_b_class, severity, mechanism
    )
